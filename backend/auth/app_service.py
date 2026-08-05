"""
auth/app_service.py — Service layer handling GitHub App API operations.

Features:
1. Generates GitHub App JWTs for app-authenticated calls.
2. Generates installation access tokens for repository operations.
3. Fetches user/org accessible installations.
4. Lists all accessible repositories across installations/organizations.
5. Manages repository selections per installation.
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
import jwt  # PyJWT
from auth.models import AccountType, Installation, InstallationStatus, SelectedRepo
from auth.token_cache import InstallationTokenCache, TokenStatus
from auth.store import (
    get_installation_by_id,
    get_installations_for_user,
    get_selected_repos_for_installation,
    save_selected_repos,
    sync_repos_in_db,
    upsert_installation,
)

logger = logging.getLogger("backend")

GITHUB_API_BASE = "https://api.github.com"


class GitHubAppService:
    """Service encapsulating GitHub App functionality and installation tokens."""

    def __init__(self):
        self.app_id = os.getenv("GITHUB_APP_ID", "")
        self.private_key_path = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
        self.private_key_raw = os.getenv(
            "GITHUB_APP_PRIVATE_KEY", os.getenv("GITHUB_PRIVATE_KEY", "")
        )
        self.app_slug = os.getenv("GITHUB_APP_SLUG", "").strip()
        self.app_name = os.getenv("GITHUB_APP_NAME", "").strip()
        self.install_url = os.getenv("GITHUB_APP_INSTALL_URL", "").strip()

        # Initialise the token cache — bound to this service's fetch function
        self._token_cache = InstallationTokenCache(
            fetch_fn=self._fetch_token_from_github
        )

        logger.info(
            "GitHubAppService initialised. app_id=%s configured=%s",
            self.app_id or "(none)",
            self.has_app_credentials(),
        )

    def get_installation_url(self) -> str:
        """Return the GitHub installation page configured for this App."""
        if self.install_url:
            return self.install_url
        if self.app_slug:
            return f"https://github.com/apps/{self.app_slug}/installations/new"
        if self.app_name:
            derived_slug = re.sub(r"[^a-z0-9]+", "-", self.app_name.lower()).strip("-")
            if derived_slug:
                return f"https://github.com/apps/{derived_slug}/installations/new"
        return ""

    def has_app_credentials(self) -> bool:
        """Whether the credentials needed for GitHub App JWT calls are present."""
        return bool(self.app_id and self._get_private_key())

    def has_install_url(self) -> bool:
        """Whether we can construct an installation URL for onboarding."""
        return bool(self.get_installation_url())

    def is_configured(self) -> bool:
        """Compatibility helper used by existing callers."""
        return self.has_app_credentials()

    async def sync_installations_from_github_app(
        self, user_id: Optional[int] = None
    ) -> List[Installation]:
        """Sync installations directly from the GitHub App API using an app JWT."""
        app_jwt = self.generate_app_jwt()
        if not app_jwt:
            return await get_installations_for_user(user_id) if user_id else []

        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/app/installations", headers=headers
            )
            if resp.status_code != 200:
                logger.warning(
                    "Unable to list GitHub App installations: %s", resp.status_code
                )
                return await get_installations_for_user(user_id) if user_id else []
            records = resp.json()

        synced: List[Installation] = []
        for record in records:
            account = record.get("account") or {}
            synced.append(
                await upsert_installation(
                    installation_id=record["id"],
                    account_login=account.get("login", "unknown"),
                    account_type=account.get("type", "User"),
                    target_id=record.get("target_id", account.get("id", 0)),
                    target_type=record.get("target_type", account.get("type", "User")),
                    user_id=user_id,
                    status="active" if not record.get("suspended_at") else "suspended",
                )
            )
        return synced

    def get_configuration_issues(self) -> list[str]:
        """Returns the missing settings that block GitHub App onboarding or JWT access."""
        issues: list[str] = []
        if not self.app_id:
            issues.append("GITHUB_APP_ID")
        if not self._get_private_key():
            issues.append("GITHUB_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY")
        if not self.has_install_url():
            issues.append("GITHUB_APP_INSTALL_URL, GITHUB_APP_SLUG, or GITHUB_APP_NAME")
        return issues

    def _get_private_key(self) -> str:
        """Loads RSA private key string from raw env var or file path."""
        if self.private_key_raw:
            return self.private_key_raw.replace("\\n", "\n")
        if self.private_key_path and os.path.exists(self.private_key_path):
            with open(self.private_key_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def generate_app_jwt(self) -> str:
        """Generates a RS256 JWT signed with the GitHub App's private key valid for 10 minutes."""
        pk = self._get_private_key()
        if not pk or not self.app_id:
            logger.warning(
                "GITHUB_APP_ID or private key not configured; fallback mode active."
            )
            return ""

        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + (10 * 60), "iss": self.app_id}
        try:
            return jwt.encode(payload, pk, algorithm="RS256")
        except Exception as e:
            logger.warning(f"Failed to generate GitHub App JWT: {str(e)}")
            return ""

    async def get_installation_access_token(self, installation_id: int) -> str:
        """
        Return a valid installation access token.

        Uses the InstallationTokenCache:
          - Returns a cached token if it won't expire within 5 minutes.
          - Otherwise fetches a fresh token from GitHub (with retry).
          - Serializes concurrent requests for the same installation.
        Falls back to GITHUB_TOKEN env var when JWT credentials are absent.
        """
        if not self.has_app_credentials():
            fallback = os.getenv("GITHUB_TOKEN", "")
            if fallback:
                logger.warning(
                    "[TokenCache] No app credentials — using GITHUB_TOKEN fallback "
                    "for installation %d.",
                    installation_id,
                )
            return fallback

        try:
            return await self._token_cache.get_token(installation_id)
        except RuntimeError as exc:
            logger.error(
                "[TokenCache] Could not obtain token for installation %d: %s",
                installation_id,
                str(exc),
            )
            return ""

    async def _fetch_token_from_github(
        self, installation_id: int
    ) -> tuple[str, str]:
        """
        Low-level fetcher called exclusively by InstallationTokenCache.

        Calls POST /app/installations/{id}/access_tokens with a fresh JWT.
        Returns (token_string, expires_at_iso_string).
        Raises httpx.HTTPStatusError on non-2xx responses so the cache
        can retry transient failures.
        """
        app_jwt = self.generate_app_jwt()
        if not app_jwt:
            raise RuntimeError(
                "Cannot generate GitHub App JWT — check GITHUB_APP_ID and private key."
            )

        url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()   # raises HTTPStatusError on 4xx/5xx

        data = resp.json()
        token_str = data.get("token", "")
        expires_at = data.get("expires_at", "")  # e.g. "2024-01-01T02:00:00Z"

        if not token_str:
            raise ValueError(
                f"GitHub API returned empty token for installation {installation_id}."
            )

        logger.info(
            "[TokenCache] GitHub issued token for installation %d  expires_at=%s",
            installation_id,
            expires_at,
        )
        return token_str, expires_at

    def get_token_status(self, installation_id: int) -> TokenStatus:
        """
        Return diagnostic cache status for a given installation.
        Never makes a network request — safe to call at any time.
        """
        return self._token_cache.token_status(installation_id)

    def invalidate_token(self, installation_id: int) -> None:
        """Force the next call to get_installation_access_token to fetch a fresh token."""
        self._token_cache.invalidate(installation_id)

    async def sync_installation_from_github(
        self, installation_id: int, user_id: Optional[int] = None
    ) -> Optional[Installation]:
        """Fetches installation metadata directly from GitHub App API and syncs to DB."""
        app_jwt = self.generate_app_jwt()
        if not app_jwt:
            return None

        url = f"{GITHUB_API_BASE}/app/installations/{installation_id}"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(
                    "sync_installation_from_github: GET %s returned %s",
                    url, resp.status_code,
                )
                return None
            data = resp.json()

        account = data.get("account", {})
        inst = await upsert_installation(
            installation_id=data["id"],
            account_login=account.get("login", "unknown"),
            account_type=account.get("type", "User"),
            target_id=data.get("target_id", account.get("id", 0)),
            target_type=data.get("target_type", account.get("type", "User")),
            user_id=user_id,
            status="active" if not data.get("suspended_at") else "suspended",
        )
        return inst

    async def list_installation_repos(
        self, installation_id: int, user_access_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists all repositories accessible to an installation.
        Uses user OAuth token or installation token as available.
        """
        if user_access_token:
            token = user_access_token
            url = f"{GITHUB_API_BASE}/user/installations/{installation_id}/repositories"
        else:
            token = await self.get_installation_access_token(installation_id)
            url = f"{GITHUB_API_BASE}/installation/repositories"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(
                    "Failed to fetch repos for installation %d: %s",
                    installation_id, resp.text,
                )
                return []
            data = resp.json()
            return data.get("repositories", [])

    async def sync_user_installations(
        self, user_id: int, user_access_token: str
    ) -> List[Installation]:
        """Sync all GitHub App installations visible to the authenticated user."""
        if not user_access_token:
            return await get_installations_for_user(user_id)

        headers = {
            "Authorization": f"Bearer {user_access_token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user/installations", headers=headers
            )
            if response.status_code != 200:
                logger.warning(
                    "Unable to synchronize GitHub App installations: %s",
                    response.status_code,
                )
                return await get_installations_for_user(user_id)
            records = response.json().get("installations", [])

        synced = []
        for record in records:
            account = record.get("account") or {}
            synced.append(
                await upsert_installation(
                    installation_id=record["id"],
                    account_login=account.get("login", "unknown"),
                    account_type=account.get("type", "User"),
                    target_id=record.get("target_id", account.get("id", 0)),
                    target_type=record.get("target_type", account.get("type", "User")),
                    user_id=user_id,
                    status="active" if not record.get("suspended_at") else "suspended",
                )
            )
        return synced

    async def update_selected_repositories(
        self, installation_id: int, repo_full_names: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Saves repository selections for an installation.
        Returns (enabled_repos, disabled_repos) lists.
        """
        inst = await get_installation_by_id(installation_id)
        if not inst:
            raise ValueError(f"Installation {installation_id} not found in database.")

        # Fetch accessible repos to get numeric IDs and validate input
        accessible_repos = await self.list_installation_repos(installation_id)
        repo_dict = {
            r["full_name"].lower(): (r["full_name"], r["id"]) for r in accessible_repos
        }

        selected_tuples: List[Tuple[str, int]] = []
        enabled_list: List[str] = []

        for name in repo_full_names:
            key = name.lower()
            if key in repo_dict:
                exact_name, repo_id = repo_dict[key]
                selected_tuples.append((exact_name, repo_id))
                enabled_list.append(exact_name)
            else:
                # If exact ID not returned from API API list, store fallback ID 0
                selected_tuples.append((name, 0))
                enabled_list.append(name)

        await save_selected_repos(inst.id, selected_tuples)

        all_known = [r["full_name"] for r in accessible_repos]
        disabled_list = [r for r in all_known if r not in enabled_list]

        return enabled_list, disabled_list

    async def sync_all_repositories(self, user_id: int) -> List[Dict[str, Any]]:
        """
        For every active installation belonging to user_id:
          1. Obtain an installation access token.
          2. Call GET /installation/repositories (paginates automatically).
          3. Upsert all repos into DB; mark removed ones disabled=1.
        Returns the combined list of active repos formatted for /api/repositories.
        """
        installations = await get_installations_for_user(user_id)
        all_repos: List[Dict[str, Any]] = []

        for inst in installations:
            # --- 1. Get installation access token ---
            token = await self.get_installation_access_token(inst.installation_id)
            if not token:
                logger.warning(
                    "No installation token for installation %s – skipping.",
                    inst.installation_id,
                )
                continue

            # --- 2. Paginate GET /installation/repositories ---
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            }
            github_repos: List[Dict[str, Any]] = []
            url = f"{GITHUB_API_BASE}/installation/repositories?per_page=100"

            async with httpx.AsyncClient(timeout=15.0) as client:
                while url:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        logger.error(
                            "GET %s returned %s: %s",
                            url,
                            resp.status_code,
                            resp.text[:200],
                        )
                        break
                    data = resp.json()
                    github_repos.extend(data.get("repositories", []))
                    # Follow Link header for next page
                    link_header = resp.headers.get("Link", "")
                    next_url = None
                    for part in link_header.split(","):
                        if 'rel="next"' in part:
                            match = re.search(r"<([^>]+)>", part)
                            if match:
                                next_url = match.group(1)
                    url = next_url

            # --- 3. Sync to DB ---
            db_rows = await sync_repos_in_db(inst.id, github_repos)
            all_repos.extend(
                [
                    {
                        "id": row["github_repo_id"],
                        "name": row["name"],
                        "full_name": row["full_name"],
                        "private": bool(row["private"]),
                        "default_branch": row["default_branch"] or "main",
                        "enabled": True,
                    }
                    for row in db_rows
                ]
            )
            logger.info(
                "Synced %d repos for installation %s.",
                len(github_repos),
                inst.installation_id,
            )

        return all_repos




_app_service_instance: Optional[GitHubAppService] = None


def get_app_service() -> GitHubAppService:
    global _app_service_instance
    if _app_service_instance is None:
        _app_service_instance = GitHubAppService()
    return _app_service_instance
