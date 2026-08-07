"""
routers/auth_router.py — FastAPI endpoints for GitHub OAuth & session lifecycle.

Routes:
- GET /auth/login    -> Redirects or returns GitHub OAuth authorization URL
- GET /auth/callback -> Handles GitHub OAuth callback, sets secure session cookie
- GET /auth/me       -> Returns current logged-in user profile
- POST /auth/logout  -> Clears session cookie
"""

import logging
import os
from typing import Any, Optional

import httpx
from auth.dependencies import get_current_user_optional, require_auth
from auth.models import LoginURLResponse, User, UserProfile
from auth.oauth_service import OAuthService, get_oauth_service
from auth.session import MAX_AGE_SECONDS, SESSION_COOKIE_NAME, create_session_token
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger("backend")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/login", response_model=LoginURLResponse)
async def login(
    request: Request,
    redirect: bool = False,
    oauth_service: OAuthService = Depends(get_oauth_service),
):
    """
    Initiates GitHub OAuth flow.
    Returns JSON with authorization URL and state. If redirect=true, redirects browser directly.
    """
    login_info = await oauth_service.prepare_and_store_state(request=request)

    if redirect:
        return RedirectResponse(url=login_info.authorization_url)

    return login_info


@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str,
    oauth_service: OAuthService = Depends(get_oauth_service),
):
    """
    Handles redirect callback from GitHub OAuth.
    Exchanges code for access token, fetches profile, stores user, and sets session cookie.
    """
    try:
        logger.info(
            "OAuth callback: validating state and completing GitHub OAuth exchange."
        )
        user, _ = await oauth_service.handle_callback(code, state, request=request)
        logger.info("OAuth callback: creating session token.")
        session_token = create_session_token(
            user_id=user.id, github_id=user.github_id, login=user.login
        )

        logger.info("OAuth callback: creating redirect response and session cookie.")
        is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
        redirect_res = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        redirect_res.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            max_age=MAX_AGE_SECONDS,
            httponly=True,
            secure=is_prod,
            samesite="lax",
        )

        logger.info("OAuth callback: completed successfully.")
        return redirect_res
    except ValueError as exc:
        logger.warning(
            "OAuth callback rejected: type=%s message=%s",
            type(exc).__name__,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.exception(
            "OAuth callback failed while talking to GitHub: type=%s message=%s",
            type(exc).__name__,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub OAuth exchange failed. Please try signing in again.",
        ) from exc
    except Exception as exc:
        logger.exception(
            "OAuth callback failed: type=%s message=%s",
            type(exc).__name__,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected authentication failure.",
        ) from exc


@router.get("/me", response_model=UserProfile)
async def get_me(user: User = Depends(require_auth)):
    """Returns the authenticated user's profile information."""
    return UserProfile(
        github_id=user.github_id,
        login=user.login,
        name=user.name,
        avatar_url=user.avatar_url,
        email=user.email,
    )


@router.post("/logout")
async def logout(response: Response):
    """Logs out user by clearing the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"status": "success", "message": "Successfully logged out."}


@router.get("/session")
async def get_session(
    user: Optional[User] = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Returns the current session authentication status."""
    if user:
        return {"authenticated": True, "user": {"id": user.id, "login": user.login}}
    return {"authenticated": False, "user": None}


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 50, user: User = Depends(require_auth)
) -> list[dict[str, Any]]:
    """Returns compliance and security audit log entries for the current user."""
    from auth.store import get_audit_logs_for_user

    logs = await get_audit_logs_for_user(user.id, limit=limit)
    return [
        {
            "id": l.id,
            "action": l.action,
            "severity": l.severity.value,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
