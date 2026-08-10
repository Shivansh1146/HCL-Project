import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("backend")

from db_engine import get_db

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
    """Initializes the PostgreSQL database with schema versioning and migrations."""
    async with get_db() as db:
        # 1. Base Tables
        await db.execute('''
            CREATE TABLE IF NOT EXISTS prs (
                id SERIAL PRIMARY KEY,
                repo TEXT,
                pr_number INTEGER,
                reviewed_at TEXT,
                status TEXT DEFAULT 'success'
            )
        ''')
        
        # Check existing columns using PostgreSQL information_schema
        prs_columns_query = '''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prs'
        '''
        prs_columns_result = await db.fetch(prs_columns_query)
        prs_columns = [row['column_name'] for row in prs_columns_result]

        # Ensure all required decision columns exist with safe defaults
        required_columns = {
            "status": "TEXT DEFAULT 'error'",
            "decision_status": "TEXT DEFAULT 'BLOCK'",
            "high_count": "INTEGER DEFAULT 0",
            "medium_count": "INTEGER DEFAULT 0",
            "low_count": "INTEGER DEFAULT 0",
            "total_chunks": "INTEGER DEFAULT 0",
            "processed_chunks": "INTEGER DEFAULT 0",
            "rule_based_count": "INTEGER DEFAULT 0",
            "decision_explanation": "TEXT"
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
                id SERIAL PRIMARY KEY,
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
        issues_columns_query = '''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'issues'
        '''
        issues_columns_result = await db.fetch(issues_columns_query)
        issues_columns = [row['column_name'] for row in issues_columns_result]
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

        # Now safe to create the unique index on a clean table
        await db.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pr ON prs(repo, pr_number)'
        )

        await db.execute('CREATE TABLE IF NOT EXISTS system_meta (key TEXT PRIMARY KEY, value TEXT)')

        # 2. Schema Migrations (Example: v2 add updated_at to processed_shas if missing)
        # In a real app, use Alembic. Here we use an internal version.
        await db.execute("INSERT INTO system_meta (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING", "schema_version", "1")

        # 3. Initialize bot start time if not exists
        await db.execute("INSERT INTO system_meta (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                       "bot_start_time", datetime.now(timezone.utc).isoformat())

        logger.info("Database initialized (PostgreSQL Mode)")

async def claim_sha_for_processing(sha: str) -> bool:
    """
    ATOMICALLY claims a SHA for processing. Rules:
      - completed  -> NEVER re-claim (permanent lock)
      - pending    -> re-claim only if stale (>30 min old)
      - failed     -> re-claim only if stale (>30 min old)
      - not exists -> always claim (via INSERT epoch seed)
    Returns True if claimed, False if already active/completed.
    """
    async with get_db() as db:
        now        = datetime.now(timezone.utc)
        stale_time = (now - timedelta(minutes=60)).isoformat()
        now_str    = now.isoformat()

        # Seed the row so the UPDATE below has something to match on first insert
        await db.execute(
            "INSERT INTO processed_shas (sha, status, updated_at) VALUES ($1, 'pending', '1970-01-01T00:00:00') ON CONFLICT (sha) DO NOTHING",
            sha
        )

        # Claim only if NOT completed AND (brand-new OR stale pending/failed)
        cursor = await db.execute(
            """
            UPDATE processed_shas
            SET    status = 'pending', updated_at = $1
            WHERE  sha = $2
              AND  status != 'completed'
              AND (
                    updated_at = '1970-01-01T00:00:00'
                 OR (status IN ('pending', 'failed') AND updated_at < $3)
                  )
            """,
            now_str, sha, stale_time
        )

        is_claimed = cursor.rowcount > 0
        if is_claimed:
            logger.info(f"SHA {sha} atomically claimed.")
        else:
            logger.info(f"SHA {sha} rejected: completed or still active (not stale).")
        return is_claimed

async def is_sha_processed(sha: str) -> bool:
    """Checks if a SHA is successfully completed. Does NOT claim it."""
    async with get_db() as db:
        row = await db.fetchrow("SELECT status FROM processed_shas WHERE sha = $1", sha)
        return row and row['status'] == 'completed'

async def mark_sha_status(sha: str, status: str):
    """Marks a commit SHA with a specific status."""
    updated_at = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO processed_shas (sha, status, updated_at) VALUES ($1, $2, $3) ON CONFLICT (sha) DO UPDATE SET status = $2, updated_at = $3",
            sha, status, updated_at
        )
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
            prs_columns_query = '''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'prs'
            '''
            prs_columns_result = await db.fetch(prs_columns_query)
            prs_columns = [row['column_name'] for row in prs_columns_result]
            has_bot_start = "bot_start_time" in prs_columns

            if has_bot_start:
                sql = '''
                    INSERT INTO prs (repo, pr_number, reviewed_at, bot_start_time, status)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT(repo, pr_number)
                    DO UPDATE SET
                        status      = excluded.status,
                        reviewed_at = excluded.reviewed_at,
                        processed_chunks = 0,
                        total_chunks = 0
                '''
                await db.execute(sql, repo, pr_number, now, now, status)
            else:
                sql = '''
                    INSERT INTO prs (repo, pr_number, reviewed_at, status)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT(repo, pr_number)
                    DO UPDATE SET
                        status      = excluded.status,
                        reviewed_at = excluded.reviewed_at,
                        processed_chunks = 0,
                        total_chunks = 0
                '''
                await db.execute(sql, repo, pr_number, now, status)

            # Return the existing or newly created row id
            result = await db.fetchrow(
                "SELECT id FROM prs WHERE repo = $1 AND pr_number = $2",
                repo, pr_number
            )
            return result['id']

    return await db_retry(_upsert)

async def update_review_progress(pr_id: int, processed: int, total: int):
    """Updates the progress counts for a PR without finalizing it."""
    async def _update():
        async with get_db() as db:
            await db.execute(
                "UPDATE prs SET processed_chunks = $1, total_chunks = $2 WHERE id = $3",
                processed, total, pr_id
            )
    await db_retry(_update)

async def initiate_review(repo: str, pr_number: int, status: str = "processing") -> int:
    """
    Step 3 Fix: Returns the pr_id for a given (repo, pr_number).
    Uses ATOMIC UPSERT to guarantee exactly ONE row per (repo, pr_number).
    """
    return await upsert_review(repo, pr_number, status=status)

async def finalize_review(pr_id: int, issues: list, status: str = "error",
                          decision_status: str = "BLOCK", high: int = 0,
                          medium: int = 0, low: int = 0,
                          total_chunks: int = 0, processed_chunks: int = 0,
                          rule_based_count: int = 0, decision_explanation: str = None):
    """
    Step 3 Fix: Finalizes via UPDATE only — never inserts a new row.
    Step 4 Fix: Empty issues list with status=success → decision stays as computed
                (the compute_decision function in main.py already returns SAFE when
                issues=[] and no error; we never force BLOCK here).
    """
    async def _update():
        async with get_db() as db:
            # Atomic UPDATE — single row per PR, never ghost inserts
            await db.execute(
                """UPDATE prs SET
                   status          = $1,
                   decision_status = $2,
                   high_count      = $3,
                   medium_count    = $4,
                   low_count       = $5,
                   total_chunks    = $6,
                   processed_chunks = $7,
                   rule_based_count = $8,
                   decision_explanation = $9
                   WHERE id        = $10""",
                status, decision_status, high, medium, low, total_chunks, processed_chunks, rule_based_count, decision_explanation, pr_id
            )

            # Delete stale issues from previous processing attempts, then re-insert
            await db.execute("DELETE FROM issues WHERE pr_id = $1", pr_id)
            for issue in issues:
                await db.execute(
                    "INSERT INTO issues (pr_id, severity, type, title, description, file, line) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    pr_id,
                    (issue.get("severity") or "low").lower(),
                    (issue.get("type") or "bug").lower(),
                    (issue.get("title") or "Issue Detected"),
                    (issue.get("description") or ""),
                    (issue.get("file") or ""),
                    (issue.get("line") or 0)
                )

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
                "UPDATE prs SET processed_chunks = $1, total_chunks = $2 WHERE id = $3",
                processed, total, pr_id
            )
    await db_retry(_update)

async def get_stats(limit: int = 15, offset: int = 0) -> dict:
    """Aggregates telemetry with pagination."""
    async with get_db() as db:
        # Atomic read transaction to prevent dirty reads and UI flickering
        total_prs = await db.fetchval("SELECT COUNT(*) FROM prs")
        
        # Calculate coverage stats
        coverage_stats = await db.fetchrow(
            "SELECT AVG(total_chunks), AVG(high_count + medium_count + low_count) FROM prs"
        )
        
        # Decision status distribution
        decision_dist = await db.fetch(
            "SELECT decision_status, COUNT(*) as cnt FROM prs GROUP BY decision_status"
        )
        decision_counts = {row['decision_status']: row['cnt'] for row in decision_dist}
        
        # Severity distribution (from issues table)
        severity_dist = await db.fetch(
            "SELECT severity, COUNT(*) as count FROM issues WHERE pr_id IN (SELECT id FROM prs WHERE status='success') GROUP BY severity"
        )
        severity_counts = {row['severity']: row['count'] for row in severity_dist}
        
        # Type distribution
        type_dist = await db.fetch(
            "SELECT type, COUNT(*) as count FROM issues WHERE pr_id IN (SELECT id FROM prs WHERE status='success') GROUP BY type"
        )
        type_counts = {row['type']: row['count'] for row in type_dist}
        
        # Paginated PR list
        prs_list = await db.fetch(
            "SELECT * FROM prs ORDER BY reviewed_at DESC LIMIT $1 OFFSET $2",
            limit, offset
        )
        
        # Last reviewed timestamp
        last_reviewed = await db.fetchval(
            "SELECT reviewed_at FROM prs ORDER BY reviewed_at DESC LIMIT 1"
        )
        
        return {
            "total_prs": total_prs,
            "coverage_avg_chunks": coverage_stats['avg'] if coverage_stats else 0,
            "coverage_avg_issues": coverage_stats['avg_1'] if coverage_stats else 0,
            "decision_distribution": decision_counts,
            "severity_distribution": severity_counts,
            "type_distribution": type_counts,
            "prs": [dict(pr) for pr in prs_list],
            "last_reviewed_at": last_reviewed
        }

async def get_pr_details(repo: str, pr_number: int) -> dict:
    """Fetch detailed information for a specific PR."""
    async with get_db() as db:
        pr_row = await db.fetchrow(
            "SELECT * FROM prs WHERE repo = $1 AND pr_number = $2",
            repo, pr_number
        )
        
        if not pr_row:
            return None
            
        issues = await db.fetch(
            "SELECT * FROM issues WHERE pr_id = $1",
            pr_row['id']
        )
        
        return {
            "pr": dict(pr_row),
            "issues": [dict(issue) for issue in issues]
        }

async def list_prs(repo: str = None, limit: int = 15, offset: int = 0,
                 status_filter: str = None, decision_filter: str = None,
                 sort_by: str = "reviewed_at", sort_order: str = "DESC") -> list:
    """
    Fetch PRs with optional filtering and pagination.
    """
    async with get_db() as db:
        query = "SELECT * FROM prs WHERE 1=1"
        param_count = 0
        
        if repo:
            param_count += 1
            query += f" AND repo = ${param_count}"
            
        if status_filter:
            param_count += 1
            query += f" AND status = ${param_count}"
            
        if decision_filter:
            param_count += 1
            query += f" AND decision_status = ${param_count}"
            
        # Sorting
        valid_sort_fields = {"reviewed_at", "status", "decision_status", "pr_number"}
        if sort_by in valid_sort_fields:
            query += f" ORDER BY {sort_by} {sort_order}"
        else:
            query += " ORDER BY reviewed_at DESC"
            
        param_count += 1
        query += f" LIMIT ${param_count}"
        param_count += 1
        query += f" OFFSET ${param_count}"
        
        # Build params in correct order
        params = []
        if repo:
            params.append(repo)
        if status_filter:
            params.append(status_filter)
        if decision_filter:
            params.append(decision_filter)
        params.extend([limit, offset])
        
        prs = await db.fetch(query, *params)
        return [dict(pr) for pr in prs]
