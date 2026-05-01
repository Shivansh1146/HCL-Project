import aiosqlite
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TEST_DB_PATH") or os.path.join(BASE_DIR, "reviews.db")
logger = logging.getLogger("backend")

# Global connection removed to prevent transaction bleeding
@asynccontextmanager
async def get_db():
    """Returns a new, dedicated database connection per task."""
    db = await aiosqlite.connect(DB_PATH, timeout=30.0)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    try:
        yield db
    finally:
        await db.close()

async def db_retry(func, *args, retries=3, delay=1, **kwargs):
    """Wrapper to retry database operations on failure."""
    for attempt in range(retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                logger.error(f"Database operation failed after {retries} attempts: {str(e)}")
                raise
            await asyncio.sleep(delay * (attempt + 1))

async def close_db():
    """No-op for backward compatibility."""
    pass

async def initialize_db():
    """Initializes the SQLite database with schema versioning and migrations."""
    async with get_db() as db:
        # 1. Base Tables
        await db.execute('''
            CREATE TABLE IF NOT EXISTS prs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT,
                pr_number INTEGER,
                reviewed_at TEXT,
                status TEXT DEFAULT 'success'
            )
        ''')
        # Backward compatibility migration: add decision columns for older DBs.
        async with db.execute("PRAGMA table_info(prs)") as cursor:
            prs_columns = [row[1] for row in await cursor.fetchall()]

        # Ensure all required decision columns exist with safe defaults
        required_columns = {
            "status": "TEXT DEFAULT 'error'",
            "decision_status": "TEXT DEFAULT 'BLOCK'",
            "high_count": "INTEGER DEFAULT 0",
            "medium_count": "INTEGER DEFAULT 0",
            "low_count": "INTEGER DEFAULT 0",
            "total_chunks": "INTEGER DEFAULT 0",
            "processed_chunks": "INTEGER DEFAULT 0"
        }
        for col, definition in required_columns.items():
            if col not in prs_columns:
                await db.execute(f"ALTER TABLE prs ADD COLUMN {col} {definition}")

        # Backfill migration: ensure no NULLs exist in decision columns
        await db.execute("UPDATE prs SET decision_status = 'BLOCK' WHERE decision_status IS NULL")
        await db.execute("UPDATE prs SET high_count = 0 WHERE high_count IS NULL")
        await db.execute("UPDATE prs SET medium_count = 0 WHERE medium_count IS NULL")
        await db.execute("UPDATE prs SET low_count = 0 WHERE low_count IS NULL")

        await db.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_id INTEGER,
                severity TEXT,
                type TEXT,
                title TEXT,
                description TEXT,
                file TEXT,
                line INTEGER,
                FOREIGN KEY (pr_id) REFERENCES prs (id)
            )
        ''')
        
        # Migration: Add title column if it doesn't exist
        async with db.execute("PRAGMA table_info(issues)") as cursor:
            issues_columns = [row[1] for row in await cursor.fetchall()]
        if "title" not in issues_columns:
            await db.execute("ALTER TABLE issues ADD COLUMN title TEXT DEFAULT ''")

        await db.execute('''
            CREATE TABLE IF NOT EXISTS processed_shas (
                sha TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                updated_at TEXT
            )
        ''')

        # Step 2 Fix: Enforce dedup at DB level — in-memory sets are NOT sufficient
        await db.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_sha ON processed_shas(sha)'
        )

        # Step 3 Fix: Deduplicate existing prs rows BEFORE enforcing uniqueness.
        # Keep only the latest row (highest id) per (repo, pr_number).
        await db.execute('''
            DELETE FROM prs
            WHERE id NOT IN (
                SELECT MAX(id) FROM prs GROUP BY repo, pr_number
            )
        ''')
        await db.commit()

        # Now safe to create the unique index on a clean table
        await db.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pr ON prs(repo, pr_number)'
        )

        await db.execute('CREATE TABLE IF NOT EXISTS system_meta (key TEXT PRIMARY KEY, value TEXT)')

        # 2. Schema Migrations (Example: v2 add updated_at to processed_shas if missing)
        # In a real app, use Alembic. Here we use an internal version.
        await db.execute("INSERT OR IGNORE INTO system_meta (key, value) VALUES (?, ?)", ("schema_version", "1"))

        # 3. Initialize bot start time if not exists
        await db.execute("INSERT OR IGNORE INTO system_meta (key, value) VALUES (?, ?)",
                       ("bot_start_time", datetime.now(timezone.utc).isoformat()))

        await db.commit()
        logger.info("Database initialized (Persistent Mode)")

async def claim_sha_for_processing(sha: str) -> bool:
    """
    ATOMICALLY claims a SHA for processing. Rules:
      - completed  -> NEVER re-claim (permanent lock)
      - pending    -> re-claim only if stale (>30 min old)
      - failed     -> re-claim only if stale (>30 min old)
      - not exists -> always claim (via INSERT OR IGNORE epoch seed)
    Returns True if claimed, False if already active/completed.
    """
    async with get_db() as db:
        now        = datetime.now(timezone.utc)
        stale_time = (now - timedelta(minutes=60)).isoformat()
        now_str    = now.isoformat()

        # Seed the row so the UPDATE below has something to match on first insert
        await db.execute(
            "INSERT OR IGNORE INTO processed_shas (sha, status, updated_at) "
            "VALUES (?, 'pending', '1970-01-01T00:00:00')",
            (sha,)
        )

        # Claim only if NOT completed AND (brand-new OR stale pending/failed)
        cursor = await db.execute(
            """
            UPDATE processed_shas
            SET    status = 'pending', updated_at = ?
            WHERE  sha = ?
              AND  status != 'completed'
              AND (
                    updated_at = '1970-01-01T00:00:00'
                 OR (status IN ('pending', 'failed') AND updated_at < ?)
                  )
            """,
            (now_str, sha, stale_time)
        )

        await db.commit()
        is_claimed = cursor.rowcount > 0
        if is_claimed:
            logger.info(f"SHA {sha} atomically claimed.")
        else:
            logger.info(f"SHA {sha} rejected: completed or still active (not stale).")
        return is_claimed

async def is_sha_processed(sha: str) -> bool:
    """Checks if a SHA is successfully completed. Does NOT claim it."""
    async with get_db() as db:
        async with db.execute("SELECT status FROM processed_shas WHERE sha = ?", (sha,)) as cursor:
            row = await cursor.fetchone()
            return row and row['status'] == 'completed'

async def mark_sha_status(sha: str, status: str):
    """Marks a commit SHA with a specific status."""
    updated_at = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO processed_shas (sha, status, updated_at) VALUES (?, ?, ?)",
            (sha, status, updated_at)
        )
        await db.commit()
    logger.info(f"SHA {sha} marked as {status}")

async def record_review(repo: str, pr_number: int, issues: list, status: str = "success"):
    """
    DEPRECATED: Use initiate_review and finalize_review for observability consistency.
    Legacy wrapper for compatibility during migration.
    """
    pr_id = await initiate_review(repo, pr_number, status=status)
    await finalize_review(pr_id, issues, status=status)

async def upsert_review(repo: str, pr_number: int, status: str = "processing") -> int:
    """
    Step 3 Fix: ATOMIC UPSERT — guarantees exactly ONE row per (repo, pr_number).
    State machine: RECEIVED -> PROCESSING -> COMPLETED / FAILED.
    Never inserts duplicate rows; always updates existing ones.
    Handles legacy schema with bot_start_time NOT NULL column.
    """
    now = datetime.now(timezone.utc).isoformat()

    async def _upsert():
        async with get_db() as db:
            # Detect schema once to handle legacy bot_start_time column
            async with db.execute("PRAGMA table_info(prs)") as c:
                cols = [row[1] for row in await c.fetchall()]
            has_bot_start = "bot_start_time" in cols

            if has_bot_start:
                sql = '''
                    INSERT INTO prs (repo, pr_number, reviewed_at, bot_start_time, status)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(repo, pr_number)
                    DO UPDATE SET
                        status      = excluded.status,
                        reviewed_at = excluded.reviewed_at,
                        processed_chunks = 0,
                        total_chunks = 0
                '''
                params = (repo, pr_number, now, now, status)
            else:
                sql = '''
                    INSERT INTO prs (repo, pr_number, reviewed_at, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(repo, pr_number)
                    DO UPDATE SET
                        status      = excluded.status,
                        reviewed_at = excluded.reviewed_at,
                        processed_chunks = 0,
                        total_chunks = 0
                '''
                params = (repo, pr_number, now, status)

            await db.execute(sql, params)
            await db.commit()
            # Return the existing or newly created row id
            async with db.execute(
                "SELECT id FROM prs WHERE repo = ? AND pr_number = ?",
                (repo, pr_number)
            ) as c:
                row = await c.fetchone()
                return row[0]

    return await db_retry(_upsert)


async def initiate_review(repo: str, pr_number: int, status: str = "pending") -> int:
    """Backwards-compat shim — delegates to upsert_review."""
    return await upsert_review(repo, pr_number, status=status)

async def finalize_review(pr_id: int, issues: list, status: str = "error",
                          decision_status: str = "BLOCK", high: int = 0,
                          medium: int = 0, low: int = 0,
                          total_chunks: int = 0, processed_chunks: int = 0):
    """
    Step 3 Fix: Finalizes via UPDATE only — never inserts a new row.
    Step 4 Fix: Empty issues list with status=success → decision stays as computed
                (the compute_decision function in main.py already returns SAFE when
                issues=[] and no error; we never force BLOCK here).
    """
    async def _update():
        async with get_db() as db:
            # Explicit transaction for atomicity
            await db.execute("BEGIN IMMEDIATE")
            
            # Atomic UPDATE — single row per PR, never ghost inserts
            await db.execute(
                """UPDATE prs SET
                   status          = ?,
                   decision_status = ?,
                   high_count      = ?,
                   medium_count    = ?,
                   low_count       = ?,
                   total_chunks    = ?,
                   processed_chunks = ?
                   WHERE id        = ?""",
                (status, decision_status, high, medium, low, total_chunks, processed_chunks, pr_id)
            )

            # Delete stale issues from previous processing attempts, then re-insert
            await db.execute("DELETE FROM issues WHERE pr_id = ?", (pr_id,))
            for issue in issues:
                await db.execute(
                    "INSERT INTO issues (pr_id, severity, type, title, description, file, line) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        pr_id,
                        (issue.get("severity") or "low").lower(),
                        (issue.get("type") or "bug").lower(),
                        (issue.get("title") or "Issue Detected"),
                        (issue.get("description") or ""),
                        (issue.get("file") or ""),
                        (issue.get("line") or 0)
                    )
                )
            await db.commit()

    await db_retry(_update)
    logger.info(
        f"📈 Telemetry Finalized: PR ID {pr_id} | Status: {status} "
        f"| Decision: {decision_status} | Issues: H={high} M={medium} L={low}"
    )

async def update_review_progress(pr_id: int, processed: int, total: int):
    """Updates the progress counts for a PR without finalizing it."""
    async def _update():
        async with get_db() as db:
            await db.execute(
                "UPDATE prs SET processed_chunks = ?, total_chunks = ? WHERE id = ?",
                (processed, total, pr_id)
            )
            await db.commit()
    await db_retry(_update)

async def get_stats(limit: int = 15, offset: int = 0) -> dict:
    """Aggregates telemetry with pagination."""
    async with get_db() as db:
        # Atomic read transaction to prevent dirty reads and UI flickering
        await db.execute("BEGIN")
        
        # Counts
        async with db.execute("SELECT COUNT(*) FROM prs") as c: total_prs = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM issues") as c: total_issues = (await c.fetchone())[0]

        # Breakdown (Filtered by successful PRs to prevent contamination)
        async with db.execute("SELECT severity, COUNT(*) as count FROM issues WHERE pr_id IN (SELECT id FROM prs WHERE status='success') GROUP BY severity") as c:
            sev_data = {row['severity']: row['count'] for row in await c.fetchall()}

        async with db.execute("SELECT type, COUNT(*) as count FROM issues WHERE pr_id IN (SELECT id FROM prs WHERE status='success') GROUP BY type") as c:
            type_data = {row['type']: row['count'] for row in await c.fetchall()}

        # Recent (Paginated)
        async with db.execute("SELECT * FROM prs ORDER BY reviewed_at DESC LIMIT ? OFFSET ?", (limit, offset)) as c:
            prs = await c.fetchall()

        recent_reviews = []
        for pr_row in prs:
            pr = dict(pr_row)
            pr_status = pr.get("status", "error")
            decision = pr.get("decision_status", "BLOCK")

            async with db.execute("SELECT * FROM issues WHERE pr_id = ?", (pr['id'],)) as c:
                issues = [dict(row) for row in await c.fetchall()]

            recent_reviews.append({
                "repo": pr['repo'],
                "pr_number": pr['pr_number'],
                "status": pr_status,
                "decision": decision,
                "issue_count": len(issues),
                "reviewed_at": pr['reviewed_at'],
                "issues": issues,
                "coverage": {
                    "processed": pr.get('processed_chunks', 0),
                    "total": pr.get('total_chunks', 0)
                },
                "severities": {
                    "high": pr.get('high_count', 0),
                    "medium": pr.get('medium_count', 0),
                    "low": pr.get('low_count', 0),
                }
            })

        # Meta
        async with db.execute("SELECT value FROM system_meta WHERE key = 'bot_start_time'") as c:
            row = await c.fetchone()
            bot_start_time = row[0] if row else datetime.now(timezone.utc).isoformat()

        uptime_seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(bot_start_time)).total_seconds()
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, _ = divmod(remainder, 60)

        async with db.execute("SELECT reviewed_at FROM prs ORDER BY reviewed_at DESC LIMIT 1") as c:
            last_row = await c.fetchone()
            last_review_time = last_row[0] if last_row else None
            
        await db.commit()

    return {
        "total_prs": total_prs,
        "total_issues": total_issues,
        "issues_by_severity": {"high": sev_data.get("high", 0), "medium": sev_data.get("medium", 0), "low": sev_data.get("low", 0)},
        "issues_by_type": {"security": type_data.get("security", 0), "bug": type_data.get("bug", 0), "performance": type_data.get("performance", 0), "quality": type_data.get("quality", 0)},
        "recent_reviews": recent_reviews,
        "bot_status": "online",
        "uptime": f"{hours}h {minutes}m",
        "last_review_time": last_review_time
    }

async def get_issues_for_pr(pr_number: int) -> list:
    """Retrieves all issues associated with a specific PR number."""
    async with get_db() as db:
        async with db.execute("""
            SELECT i.* FROM issues i
            JOIN prs p ON i.pr_id = p.id
            WHERE p.pr_number = ?
        """, (pr_number,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
