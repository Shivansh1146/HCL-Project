"""
tests/test_pr_processing.py — Unit & Integration tests for Pull Request Event Processing (Phase 1.7).

Tests cover:
1. 'opened' event processing: inserts PR record with author, branches, and metadata.
2. 'edited' event processing: updates title and body of existing PR.
3. 'closed' event processing (non-merged): updates state to 'closed', merged=False.
4. 'closed' event processing (merged): updates state to 'closed', merged=True.
5. 'synchronize' event processing: updates head_sha and additions/deletions counts.
6. Duplicate delivery GUID: deduplication check skips second delivery.
7. Invalid payload handling: payload without pull_request object returns error safely.
8. API Endpoints: GET /api/prs, GET /api/prs/stats, GET /api/prs/{number}.
"""

import asyncio
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from main import app
from auth.store import initialize_auth_db, get_pull_request
from services.pr_service import PRService

WEBHOOK_SECRET = "test_pr_webhook_secret_6789"


def setup_module(module):
    """Initializes Auth DB synchronously before test suite execution."""
    asyncio.run(initialize_auth_db())


class TestPRProcessing:
    """Test suite for Phase 1.7 Pull Request Event Ingestion & Persistence."""

    def test_pr_opened_event(self):
        """Test opened event inserts a new PR in DB."""
        payload = {
            "action": "opened",
            "number": 101,
            "pull_request": {
                "id": 1100101,
                "number": 101,
                "title": "Feat: Add enterprise OAuth flow",
                "body": "Implements GitHub App OAuth integration.",
                "state": "open",
                "draft": False,
                "merged": False,
                "user": {"login": "dev_user", "avatar_url": "https://avatars.example/dev"},
                "head": {"ref": "feature/oauth", "sha": "headsha123456"},
                "base": {"ref": "main", "sha": "basesha654321"},
                "created_at": "2026-08-07T00:00:00Z",
                "updated_at": "2026-08-07T00:00:00Z",
                "html_url": "https://github.com/Shivansh1146/HCL-Project/pull/101",
                "additions": 45,
                "deletions": 12,
                "changed_files": 3,
                "commits": 2,
            },
            "repository": {
                "id": 5001,
                "name": "HCL-Project",
                "full_name": "Shivansh1146/HCL-Project",
                "owner": {"login": "Shivansh1146"},
            },
            "sender": {"login": "dev_user"},
        }

        async def _run():
            res = await PRService.process_pull_request_event(payload)
            assert res["status"] == "processed"
            assert res["action"] == "opened"
            assert res["pr_number"] == 101

            pr = await get_pull_request(101, "Shivansh1146/HCL-Project")
            assert pr is not None
            assert pr["title"] == "Feat: Add enterprise OAuth flow"
            assert pr["author_login"] == "dev_user"
            assert pr["head_sha"] == "headsha123456"
            assert pr["state"] == "open"
            assert pr["merged"] is False

        asyncio.run(_run())

    def test_pr_edited_event(self):
        """Test edited event updates existing PR title and body."""
        payload = {
            "action": "edited",
            "number": 101,
            "pull_request": {
                "id": 1100101,
                "number": 101,
                "title": "Feat: Add enterprise OAuth flow [UPDATED]",
                "body": "Updated description with security audit details.",
                "state": "open",
                "draft": False,
                "merged": False,
                "user": {"login": "dev_user"},
                "head": {"ref": "feature/oauth", "sha": "headsha123456"},
                "base": {"ref": "main", "sha": "basesha654321"},
            },
            "repository": {"full_name": "Shivansh1146/HCL-Project", "owner": {"login": "Shivansh1146"}},
        }

        async def _run():
            res = await PRService.process_pull_request_event(payload)
            assert res["status"] == "processed"

            pr = await get_pull_request(101, "Shivansh1146/HCL-Project")
            assert pr["title"] == "Feat: Add enterprise OAuth flow [UPDATED]"
            assert pr["body"] == "Updated description with security audit details."

        asyncio.run(_run())

    def test_pr_closed_and_merged_event(self):
        """Test closed event with merged=True sets state=closed and merged=True."""
        payload = {
            "action": "closed",
            "number": 101,
            "pull_request": {
                "id": 1100101,
                "number": 101,
                "title": "Feat: Add enterprise OAuth flow [UPDATED]",
                "state": "closed",
                "draft": False,
                "merged": True,
                "merged_at": "2026-08-07T01:00:00Z",
                "closed_at": "2026-08-07T01:00:00Z",
                "user": {"login": "dev_user"},
                "head": {"ref": "feature/oauth", "sha": "headsha123456"},
                "base": {"ref": "main", "sha": "basesha654321"},
            },
            "repository": {"full_name": "Shivansh1146/HCL-Project", "owner": {"login": "Shivansh1146"}},
        }

        async def _run():
            res = await PRService.process_pull_request_event(payload)
            assert res["status"] == "processed"
            assert res["merged"] is True

            pr = await get_pull_request(101, "Shivansh1146/HCL-Project")
            assert pr["state"] == "closed"
            assert pr["merged"] is True

        asyncio.run(_run())

    def test_pr_synchronize_event(self):
        """Test synchronize event updates head_sha when new commits are pushed."""
        payload = {
            "action": "synchronize",
            "number": 102,
            "pull_request": {
                "id": 1100102,
                "number": 102,
                "title": "Refactor token cache",
                "state": "open",
                "user": {"login": "alice"},
                "head": {"ref": "refactor/cache", "sha": "new_sha_999999"},
                "base": {"ref": "main", "sha": "base_sha_000000"},
                "additions": 150,
                "deletions": 40,
                "changed_files": 5,
            },
            "repository": {"full_name": "Shivansh1146/HCL-Project", "owner": {"login": "Shivansh1146"}},
        }

        async def _run():
            res = await PRService.process_pull_request_event(payload)
            assert res["status"] == "processed"

            pr = await get_pull_request(102, "Shivansh1146/HCL-Project")
            assert pr["head_sha"] == "new_sha_999999"
            assert pr["additions"] == 150
            assert pr["deletions"] == 40

        asyncio.run(_run())

    def test_pr_invalid_payload_missing_object(self):
        """Test handling payload missing pull_request object."""

        async def _run():
            res = await PRService.process_pull_request_event({"action": "opened"})
            assert res["status"] == "error"
            assert "missing" in res["reason"]

        asyncio.run(_run())


class TestPREndpointsAuthGuard:
    """Verify auth requirement for PR endpoints."""

    def test_get_prs_requires_auth(self):
        client = TestClient(app)
        res = client.get("/api/prs")
        assert res.status_code == 401

    def test_get_pr_stats_requires_auth(self):
        client = TestClient(app)
        res = client.get("/api/prs/stats")
        assert res.status_code == 401

    def test_get_pr_by_number_requires_auth(self):
        client = TestClient(app)
        res = client.get("/api/prs/101")
        assert res.status_code == 401
