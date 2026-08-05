"""
tests/test_oauth_service.py — Unit tests for OAuth & Session management.
"""
import pytest
from auth.oauth_service import OAuthService
from auth.session import create_session_token, verify_session_token


def test_oauth_login_url_generation():
    service = OAuthService()
    res = service.generate_login_url()

    assert res.authorization_url.startswith("https://github.com/login/oauth/authorize")
    assert "state=" in res.authorization_url
    assert len(res.state) > 10


def test_session_token_create_and_verify():
    token = create_session_token(user_id=42, github_id=9999, login="octocat")
    assert isinstance(token, str)

    payload = verify_session_token(token)
    assert payload is not None
    assert payload["user_id"] == 42
    assert payload["github_id"] == 9999
    assert payload["login"] == "octocat"


def test_invalid_session_token():
    assert verify_session_token("invalid_token_string") is None
    assert verify_session_token("") is None
