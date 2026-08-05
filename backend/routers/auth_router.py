"""
routers/auth_router.py — FastAPI endpoints for GitHub OAuth & session lifecycle.

Routes:
- GET /auth/login    -> Redirects or returns GitHub OAuth authorization URL
- GET /auth/callback -> Handles GitHub OAuth callback, sets secure session cookie
- GET /auth/me       -> Returns current logged-in user profile
- POST /auth/logout  -> Clears session cookie
"""
import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse

from auth.models import LoginURLResponse, UserProfile, User
from auth.oauth_service import get_oauth_service, OAuthService
from auth.session import create_session_token, SESSION_COOKIE_NAME, MAX_AGE_SECONDS
from auth.dependencies import get_current_user_optional, require_auth

logger = logging.getLogger("backend")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/login", response_model=LoginURLResponse)
async def login(
    redirect: bool = False,
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """
    Initiates GitHub OAuth flow.
    Returns JSON with authorization URL and state. If redirect=true, redirects browser directly.
    """
    login_info = await oauth_service.prepare_and_store_state()

    if redirect:
        return RedirectResponse(url=login_info.authorization_url)

    return login_info


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    response: Response,
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """
    Handles redirect callback from GitHub OAuth.
    Exchanges code for access token, fetches profile, stores user, and sets session cookie.
    """
    try:
        user, _ = await oauth_service.handle_callback(code, state)
    except ValueError as e:
        logger.warning(f"OAuth Callback validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during OAuth callback: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth authentication failed due to an internal error."
        )

    session_token = create_session_token(
        user_id=user.id,
        github_id=user.github_id,
        login=user.login
    )

    # Set secure HttpOnly session cookie
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    redirect_res = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    redirect_res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        secure=is_prod,
        samesite="lax"
    )

    return redirect_res


@router.get("/me", response_model=UserProfile)
async def get_me(user: User = Depends(require_auth)):
    """Returns the authenticated user's profile information."""
    return UserProfile(
        github_id=user.github_id,
        login=user.login,
        name=user.name,
        avatar_url=user.avatar_url,
        email=user.email
    )


@router.post("/logout")
async def logout(response: Response):
    """Logs out user by clearing the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"status": "success", "message": "Successfully logged out."}


@router.get("/session")
async def get_session(user: Optional[User] = Depends(get_current_user_optional)):
    """Returns the current session authentication status."""
    if user:
        return {"authenticated": True, "user": {"id": user.id, "login": user.login}}
    return {"authenticated": False, "user": None}


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 50,
    user: User = Depends(require_auth)
):
    """Returns compliance and security audit log entries for the current user."""
    from auth.store import get_audit_logs_for_user
    logs = await get_audit_logs_for_user(user.id, limit=limit)
    return [
        {
            "id": l.id,
            "action": l.action,
            "severity": l.severity.value,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]
