"""
auth/oauth_service.py — Service layer handling GitHub OAuth 2.0 flow.

Handles:
1. Authorization URL generation with state parameter for CSRF prevention.
2. Authorization code exchange for user access token.
3. User profile retrieval from GitHub API.
4. User upsert & token persistence.
"""

import logging
import os
import secrets
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx
from auth.models import LoginURLResponse, User
from auth.store import pop_oauth_state, save_oauth_state, save_oauth_token, upsert_user
from fastapi import Request

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

    def _resolve_redirect_uri(self, request: Optional[Request] = None) -> str:
        """Resolve OAuth callback URL from the current request or configured defaults."""
        if request is not None:
            forwarded_proto = (
                (
                    request.headers.get("x-forwarded-proto")
                    or request.url.scheme
                    or "https"
                )
                .split(",")[0]
                .strip()
            )
            forwarded_host = (
                (
                    request.headers.get("x-forwarded-host")
                    or request.headers.get("host", "")
                )
                .split(",")[0]
                .strip()
            )
            if forwarded_host:
                return f"{forwarded_proto}://{forwarded_host}/auth/callback"

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

    def _validate_client_id(self) -> None:
        if not self.client_id:
            raise ValueError("GITHUB_CLIENT_ID is not configured.")

    def generate_login_url(self, request: Optional[Request] = None) -> LoginURLResponse:
        """Generates GitHub OAuth login URL with secure random state."""
        self._validate_client_id()
        redirect_uri = self._resolve_redirect_uri(request)
        if not redirect_uri:
            raise ValueError("OAuth redirect URI is not configured.")

        state = secrets.token_urlsafe(32)
        scope = "read:user user:email repo"
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "state": state,
            }
        )
        url = f"{GITHUB_OAUTH_AUTHORIZE_URL}?{query}"
        return LoginURLResponse(authorization_url=url, state=state)

    async def prepare_and_store_state(
        self, request: Optional[Request] = None
    ) -> LoginURLResponse:
        """Generates login URL and records state in DB for verification."""
        resp = self.generate_login_url(request=request)
        await save_oauth_state(resp.state)
        return resp

    async def handle_callback(
        self, code: str, state: str, request: Optional[Request] = None
    ) -> Tuple[User, str]:
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
            raise ValueError(
                "Invalid or expired OAuth state parameter (CSRF protection triggered)."
            )

        self._validate_client_id()
        if not self.client_secret:
            raise ValueError("GITHUB_CLIENT_SECRET is not configured.")

        redirect_uri = self._resolve_redirect_uri(request)
        if not redirect_uri:
            raise ValueError("OAuth redirect URI is not configured.")

        # Exchange code for access token
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                GITHUB_OAUTH_ACCESS_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            if "error" in token_data:
                raise ValueError(
                    f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}"
                )

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

        logger.info(
            "User %s (GitHub ID: %s) logged in successfully via OAuth.",
            login,
            github_id,
        )
        return user, access_token


_oauth_service_instance: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    service = getattr(get_oauth_service, "_instance", None)
    if service is None:
        service = OAuthService()
        setattr(get_oauth_service, "_instance", service)
    return service
