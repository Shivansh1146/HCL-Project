"""
auth/oauth_service.py — Service layer handling GitHub OAuth 2.0 flow.

Handles:
1. Authorization URL generation with state parameter for CSRF prevention.
2. Authorization code exchange for user access token.
3. User profile retrieval from GitHub API.
4. User upsert & token persistence.
"""
import os
import secrets
import logging
from typing import Tuple, Dict, Any, Optional
import httpx

from auth.models import User, LoginURLResponse
from auth.store import (
    save_oauth_state,
    pop_oauth_state,
    upsert_user,
    save_oauth_token,
    get_oauth_token,
)

logger = logging.getLogger("backend")

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"


class OAuthService:
    """Encapsulates all GitHub OAuth 2.0 authentication logic."""

    def __init__(self):
        self.client_id = os.getenv("GITHUB_CLIENT_ID", "")
        self.client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
        self.redirect_uri = self._resolve_redirect_uri()

    def _resolve_redirect_uri(self) -> str:
        """Resolve OAuth callback URL from env or sensible local/production defaults."""
        explicit = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "").strip()
        if explicit:
            return explicit

        app_url = os.getenv("APP_URL", "").strip().rstrip("/")
        if app_url:
            return f"{app_url}/auth/callback"

        port = os.getenv("PORT", "8000")
        env = os.getenv("ENVIRONMENT", "").lower()
        if env == "production":
            logger.warning(
                "GITHUB_OAUTH_REDIRECT_URI is not set. "
                "Set GITHUB_OAUTH_REDIRECT_URI or APP_URL in production."
            )
            return ""

        return f"http://localhost:{port}/auth/callback"

    def generate_login_url(self) -> LoginURLResponse:
        """Generates GitHub OAuth login URL with secure random state."""
        state = secrets.token_urlsafe(32)
        scope = "read:user user:email repo"
        url = (
            f"{GITHUB_OAUTH_AUTHORIZE_URL}"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&scope={scope}"
            f"&state={state}"
        )
        return LoginURLResponse(authorization_url=url, state=state)

    async def prepare_and_store_state(self) -> LoginURLResponse:
        """Generates login URL and records state in DB for verification."""
        resp = self.generate_login_url()
        await save_oauth_state(resp.state)
        return resp

    async def handle_callback(self, code: str, state: str) -> Tuple[User, str]:
        """
        Executes complete OAuth callback exchange:
        1. Validates CSRF state
        2. Exchanges code for token
        3. Fetches GitHub user profile
        4. Saves user & token to DB
        Returns (User, access_token) tuple.
        """
        # Validate state
        is_valid_state = await pop_oauth_state(state)
        if not is_valid_state:
            raise ValueError("Invalid or expired OAuth state parameter (CSRF protection triggered).")

        # Exchange code for access token
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                GITHUB_OAUTH_ACCESS_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            if "error" in token_data:
                raise ValueError(f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}")

            access_token = token_data.get("access_token")
            scope = token_data.get("scope", "")
            if not access_token:
                raise ValueError("No access token returned by GitHub.")

            # Fetch User Profile
            user_resp = await client.get(
                GITHUB_USER_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            user_resp.raise_for_status()
            gh_user = user_resp.json()

        github_id = gh_user.get("id")
        login = gh_user.get("login")
        name = gh_user.get("name")
        avatar_url = gh_user.get("avatar_url")
        email = gh_user.get("email")

        # Save or update User in DB
        user = await upsert_user(
            github_id=github_id,
            login=login,
            name=name,
            avatar_url=avatar_url,
            email=email,
        )

        # Save Token
        await save_oauth_token(user_id=user.id, access_token=access_token, scope=scope)

        logger.info(f"User {login} (GitHub ID: {github_id}) logged in successfully via OAuth.")
        return user, access_token


_oauth_service_instance: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    global _oauth_service_instance
    if _oauth_service_instance is None:
        _oauth_service_instance = OAuthService()
    return _oauth_service_instance
