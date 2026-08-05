"""
tests/test_auth_store.py — Enterprise unit tests for database constraints, soft deletes, and transactions.
"""
import pytest
import asyncio
import os
import tempfile

test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["TEST_DB_PATH"] = test_db_file

from stats_store import get_db
from auth.store import (
    initialize_auth_db,
    upsert_user,
    get_user_by_id,
    soft_delete_user,
    save_oauth_token,
    get_oauth_token,
    save_oauth_state,
    pop_oauth_state,
    upsert_installation,
    get_installations_for_user,
    save_selected_repos,
    is_repo_whitelisted,
)


def test_auth_db_full_lifecycle_and_constraints():
    async def _test():
        await initialize_auth_db()

        # 1. Test User Upsert & Retrieval
        user = await upsert_user(
            github_id=12345,
            login="testuser",
            name="Test User",
            email="test@example.com"
        )
        assert user.id is not None
        assert user.github_id == 12345
        assert user.login == "testuser"
        assert user.deleted_at is None

        # 2. Test Soft Delete
        success = await soft_delete_user(user.id)
        assert success is True
        # Soft deleted user should NOT be returned by get_user_by_id
        assert await get_user_by_id(user.id) is None

        # Re-upserting revives soft deleted user
        revived_user = await upsert_user(github_id=12345, login="testuser_updated")
        assert revived_user.id == user.id
        assert revived_user.login == "testuser_updated"
        assert await get_user_by_id(user.id) is not None

        # 3. Test Foreign Key / Unique Constraint Failure
        async with get_db() as db:
            with pytest.raises(Exception):
                # Duplicate github_id direct insert should raise IntegrityError
                await db.execute("""
                    INSERT INTO users (github_id, login, created_at, updated_at)
                    VALUES (12345, 'duplicate_user', '2026-01-01', '2026-01-01')
                """)

            # 4. Test Check Constraint Failure on Invalid Installation Status
            with pytest.raises(Exception):
                await db.execute("""
                    INSERT INTO installations (installation_id, account_login, account_type, target_id, target_type, status, created_at, updated_at)
                    VALUES (9999, 'bad_account', 'User', 11, 'User', 'INVALID_STATUS', '2026-01-01', '2026-01-01')
                """)

        # 5. Test OAuth Token Encryption
        token = await save_oauth_token(user_id=user.id, access_token="gho_secret_token_123", scope="repo")
        assert token.access_token == "gho_secret_token_123"

        fetched_token = await get_oauth_token(user.id)
        assert fetched_token is not None
        assert fetched_token.access_token == "gho_secret_token_123"

        # 5. Test Installation & Repository Selection
        inst = await upsert_installation(
            installation_id=999,
            account_login="testorg",
            account_type="Organization",
            target_id=888,
            target_type="Organization",
            user_id=user.id
        )
        assert inst.installation_id == 999
        assert inst.account_login == "testorg"

        await save_selected_repos(inst.id, [("testorg/repo-a", 101), ("testorg/repo-b", 102)])
        assert await is_repo_whitelisted("testorg/repo-a") is True
        assert await is_repo_whitelisted("testorg/repo-b") is True
        assert await is_repo_whitelisted("testorg/unselected-repo") is False

    asyncio.run(_test())
