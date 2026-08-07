"""
tests/test_installation_token_cache.py — Unit tests for GitHub App installation token management.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from auth.app_service import GitHubAppService, get_app_service
from auth.dependencies import require_auth
from auth.store import initialize_auth_db, upsert_installation, upsert_user
from fastapi.testclient import TestClient
from main import app


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class DummyClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return self.response

    async def get(self, url, headers=None):
        self.requests.append((url, headers or {}))
        return self.response


def _setup_env(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv(
        "GITHUB_APP_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
    )
    monkeypatch.setenv(
        "GITHUB_APP_INSTALL_URL", "https://github.com/apps/test/installations/new"
    )


def test_installation_token_endpoint_returns_github_response_and_expiry(monkeypatch):
    _setup_env(monkeypatch)

    async def _run():
        await initialize_auth_db()
        user = await upsert_user(101, "token-user")
        installation = await upsert_installation(
            installation_id=555,
            account_login="token-org",
            account_type="Organization",
            target_id=555,
            target_type="Organization",
            user_id=user.id,
        )

        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = {"token": "ghs_cached_token", "expires_at": expires_at.isoformat()}

        with (
            patch(
                "auth.app_service.httpx.AsyncClient",
                return_value=DummyClient(DummyResponse(payload)),
            ),
            patch(
                "auth.app_service.GitHubAppService.generate_app_jwt",
                return_value="jwt-token",
            ),
        ):
            service = GitHubAppService()
            result = await service.create_installation_access_token_response(
                installation.installation_id
            )

        assert result.token == "ghs_cached_token"
        assert result.expires_at.isoformat() == expires_at.isoformat()
        assert result.github_response["expires_at"] == expires_at.isoformat()
        assert result.github_response["token_type"] == "installation"

    asyncio.run(_run())


def test_installation_token_cache_reuses_token_until_invalidated(monkeypatch):
    _setup_env(monkeypatch)

    calls = []

    async def fetcher(installation_id: int):
        calls.append(installation_id)
        return (
            f"tok-{len(calls)}",
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

    from auth.token_cache import InstallationTokenCache

    cache = InstallationTokenCache(fetch_fn=fetcher)

    async def _run():
        first = await cache.get_token(99)
        second = await cache.get_token(99)
        assert first == second
        assert len(calls) == 1

        cache.invalidate(99)
        third = await cache.get_token(99)
        assert third != first
        assert len(calls) == 2

    asyncio.run(_run())


def test_installation_token_cache_retries_transient_failures(monkeypatch):
    _setup_env(monkeypatch)

    attempts = {"count": 0}

    async def fetcher(installation_id: int):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary GitHub failure")
        return (
            "tok-final",
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

    from auth.token_cache import InstallationTokenCache

    cache = InstallationTokenCache(fetch_fn=fetcher)

    async def _run():
        token = await cache.get_token(101)
        assert token == "tok-final"
        assert attempts["count"] == 3

    asyncio.run(_run())


def test_installation_token_endpoint_serves_authenticated_user(monkeypatch):
    _setup_env(monkeypatch)

    async def _run():
        await initialize_auth_db()
        user = await upsert_user(202, "endpoint-user")
        installation = await upsert_installation(
            installation_id=777,
            account_login="endpoint-org",
            account_type="Organization",
            target_id=777,
            target_type="Organization",
            user_id=user.id,
        )

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        payload = {"token": "ghs_endpoint", "expires_at": expires_at.isoformat()}

        with (
            patch(
                "auth.app_service.httpx.AsyncClient",
                return_value=DummyClient(DummyResponse(payload)),
            ),
            patch(
                "auth.app_service.GitHubAppService.generate_app_jwt",
                return_value="jwt-token",
            ),
            patch(
                "auth.store.get_installation_by_id",
                return_value=installation,
            ),
        ):
            app.dependency_overrides[require_auth] = lambda: user
            app.dependency_overrides[get_app_service] = GitHubAppService
            client = TestClient(app)
            response = client.post(
                f"/app/installations/{installation.installation_id}/access_tokens"
            )
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["token"] == "ghs_endpoint"
        assert body["expires_at_iso"] == expires_at.isoformat()
        assert body["github_response"]["expires_at"] == expires_at.isoformat()

    asyncio.run(_run())


def test_list_installation_repos_uses_installation_endpoint(monkeypatch):
    _setup_env(monkeypatch)

    async def _run():
        payload = {
            "repositories": [
                {
                    "id": 101,
                    "full_name": "org/repo-a",
                    "name": "repo-a",
                    "private": False,
                    "default_branch": "main",
                    "owner": {"login": "org"},
                }
            ]
        }
        dummy_client = DummyClient(DummyResponse(payload))

        with (
            patch("auth.app_service.httpx.AsyncClient", return_value=dummy_client),
            patch(
                "auth.app_service.GitHubAppService.get_installation_access_token",
                return_value="installation-token",
            ),
        ):
            service = GitHubAppService()
            repos = await service.list_installation_repos(
                123, user_access_token="user-token"
            )

        assert repos[0]["id"] == 101
        assert repos[0]["repo_id"] == 101
        assert any(
            "/installation/repositories" in url for url, _ in dummy_client.requests
        )
        assert not any(
            "/user/installations/" in url for url, _ in dummy_client.requests
        )

    asyncio.run(_run())
