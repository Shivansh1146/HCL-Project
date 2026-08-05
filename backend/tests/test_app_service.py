"""
tests/test_app_service.py — Unit tests for GitHub App JWT & Repo Selection logic.
"""

import pytest
from auth.app_service import GitHubAppService
from pytest import MonkeyPatch


def test_app_jwt_fallback_when_unconfigured():
    service = GitHubAppService()
    jwt_token = service.generate_app_jwt()
    # Unconfigured app_id/key returns empty string safely without crashing
    assert jwt_token == ""


def test_install_url_is_derived_from_app_name(monkeypatch: MonkeyPatch):
    monkeypatch.delenv("GITHUB_APP_INSTALL_URL", raising=False)
    monkeypatch.delenv("GITHUB_APP_SLUG", raising=False)
    monkeypatch.setenv("GITHUB_APP_NAME", "HCL AI Code Reviewer")

    service = GitHubAppService()

    assert (
        service.get_installation_url()
        == "https://github.com/apps/hcl-ai-code-reviewer/installations/new"
    )
    assert service.has_install_url() is True


def test_explicit_install_url_takes_priority(monkeypatch: MonkeyPatch):
    monkeypatch.setenv(
        "GITHUB_APP_INSTALL_URL", "https://github.com/apps/custom/installations/new"
    )
    monkeypatch.setenv("GITHUB_APP_NAME", "Something Else")

    service = GitHubAppService()

    assert (
        service.get_installation_url()
        == "https://github.com/apps/custom/installations/new"
    )
