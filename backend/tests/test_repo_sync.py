"""
tests/test_repo_sync.py — Backend tests for repository synchronisation.

Tests:
 1. sync_repos_in_db inserts new repos.
 2. sync_repos_in_db updates existing repos.
 3. sync_repos_in_db marks removed repos as inactive (disabled=1).
 4. get_repos_for_user returns only active repos in the right shape.
 5. GET /api/repositories returns 401 when unauthenticated.
 6. POST /api/repositories/sync returns 401 when unauthenticated.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

FAKE_REPOS = [
    {
        "id": 111,
        "name": "repo-alpha",
        "full_name": "testuser/repo-alpha",
        "private": False,
        "default_branch": "main",
        "language": "Python",
        "stargazers_count": 5,
        "archived": False,
        "fork": False,
        "owner": {"login": "testuser"},
    },
    {
        "id": 222,
        "name": "repo-beta",
        "full_name": "testuser/repo-beta",
        "private": True,
        "default_branch": "develop",
        "language": "JavaScript",
        "stargazers_count": 0,
        "archived": False,
        "fork": False,
        "owner": {"login": "testuser"},
    },
]


# ---------------------------------------------------------------------------
# 1-3: sync_repos_in_db
# ---------------------------------------------------------------------------

class TestSyncReposInDb:
    """Tests for auth.store.sync_repos_in_db using a real in-memory SQLite DB."""

    def _setup_db(self):
        """Return an async context manager wrapping an aiosqlite in-memory connection."""
        import aiosqlite

        async def _ctx():
            db = await aiosqlite.connect(":memory:")
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    github_repo_id INTEGER UNIQUE NOT NULL,
                    installation_id INTEGER NOT NULL,
                    full_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    owner_login TEXT NOT NULL DEFAULT '',
                    private INTEGER DEFAULT 0,
                    default_branch TEXT DEFAULT 'main',
                    language TEXT,
                    stargazers_count INTEGER DEFAULT 0,
                    archived INTEGER DEFAULT 0,
                    disabled INTEGER DEFAULT 0,
                    fork INTEGER DEFAULT 0,
                    open_pr_count INTEGER DEFAULT 0,
                    reviewed_pr_count INTEGER DEFAULT 0,
                    blocked_pr_count INTEGER DEFAULT 0,
                    last_reviewed_at TEXT,
                    last_synced_at TEXT,
                    sync_status TEXT DEFAULT 'idle',
                    last_sync_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.commit()
            return db

        return _ctx()

    def test_sync_inserts_new_repos(self):
        async def _run():
            from auth.store import sync_repos_in_db
            db = await self._setup_db()
            # Patch get_db to return our in-memory db
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def _fake_get_db():
                yield db

            with patch("auth.store.get_db", _fake_get_db):
                result = await sync_repos_in_db(1, FAKE_REPOS)

            assert len(result) == 2
            names = {r["name"] for r in result}
            assert "repo-alpha" in names
            assert "repo-beta" in names
            await db.close()

        asyncio.run(_run())

    def test_sync_updates_existing_repo(self):
        async def _run():
            from auth.store import sync_repos_in_db
            from contextlib import asynccontextmanager

            db = await self._setup_db()

            @asynccontextmanager
            async def _fake_get_db():
                yield db

            # Insert once
            with patch("auth.store.get_db", _fake_get_db):
                await sync_repos_in_db(1, [FAKE_REPOS[0]])

            # Update with changed branch
            updated = {**FAKE_REPOS[0], "default_branch": "release"}
            with patch("auth.store.get_db", _fake_get_db):
                result = await sync_repos_in_db(1, [updated])

            assert result[0]["default_branch"] == "release"
            await db.close()

        asyncio.run(_run())

    def test_sync_marks_removed_repos_inactive(self):
        async def _run():
            from auth.store import sync_repos_in_db
            from contextlib import asynccontextmanager

            db = await self._setup_db()

            @asynccontextmanager
            async def _fake_get_db():
                yield db

            # First sync: two repos
            with patch("auth.store.get_db", _fake_get_db):
                await sync_repos_in_db(1, FAKE_REPOS)

            # Second sync: only one repo — the other must become disabled
            with patch("auth.store.get_db", _fake_get_db):
                result = await sync_repos_in_db(1, [FAKE_REPOS[0]])

            assert len(result) == 1
            assert result[0]["github_repo_id"] == 111

            # Confirm the removed repo is disabled in the DB
            async with db.execute(
                "SELECT disabled FROM repositories WHERE github_repo_id = 222"
            ) as cur:
                row = await cur.fetchone()
            assert row["disabled"] == 1
            await db.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4: get_repos_for_user shape check
# ---------------------------------------------------------------------------

class TestGetReposForUser:
    def test_returns_correct_shape(self):
        async def _run():
            from auth.store import get_repos_for_user
            from contextlib import asynccontextmanager
            from unittest.mock import patch

            # Fake installation
            fake_inst = MagicMock()
            fake_inst.id = 1

            import aiosqlite

            db = await aiosqlite.connect(":memory:")
            db.row_factory = aiosqlite.Row
            await db.execute("""
                CREATE TABLE repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    github_repo_id INTEGER,
                    installation_id INTEGER,
                    full_name TEXT,
                    name TEXT,
                    owner_login TEXT DEFAULT '',
                    private INTEGER DEFAULT 0,
                    default_branch TEXT DEFAULT 'main',
                    language TEXT,
                    stargazers_count INTEGER DEFAULT 0,
                    archived INTEGER DEFAULT 0,
                    disabled INTEGER DEFAULT 0,
                    fork INTEGER DEFAULT 0,
                    open_pr_count INTEGER DEFAULT 0,
                    reviewed_pr_count INTEGER DEFAULT 0,
                    blocked_pr_count INTEGER DEFAULT 0,
                    last_reviewed_at TEXT,
                    last_synced_at TEXT,
                    sync_status TEXT DEFAULT 'idle',
                    last_sync_error TEXT,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO repositories (github_repo_id, installation_id, full_name, name, "
                "private, default_branch, disabled, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (999, 1, "user/my-repo", "my-repo", 0, "main", 0, now, now),
            )
            await db.commit()

            @asynccontextmanager
            async def _fake_get_db():
                yield db

            with (
                patch("auth.store.get_installations_for_user", AsyncMock(return_value=[fake_inst])),
                patch("auth.store.get_db", _fake_get_db),
            ):
                repos = await get_repos_for_user(user_id=42)

            assert len(repos) == 1
            r = repos[0]
            assert r["id"] == 999
            assert r["name"] == "my-repo"
            assert r["full_name"] == "user/my-repo"
            assert r["private"] is False
            assert r["default_branch"] == "main"
            assert r["enabled"] is True
            await db.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5-6: HTTP endpoint auth guards
# ---------------------------------------------------------------------------

class TestRepoEndpointsAuthGuard:
    """Verify that the repo endpoints require authentication."""

    def test_get_repositories_requires_auth(self):
        import httpx
        res = httpx.get("http://127.0.0.1:8080/api/repositories")
        assert res.status_code == 401

    def test_post_sync_requires_auth(self):
        import httpx
        res = httpx.post("http://127.0.0.1:8080/api/repositories/sync")
        assert res.status_code == 401
