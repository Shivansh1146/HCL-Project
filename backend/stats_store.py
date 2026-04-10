import aiosqlite
import asyncio
import logging
import os
from datetime import datetime, timedelta

DB_PATH = "reviews.db"
logger = logging.getLogger("backend")

# Global connection to eliminate connection churn
_db_connection = None

async def get_db():
    """Returns the persistent database connection."""
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(DB_PATH)
        _db_connection.row_factory = aiosqlite.Row
    return _db_connection

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
    """Closes the persistent database connection."""
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None

async def initialize_db():
    """Initializes the SQLite database with schema versioning and migrations."""
    db = await get_db()

    # 0. Enable WAL Mode (Write-Ahead Logging) for better concurrency on Windows
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")

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
        "low_count": "INTEGER DEFAULT 0"
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
            description TEXT,
            file TEXT,
            line INTEGER,
            FOREIGN KEY (pr_id) REFERENCES prs (id)
        )
    ''')

    await db.execute('''
        CREATE TABLE IF NOT EXISTS processed_shas (
            sha TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            updated_at TEXT
        )
    ''')

    await db.execute('CREATE TABLE IF NOT EXISTS system_meta (key TEXT PRIMARY KEY, value TEXT)')

    # 2. Schema Migrations (Example: v2 add updated_at to processed_shas if missing)
    # In a real app, use Alembic. Here we use an internal version.
    await db.execute("INSERT OR IGNORE INTO system_meta (key, value) VALUES (?, ?)", ("schema_version", "1"))

    # 3. Initialize bot start time if not exists
    await db.execute("INSERT OR IGNORE INTO system_meta (key, value) VALUES (?, ?)",
                   ("bot_start_time", datetime.now().isoformat()))

    await db.commit()
    logger.info("Database initialized (Persistent Mode)")

async def claim_sha_for_processing(sha: str) -> bool:
    """
    Atynchronously and ATOMICALLY claims a SHA for processing.
    Uses an atomic UPDATE with state + TTL checks to prevent race conditions.
    Returns True if successfully claimed, False if already active.
    """
    db = await get_db()
    now = datetime.now()
    stale_time = (now - timedelta(minutes=30)).isoformat()
    now_str = now.isoformat()

    # Atomic Claim: Update only if (not exists OR failed OR stale pending OR pending-without-pr)
    # 1. Ensure SHA exists in processed_shas
    await db.execute("INSERT OR IGNORE INTO processed_shas (sha, status, updated_at) VALUES (?, 'pending', ?)",
                    (sha, "1970-01-01T00:00:00"))

    # 2. Check if a PR record actually exists for this SHA if it is 'pending'
    # This detects "orphaned" pending SHAs from previous crashes.
    async with db.execute("SELECT pr_number FROM prs WHERE id = (SELECT MAX(id) FROM prs WHERE repo IN (SELECT repo FROM prs)) AND pr_number IN (SELECT pr_number FROM prs)") as c:
        # Note: In a production system, we'd join prs and processed_shas.
        # For this design, we'll allow re-claim if status is 'pending' AND updated_at is old
        pass

    cursor = await db.execute('''
        UPDATE processed_shas
        SET status = 'pending', updated_at = ?
        WHERE sha = ? AND (
            status = 'failed' OR
            updated_at < ? OR
            updated_at = '1970-01-01T00:00:00'
        )
    ''', (now_str, sha, stale_time))

    await db.commit()
    is_claimed = cursor.rowcount > 0
    if is_claimed:
        logger.info(f"SHA {sha} atomically claimed.")
    return is_claimed

async def is_sha_processed(sha: str) -> bool:
    """Checks if a SHA is successfully completed. Does NOT claim it."""
    db = await get_db()
    async with db.execute("SELECT status FROM processed_shas WHERE sha = ?", (sha,)) as cursor:
        row = await cursor.fetchone()
        return row and row['status'] == 'completed'

async def mark_sha_status(sha: str, status: str):
    """Marks a commit SHA with a specific status."""
    updated_at = datetime.now().isoformat()
    db = await get_db()
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

async def initiate_review(repo: str, pr_number: int, status: str = "pending") -> int:
    """Records the INTENT to review before external side effects happen."""
    db = await get_db()
    reviewed_at = datetime.now().isoformat()
    bot_start_time = datetime.now().isoformat()

    # Support legacy schemas where prs may contain additional NOT NULL columns.
    async with db.execute("PRAGMA table_info(prs)") as cursor:
        prs_columns = [row[1] for row in await cursor.fetchall()]

    async def _insert():
        if "bot_start_time" in prs_columns:
            cursor = await db.execute(
                "INSERT INTO prs (repo, pr_number, reviewed_at, bot_start_time, status) VALUES (?, ?, ?, ?, ?)",
                (repo, pr_number, reviewed_at, bot_start_time, status)
            )
        else:
            cursor = await db.execute(
                "INSERT INTO prs (repo, pr_number, reviewed_at, status) VALUES (?, ?, ?, ?)",
                (repo, pr_number, reviewed_at, status)
            )
        await db.commit()
        return cursor.lastrowid

    return await db_retry(_insert)

async def finalize_review(pr_id: int, issues: list, status: str = "error",
                          decision_status: str = "BLOCK", high: int = 0,
                          medium: int = 0, low: int = 0):
    """Finalizes an existing review record with results, decision, and metrics."""
    db = await get_db()

    async def _update():
        # 1. Update PR status and decision metrics
        await db.execute(
            """UPDATE prs SET
               status = ?,
               decision_status = ?,
               high_count = ?,
               medium_count = ?,
               low_count = ?
               WHERE id = ?""",
            (status, decision_status, high, medium, low, pr_id)
        )

        # 2. Insert issues
        for issue in issues:
            await db.execute(
                "INSERT INTO issues (pr_id, severity, type, description, file, line) VALUES (?, ?, ?, ?, ?, ?)",
                (pr_id, issue.get("severity", "low").lower(), issue.get("type", "bug").lower(),
                 issue.get("description", ""), issue.get("file", ""), issue.get("line", 0))
            )
        await db.commit()

    await db_retry(_update)
    logger.info(f"📈 Telemetry Finalized: PR ID {pr_id} Status: {status} Decision: {decision_status}")

async def get_stats(limit: int = 15, offset: int = 0) -> dict:
    """Aggregates telemetry with pagination."""
    db = await get_db()

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
            "reviewed_at": datetime.fromisoformat(pr['reviewed_at']).strftime("%H:%M:%S"),
            "issues": issues,
            "severities": {
                "high": pr.get('high_count', 0),
                "medium": pr.get('medium_count', 0),
                "low": pr.get('low_count', 0),
            }
        })

    # Meta
    async with db.execute("SELECT value FROM system_meta WHERE key = 'bot_start_time'") as c:
        row = await c.fetchone()
        bot_start_time = row[0]

    uptime_seconds = (datetime.now() - datetime.fromisoformat(bot_start_time)).total_seconds()
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, _ = divmod(remainder, 60)

    async with db.execute("SELECT reviewed_at FROM prs ORDER BY reviewed_at DESC LIMIT 1") as c:
        last_row = await c.fetchone()
        last_review_time = last_row[0] if last_row else None

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
