"""
tests/test_oauth_service.py — Unit tests for OAuth & Session management.
"""

from typing import Any, cast

import pytest
from auth.oauth_service import OAuthService
from auth.session import create_session_token, verify_session_token


class _DummyRequest:
    def __init__(self, host: str, proto: str = "https"):
        self.headers = {
            "host": host,
            "x-forwarded-proto": proto,
        }
        self.url = type("URL", (), {"scheme": proto})()


def test_oauth_login_url_uses_request_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv(
        "GITHUB_OAUTH_REDIRECT_URI", "http://127.0.0.1:8080/auth/callback"
    )

    service = OAuthService()
    res = service.generate_login_url(
        request=cast(Any, _DummyRequest("hcl-project-3tgd.onrender.com"))
    )

    assert (
        "redirect_uri=https%3A%2F%2Fhcl-project-3tgd.onrender.com%2Fauth%2Fcallback"
        in res.authorization_url
    )
    assert (
        "redirect_uri=http%3A%2F%2F127.0.0.1%3A8080%2Fauth%2Fcallback"
        not in res.authorization_url
    )


def test_oauth_login_url_generation():
    import os

    os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
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
