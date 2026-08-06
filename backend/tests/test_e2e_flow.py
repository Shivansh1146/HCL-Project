"""
tests/test_e2e_flow.py — End-to-End Integration Test for the Full PR Lifecycle.

Simulates the complete flow:
  Stage 1:  GitHub OAuth Login          → User record created in DB
  Stage 2:  Dashboard                   → /api/health responds 200
  Stage 3:  GitHub App Installed        → Installation record exists
  Stage 4:  Repository Sync             → Repository record upserted in DB
  Stage 5:  Open Pull Request on GitHub → Simulated via webhook
  Stage 6:  GitHub Webhook Delivered    → POST /api/webhooks/github with HMAC sig
  Stage 7:  Webhook Verification        → Signature verified, payload parsed
  Stage 8:  Database Updated            → PR row upserted in pull_requests table
  Stage 9:  PR Appears in Dashboard     → GET /api/prs/stats returns correct counts
"""

import asyncio
import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from auth.store import (
    upsert_user,
    get_pull_request,
    get_pr_stats,
    initialize_auth_db,
    upsert_installation,
    sync_repos_in_db,
)
from main import app

# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────
WEBHOOK_SECRET  = "e2e_test_secret_phase_1_7"
TEST_USER_LOGIN = "e2e_test_user"
TEST_INSTALL_ID = 99901
TEST_REPO_ID    = 88801
TEST_REPO_NAME  = "e2e_test_user/e2e-test-repo"
TEST_PR_NUMBER  = 201
TEST_PR_TITLE   = "feat: E2E test pull request"
TEST_PR_ID      = 999201


def _make_signature(payload_bytes: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), msg=payload_bytes, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _make_pr_payload(action: str, state: str = "open",
                     merged: bool = False, draft: bool = False) -> dict:
    return {
        "action": action,
        "number": TEST_PR_NUMBER,
        "pull_request": {
            "id": TEST_PR_ID,
            "number": TEST_PR_NUMBER,
            "title": TEST_PR_TITLE,
            "body": "E2E test PR submitted via simulated GitHub webhook.",
            "state": state,
            "draft": draft,
            "merged": merged,
            "merged_at": "2026-08-07T03:00:00Z" if merged else None,
            "closed_at": "2026-08-07T03:00:00Z" if state == "closed" else None,
            "user": {
                "login": TEST_USER_LOGIN,
                "avatar_url": "https://avatars.githubusercontent.com/u/12345678"
            },
            "head": {
                "ref": "feature/e2e-test",
                "sha": "abc123def456abc123def456abc123def456abc1"
            },
            "base": {
                "ref": "main",
                "sha": "000000def456abc123def456abc123def456abc0"
            },
            "html_url": f"https://github.com/{TEST_REPO_NAME}/pull/{TEST_PR_NUMBER}",
            "url":      f"https://api.github.com/repos/{TEST_REPO_NAME}/pulls/{TEST_PR_NUMBER}",
            "additions": 120,
            "deletions": 35,
            "changed_files": 7,
            "commits": 4,
            "labels": [{"name": "enhancement"}, {"name": "phase-1.7"}],
            "requested_reviewers": [{"login": "reviewer_alice"}],
            "created_at": "2026-08-07T00:00:00Z",
            "updated_at": "2026-08-07T01:00:00Z",
        },
        "repository": {
            "id": TEST_REPO_ID,
            "name": "e2e-test-repo",
            "full_name": TEST_REPO_NAME,
            "owner": {"login": "e2e_test_user"},
            "private": False,
        },
        "sender": {"login": TEST_USER_LOGIN},
    }


# ─────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────

def setup_module(module):
    asyncio.run(initialize_auth_db())


# ─────────────────────────────────────────────────────────
# Stage 1 — GitHub Login: User Created in DB
# ─────────────────────────────────────────────────────────

def test_stage1_user_record_created():
    """Stage 1: OAuth login creates/upserts user record in database."""
    async def _run():
        user = await upsert_user(
            github_id=9900001,
            login=TEST_USER_LOGIN,
            name="E2E Test User",
            email="e2e@test.example.com",
            avatar_url="https://avatars.githubusercontent.com/u/9900001",
        )
        assert user is not None
        assert user.login == TEST_USER_LOGIN
        assert user.github_id == 9900001
    asyncio.run(_run())


# ─────────────────────────────────────────────────────────
# Stage 2 — Dashboard: Health Check
# ─────────────────────────────────────────────────────────

def test_stage2_health_check_returns_200():
    """Stage 2: Dashboard health endpoint confirms server is alive."""
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in ("ok", "healthy", "connected")


# ─────────────────────────────────────────────────────────
# Stage 3 — GitHub App Installed: Installation Upserted
# ─────────────────────────────────────────────────────────

def test_stage3_installation_upserted():
    """Stage 3: GitHub App installation record is created in database."""
    async def _run():
        inst = await upsert_installation(
            installation_id=TEST_INSTALL_ID,
            account_login=TEST_USER_LOGIN,
            account_type="User",
            target_id=9900001,
            target_type="User",
            user_id=None,
            status="active",
        )
        assert inst is not None
        assert inst.installation_id == TEST_INSTALL_ID
    asyncio.run(_run())


# ─────────────────────────────────────────────────────────
# Stage 4 — Repository Sync: Repo Upserted
# ─────────────────────────────────────────────────────────

def test_stage4_repository_synced():
    """Stage 4: Repository sync stores repo record linked to installation."""
    async def _run():
        now = "2026-08-07T00:00:00Z"
        repos_payload = [{
            "id": TEST_REPO_ID,
            "name": "e2e-test-repo",
            "full_name": TEST_REPO_NAME,
            "owner": {"login": TEST_USER_LOGIN},
            "private": False,
            "default_branch": "main",
            "language": "Python",
            "description": "E2E test repository",
            "fork": False,
            "archived": False,
            "disabled": False,
            "created_at": now,
            "updated_at": now,
        }]
        result = await sync_repos_in_db(TEST_INSTALL_ID, repos_payload)
        assert result is not None
        assert len(result) >= 1
        assert any(r["full_name"] == TEST_REPO_NAME for r in result)
    asyncio.run(_run())


# ─────────────────────────────────────────────────────────
# Stage 5+6+7 — PR Opened → Webhook Delivered → Verified
# ─────────────────────────────────────────────────────────

def test_stage5_6_7_webhook_delivered_and_verified(monkeypatch):
    """
    Stage 5: Pull Request opened on GitHub.
    Stage 6: GitHub delivers webhook to POST /api/webhooks/github.
    Stage 7: HMAC-SHA256 signature is verified before processing.
    """
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)

    payload       = _make_pr_payload("opened")
    payload_bytes = json.dumps(payload).encode("utf-8")
    delivery_id   = str(uuid.uuid4())

    client = TestClient(app)
    resp = client.post(
        "/api/webhooks/github",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": _make_signature(payload_bytes, WEBHOOK_SECRET),
            "X-GitHub-Event":      "pull_request",
            "X-GitHub-Delivery":   delivery_id,
            "Content-Type":        "application/json",
        },
    )

    assert resp.status_code == 200, f"Webhook rejected: {resp.text}"
    data = resp.json()
    assert data["status"] == "processed"
    assert data["event"]  == "pull_request"
    assert data["action"] == "opened"
    assert data["pr_number"] == TEST_PR_NUMBER


# ─────────────────────────────────────────────────────────
# Stage 8 — Database Updated: Full PR Metadata Persisted
# ─────────────────────────────────────────────────────────

def test_stage8_pr_persisted_in_database():
    """Stage 8: After webhook, all PR metadata is in pull_requests table."""
    async def _run():
        pr = await get_pull_request(TEST_PR_NUMBER, TEST_REPO_NAME)
        assert pr is not None,              "PR not found in DB after webhook"
        assert pr["title"]        == TEST_PR_TITLE
        assert pr["state"]        == "open"
        assert pr["merged"]       is False
        assert pr["draft"]        is False
        assert pr["author_login"] == TEST_USER_LOGIN
        assert pr["head_sha"]     == "abc123def456abc123def456abc123def456abc1"
        assert pr["head_branch"]  == "feature/e2e-test"
        assert pr["base_branch"]  == "main"
        assert pr["additions"]    == 120
        assert pr["deletions"]    == 35
        assert pr["changed_files"] == 7
        assert pr["commits"]      == 4
        assert "enhancement"      in pr["labels"]
        assert "phase-1.7"        in pr["labels"]
        assert "reviewer_alice"   in pr["requested_reviewers"]
    asyncio.run(_run())


# ─────────────────────────────────────────────────────────
# Stage 9 — PR Appears in Dashboard: Stats API
# ─────────────────────────────────────────────────────────

def test_stage9_pr_stats_updated():
    """Stage 9: PR Dashboard /api/prs/stats shows at least 1 open PR."""
    async def _run():
        stats = await get_pr_stats()
        assert stats["total"] >= 1,  f"Expected total>=1, got {stats}"
        assert stats["open"]  >= 1,  f"Expected open>=1,  got {stats}"
    asyncio.run(_run())


# ─────────────────────────────────────────────────────────
# Full Lifecycle Bonus Tests
# ─────────────────────────────────────────────────────────

def test_bonus_synchronize_updates_sha(monkeypatch):
    """Bonus: New commits pushed → synchronize updates head SHA & additions."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)

    payload = _make_pr_payload("synchronize")
    payload["pull_request"]["head"]["sha"] = "updated_sha_after_push_999"
    payload["pull_request"]["additions"]   = 200
    payload_bytes = json.dumps(payload).encode("utf-8")

    client = TestClient(app)
    resp = client.post(
        "/api/webhooks/github",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": _make_signature(payload_bytes, WEBHOOK_SECRET),
            "X-GitHub-Event":      "pull_request",
            "X-GitHub-Delivery":   str(uuid.uuid4()),
            "Content-Type":        "application/json",
        },
    )
    assert resp.status_code == 200

    async def _check():
        pr = await get_pull_request(TEST_PR_NUMBER, TEST_REPO_NAME)
        assert pr["head_sha"]  == "updated_sha_after_push_999"
        assert pr["additions"] == 200
    asyncio.run(_check())


def test_bonus_pr_merged_sets_merged_flag(monkeypatch):
    """Bonus: PR closed+merged webhook sets merged=True and stats update."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)

    payload       = _make_pr_payload("closed", state="closed", merged=True)
    payload_bytes = json.dumps(payload).encode("utf-8")

    client = TestClient(app)
    resp = client.post(
        "/api/webhooks/github",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": _make_signature(payload_bytes, WEBHOOK_SECRET),
            "X-GitHub-Event":      "pull_request",
            "X-GitHub-Delivery":   str(uuid.uuid4()),
            "Content-Type":        "application/json",
        },
    )
    assert resp.status_code == 200

    async def _check():
        pr = await get_pull_request(TEST_PR_NUMBER, TEST_REPO_NAME)
        assert pr["merged"] is True
        assert pr["state"]  == "closed"
        stats = await get_pr_stats()
        assert stats["merged"] >= 1
    asyncio.run(_check())


def test_bonus_tampered_signature_rejected(monkeypatch):
    """Bonus: Webhook with wrong HMAC signature returns HTTP 401."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)

    payload_bytes = json.dumps(_make_pr_payload("opened")).encode("utf-8")

    client = TestClient(app)
    resp = client.post(
        "/api/webhooks/github",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": "sha256=tampered_invalid_signature_00000",
            "X-GitHub-Event":      "pull_request",
            "X-GitHub-Delivery":   str(uuid.uuid4()),
            "Content-Type":        "application/json",
        },
    )
    assert resp.status_code == 401


def test_bonus_unsupported_action_ignored(monkeypatch):
    """Bonus: Unknown PR action (e.g. 'assigned') is safely ignored."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)

    payload       = _make_pr_payload("assigned")
    payload_bytes = json.dumps(payload).encode("utf-8")

    client = TestClient(app)
    resp = client.post(
        "/api/webhooks/github",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": _make_signature(payload_bytes, WEBHOOK_SECRET),
            "X-GitHub-Event":      "pull_request",
            "X-GitHub-Delivery":   str(uuid.uuid4()),
            "Content-Type":        "application/json",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"
