import aiosqlite
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

    # Atomic Claim: Update only if (not exists OR failed OR stale pending)
    # We first try to inserted a fresh pending if it doesn't exist
    await db.execute("INSERT OR IGNORE INTO processed_shas (sha, status, updated_at) VALUES (?, 'pending', ?)",
                    (sha, "1970-01-01T00:00:00")) # Seed old so it fails next check if just inserted

    # Now try to atomically switch to 'pending' from 'failed' or 'stale'
    # Or if it was just inserted above, it will be switched to 'pending' with current TS
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

    async def _insert():
        cursor = await db.execute(
            "INSERT INTO prs (repo, pr_number, reviewed_at, status) VALUES (?, ?, ?, ?)",
            (repo, pr_number, reviewed_at, status)
        )
        await db.commit()
        return cursor.lastrowid

    return await db_retry(_insert)

async def finalize_review(pr_id: int, issues: list, status: str = "success"):
    """Finalizes an existing review record with results and actual issues."""
    db = await get_db()

    async def _update():
        # 1. Update PR status
        await db.execute(
            "UPDATE prs SET status = ? WHERE id = ?",
            (status, pr_id)
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
    logger.info(f"📈 Telemetry Finalized: PR ID {pr_id} Status: {status}")

async def get_stats(limit: int = 15, offset: int = 0) -> dict:
    """Aggregates telemetry with pagination."""
    db = await get_db()

    # Counts
    async with db.execute("SELECT COUNT(*) FROM prs") as c: total_prs = (await c.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM issues") as c: total_issues = (await c.fetchone())[0]

    # Breakdown
    async with db.execute("SELECT severity, COUNT(*) as count FROM issues GROUP BY severity") as c:
        sev_data = {row['severity']: row['count'] for row in await c.fetchall()}

    async with db.execute("SELECT type, COUNT(*) as count FROM issues GROUP BY type") as c:
        type_data = {row['type']: row['count'] for row in await c.fetchall()}

    # Recent (Paginated)
    async with db.execute("SELECT * FROM prs ORDER BY reviewed_at DESC LIMIT ? OFFSET ?", (limit, offset)) as c:
        prs = await c.fetchall()

    recent_reviews = []
    for pr in prs:
        async with db.execute("SELECT * FROM issues WHERE pr_id = ?", (pr['id'],)) as c:
            issues = [dict(row) for row in await c.fetchall()]

        recent_reviews.append({
            "repo": pr['repo'],
            "pr_number": pr['pr_number'],
            "status": pr['status'],
            "issue_count": len(issues),
            "reviewed_at": datetime.fromisoformat(pr['reviewed_at']).strftime("%H:%M:%S"),
            "issues": issues,
            "severities": {
                "high": sum(1 for i in issues if i['severity'] == "high"),
                "medium": sum(1 for i in issues if i['severity'] == "medium"),
                "low": sum(1 for i in issues if i['severity'] == "low"),
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
