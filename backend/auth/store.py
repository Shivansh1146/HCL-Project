"""
auth/store.py — Async persistence layer for OAuth and GitHub App models.

Uses db_engine.get_db() which transparently handles both SQLite (development)
and PostgreSQL (production) — same aiosqlite-compatible cursor API in both cases.
"""

import base64
import json
import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from db_engine import get_db

from auth.models import (
    User,
    OAuthToken,
    Installation,
    SelectedRepo,
    Organization,
    Repository,
    AuditLog,
    AccountType,
    InstallationStatus,
    AuditSeverity,
    SyncStatus,
)

logger = logging.getLogger("backend")


def _coerce_datetime(value: Any) -> Optional[datetime]:
    """Accept SQLite ISO strings and PostgreSQL datetime values."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


# Simple obfuscation/encryption secret from env or default fallback for dev
ENCRYPTION_KEY = os.environ.get(
    "TOKEN_ENCRYPTION_SECRET", "hcl_secret_key_32bytes_change_in_prod"
)


def _encrypt(plain_text: str) -> str:
    """XOR-based light string encoding for storing tokens safely in SQLite without full heavy deps."""
    if not plain_text:
        return ""
    key_bytes = ENCRYPTION_KEY.encode("utf-8")
    text_bytes = plain_text.encode("utf-8")
    xor_bytes = bytes(
        [b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(text_bytes)]
    )
    return base64.b64encode(xor_bytes).decode("utf-8")


def _decrypt(cipher_text: str) -> str:
    """Decrypts tokens encoded with _encrypt."""
    if not cipher_text:
        return ""
    try:
        xor_bytes = base64.b64decode(cipher_text.encode("utf-8"))
        key_bytes = ENCRYPTION_KEY.encode("utf-8")
        text_bytes = bytes(
            [b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(xor_bytes)]
        )
        return text_bytes.decode("utf-8")
    except Exception:
        return cipher_text  # Fallback if plaintext was stored


async def initialize_auth_db() -> None:
    """Creates all required tables for GitHub OAuth and GitHub App integrations with enterprise constraints."""
    async with get_db() as db:
        # 1. Users Table (with soft delete support)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                github_id INTEGER UNIQUE NOT NULL,
                login TEXT NOT NULL,
                name TEXT,
                avatar_url TEXT,
                email TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
        """
        )

        # 2. OAuth Tokens Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                access_token_enc TEXT NOT NULL,
                token_type TEXT DEFAULT 'bearer',
                scope TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """
        )

        # 3. Installations Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS installations (
                id SERIAL PRIMARY KEY,
                installation_id INTEGER UNIQUE NOT NULL,
                account_login TEXT NOT NULL,
                account_type TEXT NOT NULL CHECK (account_type IN ('User', 'Organization')),
                target_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                status TEXT DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
                user_id INTEGER,
                suspended_at TEXT,
                removed_at TEXT,
                last_token_refresh TEXT,
                last_sync TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """
        )

        # Ensure any missing columns exist on installations table for existing databases
        try:
            installations_columns_query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'installations'
            """
            installations_columns_result = await db.fetch(installations_columns_query)
            existing_cols = {row["column_name"] for row in installations_columns_result}
            missing_cols = {
                "suspended_at": "TEXT",
                "removed_at": "TEXT",
                "last_token_refresh": "TEXT",
                "last_sync": "TEXT",
                "target_id": "INTEGER DEFAULT 0",
                "target_type": "TEXT DEFAULT 'User'",
            }
            for col_name, col_type in missing_cols.items():
                if col_name not in existing_cols:
                    await db.execute(
                        f"ALTER TABLE installations ADD COLUMN {col_name} {col_type};"
                    )
        except Exception as e:
            logger.warning(f"Note on installations table schema migration: {str(e)}")

        # 4. Selected Repositories Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS selected_repos (
                id SERIAL PRIMARY KEY,
                installation_id INTEGER NOT NULL,
                repo_full_name TEXT NOT NULL,
                repo_id INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1 CHECK (enabled IN (0, 1)),
                added_at TEXT NOT NULL,
                FOREIGN KEY (installation_id) REFERENCES installations (id) ON DELETE CASCADE,
                UNIQUE(installation_id, repo_full_name)
            )
        """
        )

        # 5. Ephemeral OAuth States Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                user_data TEXT,
                created_at TEXT NOT NULL
            )
        """
        )

        # 6. Organizations Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id SERIAL PRIMARY KEY,
                github_org_id INTEGER UNIQUE NOT NULL,
                login TEXT NOT NULL,
                avatar_url TEXT,
                description TEXT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, github_org_id)
            )
        """
        )

        # 7. Repositories Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS repositories (
                id SERIAL PRIMARY KEY,
                github_repo_id INTEGER UNIQUE NOT NULL,
                installation_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                name TEXT NOT NULL,
                owner_login TEXT NOT NULL,
                private INTEGER DEFAULT 0 CHECK (private IN (0, 1)),
                default_branch TEXT DEFAULT 'main',
                language TEXT,
                stargazers_count INTEGER DEFAULT 0,
                archived INTEGER DEFAULT 0 CHECK (archived IN (0, 1)),
                disabled INTEGER DEFAULT 0 CHECK (disabled IN (0, 1)),
                fork INTEGER DEFAULT 0 CHECK (fork IN (0, 1)),
                open_pr_count INTEGER DEFAULT 0,
                reviewed_pr_count INTEGER DEFAULT 0,
                blocked_pr_count INTEGER DEFAULT 0,
                last_reviewed_at TEXT,
                last_synced_at TEXT,
                sync_status TEXT DEFAULT 'idle' CHECK (sync_status IN ('idle', 'syncing', 'success', 'failed')),
                last_sync_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (installation_id) REFERENCES installations (id) ON DELETE CASCADE,
                UNIQUE(installation_id, github_repo_id)
            )
        """
        )

        # Ensure any missing columns exist on repositories table for existing databases
        try:
            repositories_columns_query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'repositories'
            """
            repositories_columns_result = await db.fetch(repositories_columns_query)
            existing_cols = {row["column_name"] for row in repositories_columns_result}
            missing_cols = {
                "disabled": "INTEGER DEFAULT 0",
                "archived": "INTEGER DEFAULT 0",
                "fork": "INTEGER DEFAULT 0",
                "last_synced_at": "TEXT",
                "sync_status": "TEXT DEFAULT 'idle'",
                "created_at": "TEXT DEFAULT ''",
                "updated_at": "TEXT DEFAULT ''",
            }
            for col_name, col_type in missing_cols.items():
                if col_name not in existing_cols:
                    await db.execute(
                        f"ALTER TABLE repositories ADD COLUMN {col_name} {col_type};"
                    )
        except Exception as e:
            logger.warning(f"Note on repositories table schema migration: {str(e)}")

        # 8. Redesigned Enterprise Audit Logs Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                request_id TEXT,
                trace_id TEXT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                severity TEXT DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
                details_json TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """
        )

        # 9. Notifications Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                type TEXT DEFAULT 'info',
                title TEXT,
                message TEXT,
                link TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """
        )

        # 9. Pull Requests Table for Enterprise Analytics & PR Service
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS pull_requests (
                id SERIAL PRIMARY KEY,

                -- GitHub IDs must use BIGINT because GitHub IDs can exceed
                -- PostgreSQL's 32-bit INTEGER range.
                github_pr_id BIGINT UNIQUE NOT NULL,

                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'open',
                draft INTEGER DEFAULT 0,
                merged INTEGER DEFAULT 0,

                owner TEXT NOT NULL,
                repository_name TEXT NOT NULL,

                installation_id INTEGER,
                author_login TEXT NOT NULL,
                author_avatar_url TEXT,

                base_branch TEXT DEFAULT 'main',
                head_branch TEXT DEFAULT '',
                head_sha TEXT DEFAULT '',
                html_url TEXT,

                review_status TEXT DEFAULT 'pending',
                decision TEXT DEFAULT 'PENDING',

                security_issues_count INTEGER DEFAULT 0,
                quality_issues_count INTEGER DEFAULT 0,

                coverage_percentage REAL DEFAULT 100.0,
                processing_time_sec REAL DEFAULT 0.0,

                review_posted INTEGER DEFAULT 0,
                review_posted_at TEXT,

                -- GitHub review IDs can also exceed 32-bit INTEGER.
                github_review_id BIGINT,

                summary_md TEXT,
                risk_level TEXT DEFAULT 'LOW',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                merged_at TEXT,
                closed_at TEXT
            )
        """
        )

        # ---------------------------------------------------------------------------
        # Pull Requests schema migrations
        # ---------------------------------------------------------------------------
        # These migrations are idempotent. They are safe to run on every startup.
        # They upgrade older production databases without deleting existing data.

        _pr_extra_cols = {
            "repository_id": "BIGINT",
            "body": "TEXT DEFAULT ''",
            "mergeable": "INTEGER DEFAULT 1",
            "author_avatar": "TEXT DEFAULT ''",
            "base_sha": "TEXT DEFAULT ''",
            "api_url": "TEXT DEFAULT ''",
            "additions": "INTEGER DEFAULT 0",
            "deletions": "INTEGER DEFAULT 0",
            "changed_files": "INTEGER DEFAULT 0",
            "commits": "INTEGER DEFAULT 0",
            "labels": "TEXT DEFAULT '[]'",
            "requested_reviewers": "TEXT DEFAULT '[]'",
            "raw_payload": "TEXT DEFAULT '{}'",
            "last_synced_at": "TEXT",
            "issues_count": "INTEGER DEFAULT 0",
            "high_count": "INTEGER DEFAULT 0",
            "medium_count": "INTEGER DEFAULT 0",
            "low_count": "INTEGER DEFAULT 0",
            "review_summary": "TEXT",
            "issues_json": "TEXT DEFAULT '[]'",
            "previous_issues_json": "TEXT",
            "previous_review_summary": "TEXT",
            "reviewed_at": "TEXT",
        }

        try:
            pr_col_result = await db.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'pull_requests'
                """
            )

            pr_existing_cols = {r["column_name"] for r in pr_col_result}

            for col_name, col_def in _pr_extra_cols.items():
                if col_name not in pr_existing_cols:
                    await db.execute(
                        f"ALTER TABLE pull_requests ADD COLUMN {col_name} {col_def};"
                    )

        except Exception as e:
            logger.warning(f"Note on pull_requests migration: {e}")


        # ---------------------------------------------------------------------------
        # GitHub ID type migrations
        # ---------------------------------------------------------------------------

        # GitHub PR IDs can exceed PostgreSQL's 32-bit INTEGER range.
        # Example:
        # 4265044189 > 2147483647
        #
        # This migration upgrades existing production data from INTEGER -> BIGINT.
        # Existing values are preserved.
        try:
            await db.execute(
                """
                ALTER TABLE pull_requests
                ALTER COLUMN github_pr_id TYPE BIGINT;
                """
            )
        except Exception as err:
            logger.warning(
                f"Note on github_pr_id BIGINT migration: {err}"
            )


        # GitHub repository IDs can exceed PostgreSQL's 32-bit INTEGER range.
        # Keep repository_id BIGINT as well.
        try:
            await db.execute(
                """
                ALTER TABLE pull_requests
                ALTER COLUMN repository_id TYPE BIGINT;
                """
            )
        except Exception as err:
            logger.warning(
                f"Note on repository_id BIGINT migration: {err}"
            )


        # GitHub review IDs can exceed PostgreSQL's 32-bit INTEGER range.
        # This is required for values such as:
        # 4919237848
        try:
            await db.execute(
                """
                ALTER TABLE pull_requests
                ALTER COLUMN github_review_id TYPE BIGINT;
                """
            )
        except Exception as err:
            logger.warning(
                f"Note on github_review_id BIGINT migration: {err}"
            )


        # ---------------------------------------------------------------------------
        # Indexes for query performance & scale
        # ---------------------------------------------------------------------------

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);"
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);"
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);"
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_inst ON repositories(installation_id);"
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_enabled ON selected_repos(enabled);"
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_full_name ON selected_repos(repo_full_name);"
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_orgs_user ON organizations(user_id);"
        )


        # ---------------------------------------------------------------------------
        # Existing DB migrations
        # ---------------------------------------------------------------------------

        # Ensure deleted_at exists in users table.
        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN deleted_at TEXT;"
            )
        except Exception:
            pass


        # Ensure enterprise audit columns exist.
        try:
            await db.execute(
                "ALTER TABLE audit_logs ADD COLUMN request_id TEXT;"
            )

            await db.execute(
                "ALTER TABLE audit_logs ADD COLUMN trace_id TEXT;"
            )

            await db.execute(
                "ALTER TABLE audit_logs ADD COLUMN entity_type TEXT;"
            )

            await db.execute(
                "ALTER TABLE audit_logs ADD COLUMN entity_id TEXT;"
            )

            await db.execute(
                "ALTER TABLE audit_logs ADD COLUMN severity TEXT DEFAULT 'INFO';"
            )

            await db.execute(
                "ALTER TABLE audit_logs ADD COLUMN details_json TEXT;"
            )

        except Exception:
            pass


        logger.info(
            "Auth Database Schema Initialized with Enterprise Rules."
        )


# ---------------------------------------------------------------------------
# User CRUD & Soft Delete
# ---------------------------------------------------------------------------


async def upsert_user(
    github_id: int,
    login: str,
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    email: Optional[str] = None,
) -> User:
    """Inserts or updates a GitHub user in the database."""
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO users (github_id, login, name, avatar_url, email, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT(github_id) DO UPDATE SET
                login = excluded.login,
                name = COALESCE(excluded.name, users.name),
                avatar_url = COALESCE(excluded.avatar_url, users.avatar_url),
                email = COALESCE(excluded.email, users.email),
                updated_at = excluded.updated_at,
                deleted_at = NULL
        """,
            github_id,
            login,
            name,
            avatar_url,
            email,
            now,
            now,
        )

        row = await db.fetchrow("SELECT * FROM users WHERE github_id = $1", github_id)
        return User(
            id=row["id"],
            github_id=row["github_id"],
            login=row["login"],
            name=row["name"],
            avatar_url=row["avatar_url"],
            email=row["email"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=(
                datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None
            ),
        )


async def get_user_by_id(user_id: int) -> Optional[User]:
    """Retrieves an active (non-deleted) user by primary key."""
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT * FROM users WHERE id = $1 AND deleted_at IS NULL", user_id
        )
        if not row:
            return None
        return User(
            id=row["id"],
            github_id=row["github_id"],
            login=row["login"],
            name=row["name"],
            avatar_url=row["avatar_url"],
            email=row["email"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=(
                datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None
            ),
        )


async def soft_delete_user(user_id: int) -> bool:
    """Soft-deletes a user by setting deleted_at timestamp."""
    now_str = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE users SET deleted_at = $1 WHERE id = $2 AND deleted_at IS NULL",
            now_str,
            user_id,
        )
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# OAuth Token CRUD
# ---------------------------------------------------------------------------


async def save_oauth_token(
    user_id: int,
    access_token: str,
    scope: str = "",
    expires_at: Optional[datetime] = None,
) -> OAuthToken:
    """Saves or updates an encrypted OAuth access token for a user."""
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    expires_str = expires_at.isoformat() if expires_at else None
    enc_token = _encrypt(access_token)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO oauth_tokens (user_id, access_token_enc, token_type, scope, created_at, expires_at)
            VALUES ($1, $2, 'bearer', $3, $4, $5)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token_enc = excluded.access_token_enc,
                scope = excluded.scope,
                expires_at = excluded.expires_at
        """,
            user_id,
            enc_token,
            scope,
            now_str,
            expires_str,
        )

        row = await db.fetchrow(
            "SELECT * FROM oauth_tokens WHERE user_id = $1", user_id
        )
        return OAuthToken(
            id=row["id"],
            user_id=row["user_id"],
            access_token=access_token,
            token_type=row["token_type"],
            scope=row["scope"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=(
                datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            ),
        )


async def get_oauth_token(user_id: int) -> Optional[OAuthToken]:
    """Retrieves and decrypts the OAuth token for a given user."""
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT * FROM oauth_tokens WHERE user_id = $1", user_id
        )
        if not row:
            return None
        decrypted_token = _decrypt(row["access_token_enc"])
        return OAuthToken(
            id=row["id"],
            user_id=row["user_id"],
            access_token=decrypted_token,
            token_type=row["token_type"],
            scope=row["scope"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=(
                datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            ),
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

async def create_notification(
    user_id: int, type: str, title: str, message: str, link: Optional[str] = None
) -> None:
    async with get_db() as db:
        await db.execute(
            """INSERT INTO notifications (user_id, type, title, message, link, is_read, created_at)
               VALUES ($1, $2, $3, $4, $5, 0, $6)""",
            user_id, type, title, message, link, datetime.now(timezone.utc).isoformat()
        )

async def get_notifications_for_user(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id, limit
        )
        return [dict(r) for r in rows]

async def mark_notification_read(notification_id: int, user_id: int) -> bool:
    async with get_db() as db:
        status_str = await db.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = $1 AND user_id = $2",
            notification_id, user_id
        )
        return status_str.rowcount > 0

async def mark_all_notifications_read(user_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = $1", user_id
        )

async def get_user_ids_for_installation(installation_id: int) -> List[int]:
    """Returns all user_ids that own the given GitHub App installation_id."""
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT DISTINCT user_id FROM installations WHERE installation_id = $1 AND user_id IS NOT NULL",
            installation_id,
        )
        return [r["user_id"] for r in rows]

# ---------------------------------------------------------------------------
# State CSRF Management
# ---------------------------------------------------------------------------


async def save_oauth_state(state: str, user_data: Optional[str] = None) -> None:
    """Stores state string for CSRF validation."""
    now_str = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO oauth_states (state, user_data, created_at) VALUES ($1, $2, $3)",
            state,
            user_data,
            now_str,
        )


async def pop_oauth_state(state: str) -> bool:
    """Validates state and consumes it immediately to prevent replay attacks."""
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT state FROM oauth_states WHERE state = $1", state
        )
        if not row:
            return False
        await db.execute("DELETE FROM oauth_states WHERE state = $1", state)
        return True


# ---------------------------------------------------------------------------
# Installation CRUD
# ---------------------------------------------------------------------------


async def upsert_installation(
    installation_id: int,
    account_login: str,
    account_type: str,
    target_id: int,
    target_type: str,
    user_id: Optional[int] = None,
    status: str = "active",
) -> Installation:
    """Upserts a GitHub App installation into SQLite."""
    now_str = datetime.now(timezone.utc).isoformat()
    suspended_at = now_str if status == "suspended" else None
    removed_at = now_str if status == "deleted" else None

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO installations (
                installation_id, account_login, account_type, target_id,
                target_type, status, user_id, suspended_at, removed_at, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT(installation_id) DO UPDATE SET
                account_login = excluded.account_login,
                account_type = excluded.account_type,
                status = excluded.status,
                user_id = COALESCE(excluded.user_id, installations.user_id),
                suspended_at = excluded.suspended_at,
                removed_at = excluded.removed_at,
                updated_at = excluded.updated_at
        """,
            installation_id,
            account_login,
            account_type,
            target_id,
            target_type,
            status,
            user_id,
            suspended_at,
            removed_at,
            now_str,
            now_str,
        )

        row = await db.fetchrow(
            "SELECT * FROM installations WHERE installation_id = $1", installation_id
        )
        return Installation(
            id=row["id"],
            installation_id=row["installation_id"],
            account_login=row["account_login"],
            account_type=AccountType(row["account_type"]),
            target_id=row["target_id"],
            target_type=row["target_type"],
            status=InstallationStatus(row["status"]),
            user_id=row["user_id"],
            suspended_at=(
                datetime.fromisoformat(row["suspended_at"])
                if row["suspended_at"]
                else None
            ),
            removed_at=(
                datetime.fromisoformat(row["removed_at"]) if row["removed_at"] else None
            ),
            last_token_refresh=(
                datetime.fromisoformat(row["last_token_refresh"])
                if row["last_token_refresh"]
                else None
            ),
            last_sync=(
                datetime.fromisoformat(row["last_sync"]) if row["last_sync"] else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


async def get_installations_for_user(user_id: int) -> List[Installation]:
    """Retrieves all active app installations associated with a user."""
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM installations WHERE user_id = $1 AND status = 'active'",
            user_id,
        )
        return [
            Installation(
                id=row["id"],
                installation_id=row["installation_id"],
                account_login=row["account_login"],
                account_type=AccountType(row["account_type"]),
                target_id=row["target_id"],
                target_type=row["target_type"],
                status=InstallationStatus(row["status"]),
                user_id=row["user_id"],
                suspended_at=(
                    datetime.fromisoformat(row["suspended_at"])
                    if row["suspended_at"]
                    else None
                ),
                removed_at=(
                    datetime.fromisoformat(row["removed_at"])
                    if row["removed_at"]
                    else None
                ),
                last_token_refresh=(
                    datetime.fromisoformat(row["last_token_refresh"])
                    if row["last_token_refresh"]
                    else None
                ),
                last_sync=(
                    datetime.fromisoformat(row["last_sync"])
                    if row["last_sync"]
                    else None
                ),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]


async def get_installation_by_id(installation_id: int) -> Optional[Installation]:
    """Finds installation by GitHub's installation_id."""
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT * FROM installations WHERE installation_id = $1", installation_id
        )
        if not row:
            return None
        return Installation(
            id=row["id"],
            installation_id=row["installation_id"],
            account_login=row["account_login"],
            account_type=AccountType(row["account_type"]),
            target_id=row["target_id"],
            target_type=row["target_type"],
            status=InstallationStatus(row["status"]),
            user_id=row["user_id"],
            suspended_at=(
                datetime.fromisoformat(row["suspended_at"])
                if row["suspended_at"]
                else None
            ),
            removed_at=(
                datetime.fromisoformat(row["removed_at"]) if row["removed_at"] else None
            ),
            last_token_refresh=(
                datetime.fromisoformat(row["last_token_refresh"])
                if row["last_token_refresh"]
                else None
            ),
            last_sync=(
                datetime.fromisoformat(row["last_sync"]) if row["last_sync"] else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# ---------------------------------------------------------------------------
# Selected Repos CRUD & Webhook Verification
# ---------------------------------------------------------------------------


async def save_selected_repos(
    installation_internal_id: int, selected_repos: List[Tuple[str, int]]
) -> None:
    """
    Saves a list of (repo_full_name, repo_id) tuples as enabled for a given installation.
    Disables any previously selected repos for that installation that are not in the new list.
    Executed inside an atomic transaction.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        # Step 1: Mark all current repos for this installation as disabled (0)
        await db.execute(
            "UPDATE selected_repos SET enabled = 0 WHERE installation_id = $1",
            installation_internal_id,
        )

        # Step 2: Upsert selected repos as enabled (1)
        for full_name, repo_id in selected_repos:
            await db.execute(
                """
                INSERT INTO selected_repos (installation_id, repo_full_name, repo_id, enabled, added_at)
                VALUES ($1, $2, $3, 1, $4)
                ON CONFLICT(installation_id, repo_full_name) DO UPDATE SET
                    enabled = 1,
                    repo_id = excluded.repo_id
            """,
                installation_internal_id,
                full_name,
                repo_id,
                now_str,
            )


async def get_selected_repos_for_installation(
    installation_internal_id: int,
) -> List[SelectedRepo]:
    """Gets all currently enabled repositories for an installation."""
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM selected_repos WHERE installation_id = $1 AND enabled = 1 ORDER BY added_at DESC",
            installation_internal_id,
        )
        return [
            SelectedRepo(
                id=row["id"],
                installation_id=row["installation_id"],
                repo_full_name=row["repo_full_name"],
                repo_id=row["repo_id"],
                enabled=bool(row["enabled"]),
                added_at=datetime.fromisoformat(row["added_at"]),
            )
            for row in rows
        ]


async def is_repo_whitelisted(repo_full_name: str) -> bool:
    """
    Automatically verifies webhook events belong to installed & enabled repositories.
    If no repositories have been explicitly configured/selected yet in the DB, defaults to True.
    """
    async with get_db() as db:
        total_selected = await db.fetchval(
            "SELECT COUNT(*) FROM selected_repos WHERE enabled = 1"
        )

        if total_selected == 0:
            return True

        match = await db.fetchrow(
            "SELECT id FROM selected_repos WHERE LOWER(repo_full_name) = LOWER($1) AND enabled = 1",
            repo_full_name,
        )
        return match is not None


# ---------------------------------------------------------------------------
# Redesigned Enterprise Audit Log CRUD
# ---------------------------------------------------------------------------


async def create_audit_log(
    action: str,
    user_id: Optional[int] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    severity: str = "INFO",
    details_json: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Inserts a structured enterprise audit log entry."""
    now_str = datetime.now(timezone.utc).isoformat()
    json_str = json.dumps(details_json) if details_json else None

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO audit_logs (
                request_id, trace_id, user_id, action, entity_type, entity_id,
                severity, details_json, ip_address, user_agent, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            request_id,
            trace_id,
            user_id,
            action,
            entity_type,
            entity_id,
            severity,
            json_str,
            ip_address,
            user_agent,
            now_str,
        )


async def get_audit_logs_for_user(user_id: int, limit: int = 50) -> List[AuditLog]:
    """Fetches recent audit logs for a given user."""
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM audit_logs WHERE user_id = $1 ORDER BY id DESC LIMIT $2",
            user_id,
            limit,
        )
        return [
            AuditLog(
                id=row["id"],
                request_id=row["request_id"],
                trace_id=row["trace_id"],
                user_id=row["user_id"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                severity=AuditSeverity(row["severity"]),
                details_json=row["details_json"],
                ip_address=row["ip_address"],
                user_agent=row["user_agent"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# Repository Sync & Query
# ---------------------------------------------------------------------------


async def sync_repos_in_db(
    installation_internal_id: int,
    github_repos: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Upserts every repository returned by GitHub into the repositories table,
    then marks any previously-known repos for this installation that are no
    longer present as inactive (disabled=1).
    Returns the final list of active repo dicts for this installation.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    incoming_ids = {r["id"] for r in github_repos}

    async with get_db() as db:
        # Step 1 – upsert every repo returned by GitHub
        for r in github_repos:
            await db.execute(
                """
                INSERT INTO repositories (
                    github_repo_id, installation_id, full_name, name, owner_login,
                    private, default_branch, language, stargazers_count,
                    archived, disabled, fork,
                    last_synced_at, sync_status, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 0, $11, $12, 'success', $13, $14)
                ON CONFLICT(github_repo_id) DO UPDATE SET
                    full_name        = excluded.full_name,
                    name             = excluded.name,
                    owner_login      = excluded.owner_login,
                    private          = excluded.private,
                    default_branch   = excluded.default_branch,
                    language         = excluded.language,
                    stargazers_count = excluded.stargazers_count,
                    archived         = excluded.archived,
                    disabled         = 0,
                    fork             = excluded.fork,
                    last_synced_at   = excluded.last_synced_at,
                    sync_status      = 'success',
                    updated_at       = excluded.updated_at
                """,
                r["id"],
                installation_internal_id,
                r.get("full_name", ""),
                r.get("name", ""),
                r.get("owner", {}).get("login", ""),
                1 if r.get("private") else 0,
                r.get("default_branch", "main"),
                r.get("language"),
                r.get("stargazers_count", 0),
                1 if r.get("archived") else 0,
                1 if r.get("fork") else 0,
                now_str,
                now_str,
                now_str,
            )

        # Step 2 – mark repos no longer in the GitHub response as inactive
        if incoming_ids:
            existing_rows = await db.fetch(
                "SELECT github_repo_id FROM repositories WHERE installation_id = $1 AND disabled = 0",
                installation_internal_id,
            )
            existing_ids = {row["github_repo_id"] for row in existing_rows}

            removed_ids = existing_ids - incoming_ids
            for repo_id in removed_ids:
                await db.execute(
                    "UPDATE repositories SET disabled = 1, sync_status = 'inactive', updated_at = $1 "
                    "WHERE github_repo_id = $2 AND installation_id = $3",
                    now_str,
                    repo_id,
                    installation_internal_id,
                )

        # Step 3 – return all active repos for this installation
        rows = await db.fetch(
            "SELECT * FROM repositories WHERE installation_id = $1 AND disabled = 0 ORDER BY full_name ASC",
            installation_internal_id,
        )
        return [dict(row) for row in rows]


async def get_repos_for_user(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns all active (disabled=0) repositories across every active installation
    owned by the given user, formatted for the GET /api/repositories response.
    """
    installations = await get_installations_for_user(user_id)
    if not installations:
        return []

    inst_ids = [inst.id for inst in installations]

    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM repositories WHERE installation_id = ANY($1) AND disabled = 0 ORDER BY full_name ASC",
            inst_ids,
        )
        return [
            {
                "id": row["github_repo_id"],
                "repo_id": row["github_repo_id"],
                "name": row["name"],
                "full_name": row["full_name"],
                "private": bool(row["private"]),
                "default_branch": row["default_branch"] or "main",
                "enabled": True,
            }
            for row in rows
        ]


# ---------------------------------------------------------------------------
# Webhook Delivery Deduplication
# ---------------------------------------------------------------------------


async def is_delivery_processed(delivery_id: str) -> bool:
    """Check if a webhook delivery GUID has already been processed."""
    if not delivery_id:
        return False
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT 1 FROM webhook_deliveries WHERE delivery_id = $1", delivery_id
        )
        return row is not None


async def record_webhook_delivery(
    delivery_id: str, event_type: str, action: Optional[str] = None
) -> bool:
    """
    Record a processed webhook delivery GUID.
    Returns True if newly inserted, False if it was already present (duplicate).
    """
    if not delivery_id:
        return True
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO webhook_deliveries (delivery_id, event_type, action, status, processed_at) "
                "VALUES ($1, $2, $3, 'processed', $4)",
                delivery_id,
                event_type,
                action,
                now_str,
            )
            return True
    except Exception:
        # Unique constraint violation means duplicate delivery ID
        return False


async def record_github_webhook_delivery(
    delivery_id: str,
    event: str,
    payload_sha256: str,
    action: Optional[str],
    installation_id: Optional[str],
    request: Any,
) -> bool:
    """Atomically claim a GitHub delivery and record exactly one audit event."""
    now = datetime.now(timezone.utc).isoformat()
    details = json.dumps(
        {
            "event": event,
            "action": action,
            "delivery_id": delivery_id,
            "payload_sha256": payload_sha256,
        }
    )
    async with get_db() as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS github_webhook_deliveries (
            delivery_id TEXT PRIMARY KEY, event TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
            action TEXT, installation_id TEXT, received_at TEXT NOT NULL)"""
        )
        try:
            await db.execute(
                "INSERT INTO github_webhook_deliveries (delivery_id, event, payload_sha256, action, installation_id, received_at) VALUES ($1, $2, $3, $4, $5, $6)",
                delivery_id,
                event,
                payload_sha256,
                action,
                installation_id,
                now,
            )
        except Exception as exc:
            if "unique" in str(exc).lower() or "constraint" in str(exc).lower():
                return False
            raise
        try:
            client = getattr(request, "client", None)
            await db.execute(
                """INSERT INTO audit_logs (request_id, trace_id, user_id, action, entity_type, entity_id,
                   severity, details_json, ip_address, user_agent, created_at)
                   VALUES ($1, $2, NULL, $3, $4, $5, 'INFO', $6, $7, $8, $9)""",
                delivery_id,
                delivery_id,
                "GITHUB_WEBHOOK_RECEIVED",
                "GitHubWebhook",
                installation_id,
                details,
                client.host if client else None,
                request.headers.get("User-Agent"),
                now,
            )
        except Exception:
            pass  # Audit log failure should not fail webhook processing
    return True


# ---------------------------------------------------------------------------
# Pull Request Processing Functions
# ---------------------------------------------------------------------------


async def upsert_pull_request(pr_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upserts pull request metadata into the pull_requests table.
    Overwrites existing records based on github_pr_id.
    """
    now_str = datetime.now(timezone.utc).isoformat()

    github_pr_id = pr_data["github_pr_id"]
    repository_id = pr_data.get("repository_id")
    repository_name = pr_data["repository_name"]
    owner = pr_data["owner"]
    number = pr_data["number"]
    title = pr_data.get("title", "")
    body = pr_data.get("body", "")
    state = pr_data.get("state", "open").lower()
    draft = 1 if pr_data.get("draft") else 0
    merged = 1 if pr_data.get("merged") else 0
    mergeable = 1 if pr_data.get("mergeable", True) else 0
    author_login = pr_data.get("author_login", "unknown")
    author_avatar = pr_data.get("author_avatar", "")
    base_branch = pr_data.get("base_branch", "main")
    head_branch = pr_data.get("head_branch", "")
    head_sha = pr_data.get("head_sha", "")
    base_sha = pr_data.get("base_sha", "")
    created_at = pr_data.get("created_at") or now_str
    updated_at = pr_data.get("updated_at") or now_str
    closed_at = pr_data.get("closed_at")
    merged_at = pr_data.get("merged_at")
    html_url = pr_data.get("html_url", "")
    api_url = pr_data.get("api_url", "")
    additions = pr_data.get("additions", 0)
    deletions = pr_data.get("deletions", 0)
    changed_files = pr_data.get("changed_files", 0)
    commits = pr_data.get("commits", 0)

    labels_json = (
        json.dumps(pr_data.get("labels", []))
        if isinstance(pr_data.get("labels"), (list, dict))
        else (pr_data.get("labels") or "[]")
    )
    reviewers_json = (
        json.dumps(pr_data.get("requested_reviewers", []))
        if isinstance(pr_data.get("requested_reviewers"), (list, dict))
        else (pr_data.get("requested_reviewers") or "[]")
    )
    raw_payload_json = (
        json.dumps(pr_data.get("raw_payload", {}))
        if isinstance(pr_data.get("raw_payload"), dict)
        else (pr_data.get("raw_payload") or "{}")
    )

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO pull_requests (
                github_pr_id, repository_id, repository_name, owner, number,
                title, body, state, draft, merged, mergeable,
                author_login, author_avatar, base_branch, head_branch,
                head_sha, base_sha, created_at, updated_at, closed_at,
                merged_at, html_url, api_url, additions, deletions,
                changed_files, commits, labels, requested_reviewers,
                raw_payload, last_synced_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31)
            ON CONFLICT(github_pr_id) DO UPDATE SET
                repository_id=excluded.repository_id,
                repository_name=excluded.repository_name,
                owner=excluded.owner,
                number=excluded.number,
                title=excluded.title,
                body=excluded.body,
                state=excluded.state,
                draft=excluded.draft,
                merged=excluded.merged,
                mergeable=excluded.mergeable,
                author_login=excluded.author_login,
                author_avatar=excluded.author_avatar,
                base_branch=excluded.base_branch,
                head_branch=excluded.head_branch,
                head_sha=excluded.head_sha,
                base_sha=excluded.base_sha,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at,
                closed_at=excluded.closed_at,
                merged_at=excluded.merged_at,
                html_url=excluded.html_url,
                api_url=excluded.api_url,
                additions=excluded.additions,
                deletions=excluded.deletions,
                changed_files=excluded.changed_files,
                commits=excluded.commits,
                labels=excluded.labels,
                requested_reviewers=excluded.requested_reviewers,
                raw_payload=excluded.raw_payload,
                last_synced_at=excluded.last_synced_at
            """,
            github_pr_id,
            repository_id,
            repository_name,
            owner,
            number,
            title,
            body,
            state,
            draft,
            merged,
            mergeable,
            author_login,
            author_avatar,
            base_branch,
            head_branch,
            head_sha,
            base_sha,
            created_at,
            updated_at,
            closed_at,
            merged_at,
            html_url,
            api_url,
            additions,
            deletions,
            changed_files,
            commits,
            labels_json,
            reviewers_json,
            raw_payload_json,
            now_str,
        )

        row = await db.fetchrow(
            "SELECT * FROM pull_requests WHERE github_pr_id = $1", github_pr_id
        )
        res = dict(row)
        res["draft"] = bool(res["draft"])
        res["merged"] = bool(res["merged"])
        res["labels"] = json.loads(res["labels"]) if res.get("labels") else []
        res["requested_reviewers"] = (
            json.loads(res["requested_reviewers"])
            if res.get("requested_reviewers")
            else []
        )
        return res


async def get_pull_request(
    number: int, repository_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Fetch a single pull request by number and optional repository_name."""
    async with get_db() as db:
        if repository_name:
            row = await db.fetchrow(
                "SELECT * FROM pull_requests WHERE number = $1 AND (repository_name = $2 OR owner || '/' || repository_name = $2)",
                number,
                repository_name,
            )
        else:
            row = await db.fetchrow(
                "SELECT * FROM pull_requests WHERE number = $1 ORDER BY id DESC LIMIT 1",
                number,
            )
        if not row:
            return None
        res = dict(row)
        res["draft"] = bool(res["draft"])
        res["merged"] = bool(res["merged"])
        res["labels"] = json.loads(res["labels"]) if res.get("labels") else []
        res["requested_reviewers"] = (
            json.loads(res["requested_reviewers"])
            if res.get("requested_reviewers")
            else []
        )
        return res


async def list_pull_requests(
    page: int = 1,
    per_page: int = 20,
    state_filter: Optional[str] = None,
    repository_name: Optional[str] = None,
    author: Optional[str] = None,
    decision: Optional[str] = None,
    review_status: Optional[str] = None,
    sort: Optional[str] = "newest",
    date_range: Optional[str] = None,
    search_query: Optional[str] = None,
) -> Dict[str, Any]:
    """Lists paginated pull requests with rich multi-field filtering, search, and sorting."""
    offset = (page - 1) * per_page
    where_conditions: List[str] = []
    params: List[Any] = []

    # 1. State filter
    if state_filter and state_filter.lower() != "all":
        st = state_filter.lower()
        if st == "merged":
            where_conditions.append("merged = 1")
        elif st == "draft":
            where_conditions.append("draft = 1 AND state = 'open'")
        elif st == "closed":
            where_conditions.append("state = 'closed' AND merged = 0")
        else:
            where_conditions.append("state = $1")
            params.append(st)

    # 2. Repository filter
    if repository_name and repository_name.lower() != "all":
        where_conditions.append(
            "(repository_name = $1 OR owner || '/' || repository_name = $1)"
        )
        params.append(repository_name)

    # 3. Author filter
    if author:
        where_conditions.append("LOWER(author_login) LIKE $1")
        params.append(f"%{author.lower()}%")

    # 4. Decision filter
    if decision and decision.upper() != "ALL":
        where_conditions.append("UPPER(decision) = $1")
        params.append(decision.upper())

    # 5. Review status filter
    if review_status and review_status.lower() != "all":
        st = review_status.lower()
        if st == "completed":
            where_conditions.append(
                "review_status IN ('success', 'failed', 'processing')"
            )
        elif st == "pending":
            where_conditions.append("review_status = 'pending'")
        elif st == "processing":
            where_conditions.append("review_status = 'processing'")
        else:
            where_conditions.append("review_status = $1")
            params.append(st)

    # 6. Search query
    if search_query:
        where_conditions.append("(title ILIKE $1 OR body ILIKE $1)")
        params.append(f"%{search_query}%")

    # Build WHERE clause
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

    # Sorting
    order_by_clause = "ORDER BY created_at DESC"
    if sort == "oldest":
        order_by_clause = "ORDER BY created_at ASC"
    elif sort == "updated":
        order_by_clause = "ORDER BY updated_at DESC"

    # Get total count
    async with get_db() as db:
        count_query = (
            f"SELECT COUNT(*) as count FROM pull_requests WHERE {where_clause}"
        )
        total_row = await db.fetchrow(count_query, *params)
        total = total_row["count"] if total_row else 0

        # Get paginated results
        query = f"SELECT * FROM pull_requests WHERE {where_clause} {order_by_clause} LIMIT $1 OFFSET $2"
        rows = await db.fetch(query, *params, per_page, offset)
        items = []
        for row in rows:
            r = dict(row)
            r["draft"] = bool(r["draft"])
            r["merged"] = bool(r["merged"])
            r["labels"] = json.loads(r["labels"]) if r.get("labels") else []
            r["requested_reviewers"] = (
                json.loads(r["requested_reviewers"])
                if r.get("requested_reviewers")
                else []
            )
            items.append(r)

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


async def get_pr_stats() -> Dict[str, Any]:
    """Returns total, open, closed, merged, draft, and AI Review Dashboard telemetry metrics."""
    async with get_db() as db:
        row = await db.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN state = 'open' AND draft = 0 THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN state = 'closed' AND merged = 0 THEN 1 ELSE 0 END) as closed_count,
                SUM(CASE WHEN merged = 1 THEN 1 ELSE 0 END) as merged_count,
                SUM(CASE WHEN draft = 1 AND state = 'open' THEN 1 ELSE 0 END) as draft_count,
                SUM(CASE WHEN review_status IN ('success', 'failed', 'processing') THEN 1 ELSE 0 END) as total_reviews,
                SUM(CASE WHEN decision IN ('SAFE', 'PERFECT') THEN 1 ELSE 0 END) as safe_count,
                SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END) as block_count,
                SUM(CASE WHEN decision = 'REVIEW_REQUIRED' THEN 1 ELSE 0 END) as review_required_count,
                SUM(CASE WHEN decision = 'ERROR' OR review_status = 'failed' THEN 1 ELSE 0 END) as error_count,
                AVG(CASE WHEN coverage_percentage > 0 THEN coverage_percentage ELSE NULL END) as avg_coverage,
                AVG(CASE WHEN processing_time_sec > 0 THEN processing_time_sec ELSE NULL END) as avg_processing_time_sec,
                SUM(CASE WHEN review_posted = 1 THEN 1 ELSE 0 END) as total_comments_published
            FROM pull_requests
            """
        )
        if not row:
            return {
                "total": 0,
                "open": 0,
                "closed": 0,
                "merged": 0,
                "draft": 0,
                "total_reviews": 0,
                "safe_count": 0,
                "block_count": 0,
                "review_required_count": 0,
                "error_count": 0,
                "avg_coverage": 100.0,
                "avg_processing_time_sec": 3.8,
                "total_comments_published": 0,
            }

        monitored_count = (
            await db.fetchval("SELECT COUNT(*) FROM selected_repos WHERE enabled = 1")
            or 0
        )
        if monitored_count == 0:
            monitored_count = (
                await db.fetchval(
                    "SELECT COUNT(*) FROM repositories WHERE disabled = 0"
                )
                or 0
            )

        avg_cov = round(float(row["avg_coverage"] or 100.0), 1)
        avg_proc = round(float(row["avg_processing_time_sec"] or 3.8), 1)

        return {
            "total": row["total"] or 0,
            "open": row["open_count"] or 0,
            "closed": row["closed_count"] or 0,
            "merged": row["merged_count"] or 0,
            "draft": row["draft_count"] or 0,
            "total_reviews": row["total_reviews"] or 0,
            "safe_count": row["safe_count"] or 0,
            "block_count": row["block_count"] or 0,
            "review_required_count": row["review_required_count"] or 0,
            "error_count": row["error_count"] or 0,
            "avg_coverage": avg_cov,
            "avg_processing_time_sec": avg_proc,
            "total_comments_published": row["total_comments_published"] or 0,
            "selected_repos_count": int(monitored_count),
            "monitored_repositories_count": int(monitored_count),
        }


async def update_pull_request_review_results(
    github_pr_id: int,
    review_status: str,
    decision: str = "PENDING",
    issues_count: int = 0,
    high_count: int = 0,
    medium_count: int = 0,
    low_count: int = 0,
    coverage_percentage: float = 0.0,
    review_summary: Optional[str] = None,
    issues_json: Optional[str] = "[]",
) -> Optional[Dict[str, Any]]:
    """Updates review status, decision, severity metrics, and findings for a pull request."""
    now_str = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            """
            UPDATE pull_requests
            SET previous_issues_json = CASE WHEN issues_json != '[]' THEN issues_json ELSE previous_issues_json END,
                previous_review_summary = CASE WHEN review_summary IS NOT NULL THEN review_summary ELSE previous_review_summary END,
                review_status = $1,
                decision = $2,
                issues_count = $3,
                high_count = $4,
                medium_count = $5,
                low_count = $6,
                coverage_percentage = $7,
                review_summary = $8,
                issues_json = $9,
                reviewed_at = $10
            WHERE github_pr_id = $11
            """,
            review_status,
            decision,
            issues_count,
            high_count,
            medium_count,
            low_count,
            coverage_percentage,
            review_summary,
            issues_json,
            now_str,
            github_pr_id,
        )

        row = await db.fetchrow(
            "SELECT * FROM pull_requests WHERE github_pr_id = $1", github_pr_id
        )
        if not row:
            return None
        res = dict(row)
        res["draft"] = bool(res["draft"])
        res["merged"] = bool(res["merged"])
        res["labels"] = json.loads(res["labels"]) if res.get("labels") else []
        res["requested_reviewers"] = (
            json.loads(res["requested_reviewers"])
            if res.get("requested_reviewers")
            else []
        )
        return res


async def update_pull_request_review_published(
    github_pr_id: int,
    review_id: Optional[int] = None,
    posted_at: Optional[str] = None,
    repository_name: Optional[str] = None,
    number: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Persist the confirmed GitHub publication state on its unique PR row."""
    now_str = posted_at or datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        row = await db.fetchrow(
            """
            UPDATE pull_requests
            SET review_posted = 1,
                review_posted_at = $1,
                github_review_id = COALESCE($2, github_review_id)
            WHERE github_pr_id = $3
            RETURNING *
            """,
            now_str,
            review_id,
            github_pr_id,
        )
        if not row:
            return None
        res = dict(row)
        res["draft"] = bool(res["draft"])
        res["merged"] = bool(res["merged"])
        res["review_posted"] = bool(res.get("review_posted", 0))
        return res


async def get_installation_id_for_repo(owner: str, repo: str) -> Optional[int]:
    """Retrieves installation_id for a given owner/repo from database."""
    full_name = f"{owner}/{repo}".lower()
    async with get_db() as db:
        row = await db.fetchrow(
            """
            SELECT i.installation_id
            FROM repositories r
            JOIN installations i ON r.installation_id = i.id
            WHERE LOWER(r.full_name) = $1 LIMIT 1
            """,
            full_name,
        )
        if row and row["installation_id"]:
            return row["installation_id"]
    return None


async def get_repos_for_user(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns all active (disabled=0) repositories across every active installation
    owned by the given user, formatted for the GET /api/repositories response.
    """
    installations = await get_installations_for_user(user_id)
    if not installations:
        return []

    inst_ids = [inst.id for inst in installations]
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM repositories WHERE installation_id = ANY($1) "
            "AND disabled = 0 ORDER BY full_name ASC",
            inst_ids,
        )
        return [
            {
                "id": row["github_repo_id"],
                "name": row["name"],
                "full_name": row["full_name"],
                "private": bool(row["private"]),
                "default_branch": row["default_branch"] or "main",
                "enabled": True,
            }
            for row in rows
        ]
