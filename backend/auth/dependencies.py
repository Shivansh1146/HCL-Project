"""
auth/dependencies.py — FastAPI dependency functions for authentication & authorization.

Provides:
1. get_current_user_optional: Returns User model if valid session cookie exists; else None.
2. require_auth: Enforces authenticated session; raises 401 Unauthorized if missing.
"""
from typing import Optional
from fastapi import Request, HTTPException, status, Depends

from auth.models import User
from auth.session import SESSION_COOKIE_NAME, verify_session_token
from auth.store import get_user_by_id


async def get_current_user_optional(request: Request) -> Optional[User]:
    """Retrieves authenticated user from session cookie if present."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Also check Authorization header for Bearer session token option
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        return None

    session_data = verify_session_token(token)
    if not session_data:
        return None

    user_id = session_data.get("user_id")
    if not user_id:
        return None

    return await get_user_by_id(user_id)


async def require_auth(user: Optional[User] = Depends(get_current_user_optional)) -> User:
    """Dependency that mandates an authenticated session."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in with GitHub.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
