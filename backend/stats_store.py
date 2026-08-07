import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("backend")

from db_engine import close_db_engine, get_db, init_db_engine


async def db_retry(func, *args, retries=3, delay=1, **kwargs):
    """Wrapper to retry database operations on failure."""
    for attempt in range(retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                logger.error(
                    f"Database operation failed after {retries} attempts: {str(e)}"
                )
                raise
            await asyncio.sleep(delay * (attempt + 1))


async def close_db():
    """No-op for backward compatibility."""
    pass


async def initialize_db():
    """Initializes the SQLite database with schema versioning and migrations."""
    async with get_db() as db:
        # 1. Base Tables
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS prs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT,
                pr_number INTEGER,
                reviewed_at TEXT,
                status TEXT DEFAULT 'success'
            )
        """
        )
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
            "processed_chunks": "INTEGER DEFAULT 0",
            "rule_based_count": "INTEGER DEFAULT 0",
            "decision_explanation": "TEXT",
        }
        for col, definition in required_columns.items():
            if col not in prs_columns:
                await db.execute(f"ALTER TABLE prs ADD COLUMN {col} {definition}")

        # Backfill migration: ensure no NULLs exist in decision columns
        await db.execute(
            "UPDATE prs SET decision_status = 'BLOCK' WHERE decision_status IS NULL"
        )
        await db.execute("UPDATE prs SET high_count = 0 WHERE high_count IS NULL")
        await db.execute("UPDATE prs SET medium_count = 0 WHERE medium_count IS NULL")
        await db.execute("UPDATE prs SET low_count = 0 WHERE low_count IS NULL")

        await db.execute(
            """
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
        """
        )

        # Migration: Add title column if it doesn't exist
        async with db.execute("PRAGMA table_info(issues)") as cursor:
            issues_columns = [row[1] for row in await cursor.fetchall()]
        if "title" not in issues_columns:
            await db.execute("ALTER TABLE issues ADD COLUMN title TEXT DEFAULT ''")

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_shas (
                sha TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                updated_at TEXT
            )
        """
        )

        # Step 2 Fix: Enforce dedup at DB level — in-memory sets are NOT sufficient
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_sha ON processed_shas(sha)"
        )

        # Step 3 Fix: Deduplicate existing prs rows BEFORE enforcing uniqueness.
        # Keep only the latest row (highest id) per (repo, pr_number).
        await db.execute(
            """
            DELETE FROM prs
            WHERE id NOT IN (
                SELECT MAX(id) FROM prs GROUP BY repo, pr_number
            )
        """
        )
        await db.commit()

        # Now safe to create the unique index on a clean table
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pr ON prs(repo, pr_number)"
        )

        await db.execute(
            "CREATE TABLE IF NOT EXISTS system_meta (key TEXT PRIMARY KEY, value TEXT)"
        )

        # 2. Schema Migrations (Example: v2 add updated_at to processed_shas if missing)
        # In a real app, use Alembic. Here we use an internal version.
        await db.execute(
            "INSERT OR IGNORE INTO system_meta (key, value) VALUES (?, ?)",
            ("schema_version", "1"),
        )

        # 3. Initialize bot start time if not exists
        await db.execute(
            "INSERT OR IGNORE INTO system_meta (key, value) VALUES (?, ?)",
            ("bot_start_time", datetime.now(timezone.utc).isoformat()),
        )

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
        now = datetime.now(timezone.utc)
        stale_time = (now - timedelta(minutes=60)).isoformat()
        now_str = now.isoformat()

        # Seed the row so the UPDATE below has something to match on first insert
        await db.execute(
            "INSERT OR IGNORE INTO processed_shas (sha, status, updated_at) "
            "VALUES (?, 'pending', '1970-01-01T00:00:00')",
            (sha,),
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
            (now_str, sha, stale_time),
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
        async with db.execute(
            "SELECT status FROM processed_shas WHERE sha = ?", (sha,)
        ) as cursor:
            row = await cursor.fetchone()
            return row and row["status"] == "completed"


async def mark_sha_status(sha: str, status: str):
    """Marks a commit SHA with a specific status."""
    updated_at = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO processed_shas (sha, status, updated_at) VALUES (?, ?, ?)",
            (sha, status, updated_at),
        )
        await db.commit()
    logger.info(f"SHA {sha} marked as {status}")


async def record_review(
    repo: str, pr_number: int, issues: list, status: str = "success"
):
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
    
    NOTE: This function is deprecated. PR data is now stored in pull_requests table
    via auth/store.py. This is kept for backward compatibility only.
    """
    # Return a dummy ID since we're not using prs table anymore
    # The actual PR data is in pull_requests table
    return 0


async def initiate_review(repo: str, pr_number: int, status: str = "pending") -> int:
    """Backwards-compat shim — delegates to upsert_review."""
    return await upsert_review(repo, pr_number, status=status)


async def finalize_review(
    pr_id: int,
    issues: list,
    status: str = "error",
    decision_status: str = "BLOCK",
    high: int = 0,
    medium: int = 0,
    low: int = 0,
    total_chunks: int = 0,
    processed_chunks: int = 0,
    rule_based_count: int = 0,
    decision_explanation: str = None,
):
    """
    Step 3 Fix: Finalizes via UPDATE only — never inserts a new row.
    Step 4 Fix: Empty issues list with status=success → decision stays as computed
                (the compute_decision function in main.py already returns SAFE when
                issues=[] and no error; we never force BLOCK here).
    
    NOTE: This function is deprecated. PR data is now stored in pull_requests table
    via auth/store.py. This is kept for backward compatibility only.
    """
    # No-op since we're not using prs table anymore
    return


async def update_review_progress(pr_id: int, processed: int, total: int):
    """Updates the progress counts for a PR without finalizing it.
    
    NOTE: This function is deprecated. PR data is now stored in pull_requests table
    via auth/store.py. This is kept for backward compatibility only.
    """
    # No-op since we're not using prs table anymore
    return


async def get_stats(limit: int = 15, offset: int = 0) -> dict:
    """Aggregates telemetry with pagination."""
    async with get_db() as db:
        # Atomic read transaction to prevent dirty reads and UI flickering
        await db.execute("BEGIN")

        # Counts from pull_requests table (the actual source of truth for AI reviews)
        async with db.execute("SELECT COUNT(*) FROM pull_requests") as c:
            total_prs = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM issues") as c:
            total_issues = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM selected_repos WHERE enabled = 1"
        ) as c:
            selected_repos_count = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM repositories WHERE disabled = 0"
        ) as c:
            monitored_repositories_count = (await c.fetchone())[0]

        # Breakdown from pull_requests table columns (not issues table)
        async with db.execute(
            "SELECT SUM(high_count) as high, SUM(medium_count) as medium, SUM(low_count) as low FROM pull_requests WHERE review_status='success'"
        ) as c:
            row = await c.fetchone()
            sev_data = {
                "high": row["high"] or 0,
                "medium": row["medium"] or 0,
                "low": row["low"] or 0
            }

        # Type breakdown - default to 0 since type is not stored in pull_requests
        type_data = {"security": 0, "bug": 0, "performance": 0, "quality": 0}

        # Recent (Paginated) from pull_requests table
        async with db.execute(
            "SELECT * FROM pull_requests ORDER BY reviewed_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as c:
            prs = await c.fetchall()

        recent_reviews = []
        for pr_row in prs:
            pr = dict(pr_row)
            pr_status = pr.get("review_status", "error")
            decision = pr.get("decision", "BLOCK")

            # Try to get issues from issues table if they exist
            async with db.execute(
                "SELECT * FROM issues WHERE pr_id = ?", (pr["id"],)
            ) as c:
                issues = [dict(row) for row in await c.fetchall()]

            recent_reviews.append(
                {
                    "repo": pr["repository_name"],
                    "pr_number": pr["number"],
                    "status": pr_status,
                    "decision": decision,
                    "issue_count": len(issues) if issues else pr.get("issues_count", 0),
                    "reviewed_at": pr["reviewed_at"],
                    "issues": issues,
                    "coverage": {
                        "processed": pr.get("processed_chunks", 0),
                        "total": pr.get("total_chunks", 0),
                    },
                    "severities": {
                        "high": pr.get("high_count", 0),
                        "medium": pr.get("medium_count", 0),
                        "low": pr.get("low_count", 0),
                    },
                    "rule_based_count": pr.get("rule_based_count", 0),
                    "decision_explanation": pr.get("decision_explanation"),
                }
            )

        # Meta
        async with db.execute(
            "SELECT value FROM system_meta WHERE key = 'bot_start_time'"
        ) as c:
            row = await c.fetchone()
            bot_start_time = row[0] if row else datetime.now(timezone.utc).isoformat()

        uptime_seconds = (
            datetime.now(timezone.utc) - datetime.fromisoformat(bot_start_time)
        ).total_seconds()
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, _ = divmod(remainder, 60)

        async with db.execute(
            "SELECT reviewed_at FROM pull_requests ORDER BY reviewed_at DESC LIMIT 1"
        ) as c:
            last_row = await c.fetchone()
            last_review_time = last_row[0] if last_row else None

        await db.commit()

    logger.info(
        "Dashboard stats: selected_repos=%d monitored_repos=%d total_reviews=%d",
        selected_repos_count,
        monitored_repositories_count,
        total_prs,
    )

    return {
        "total_prs": total_prs,
        "total_reviews": total_prs,
        "total_issues": total_issues,
        "selected_repos_count": selected_repos_count,
        "monitored_repositories_count": monitored_repositories_count,
        "repositories_count": monitored_repositories_count,
        "issues_by_severity": sev_data,
        "issues_by_type": type_data,
        "recent_reviews": recent_reviews,
        "bot_status": "online",
        "uptime": f"{hours}h {minutes}m",
        "last_review_time": last_review_time,
    }


async def get_issues_for_pr(pr_number: int) -> list:
    """Retrieves all issues associated with a specific PR number."""
    async with get_db() as db:
        async with db.execute(
            """
            SELECT i.* FROM issues i
            JOIN prs p ON i.pr_id = p.id
            WHERE p.pr_number = ?
        """,
            (pr_number,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_pr_details(repo: str, pr_number: int) -> dict:
    """Fetches detailed PR telemetry, decision status, and issues list."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM prs WHERE repo = ? AND pr_number = ?", (repo, pr_number)
        ) as cursor:
            pr_row = await cursor.fetchone()
            if not pr_row:
                return None

            pr = dict(pr_row)
            async with db.execute(
                "SELECT * FROM issues WHERE pr_id = ?", (pr["id"],)
            ) as c:
                issues = [dict(row) for row in await c.fetchall()]

            return {
                "id": pr["id"],
                "repo": pr["repo"],
                "pr_number": pr["pr_number"],
                "status": pr.get("status", "error"),
                "decision": pr.get("decision_status", "BLOCK"),
                "reviewed_at": pr["reviewed_at"],
                "high_count": pr.get("high_count", 0),
                "medium_count": pr.get("medium_count", 0),
                "low_count": pr.get("low_count", 0),
                "rule_based_count": pr.get("rule_based_count", 0),
                "decision_explanation": pr.get("decision_explanation"),
                "coverage": {
                    "processed": pr.get("processed_chunks", 0),
                    "total": pr.get("total_chunks", 0),
                },
                "issues": issues,
            }


async def list_prs(
    repo: str = None, status_filter: str = None, limit: int = 50, offset: int = 0
) -> dict:
    """Returns paginated list of PR reviews with filters."""
    async with get_db() as db:
        query = "SELECT * FROM prs WHERE 1=1"
        params = []

        if repo:
            query += " AND repo = ?"
            params.append(repo)
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY reviewed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            prs = []
            for r in rows:
                pr = dict(r)
                async with db.execute(
                    "SELECT COUNT(*) FROM issues WHERE pr_id = ?", (pr["id"],)
                ) as c:
                    issue_count = (await c.fetchone())[0]

                prs.append(
                    {
                        "id": pr["id"],
                        "repo": pr["repo"],
                        "pr_number": pr["pr_number"],
                        "status": pr.get("status", "error"),
                        "decision": pr.get("decision_status", "BLOCK"),
                        "reviewed_at": pr["reviewed_at"],
                        "issue_count": issue_count,
                        "severities": {
                            "high": pr.get("high_count", 0),
                            "medium": pr.get("medium_count", 0),
                            "low": pr.get("low_count", 0),
                        },
                        "decision_explanation": pr.get("decision_explanation"),
                    }
                )

        return {"total": len(prs), "prs": prs}
