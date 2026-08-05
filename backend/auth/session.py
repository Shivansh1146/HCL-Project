"""
auth/session.py — Secure signed cookie session management using itsdangerous.

Provides stateless, cryptographically signed session cookies to store user identity safely.
"""
import os
import logging
from typing import Optional, Dict, Any
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger("backend")

# Session Secret Key from env or fallback
SECRET_KEY = os.environ.get("SESSION_SECRET", "hcl_session_secret_key_change_in_production")
SESSION_COOKIE_NAME = "hcl_session"
MAX_AGE_SECONDS = 86400 * 7  # 7 days

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="hcl_auth_session_salt")


def create_session_token(user_id: int, github_id: int, login: str) -> str:
    """Signs user session data into a secure URL-safe token."""
    payload = {
        "user_id": user_id,
        "github_id": github_id,
        "login": login
    }
    return serializer.dumps(payload)


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies and decodes a signed session token.
    Returns payload dict if valid and non-expired; None otherwise.
    """
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=MAX_AGE_SECONDS)
        return data
    except SignatureExpired:
        logger.warning("Session token expired.")
        return None
    except BadSignature:
        logger.warning("Tampered or invalid session token received.")
        return None
    except Exception as e:
        logger.error(f"Error parsing session token: {str(e)}")
        return None
