"""
tests/test_github_review_publisher.py — Phase 2.2: Review Publisher Test Suite.

Test coverage:
  - Successful review publish (BLOCK → REQUEST_CHANGES)
  - Safe review (SAFE → APPROVE, no inline comments, "no issues" body)
  - Review required (REVIEW_REQUIRED → COMMENT, inline comments attached)
  - Invalid line number skipped from inline comments
  - GitHub API failure raises error and returns error dict
  - Token refresh / fallback to GITHUB_TOKEN
  - Duplicate publish prevention (already_published guard)
  - POST /api/prs/{owner}/{repo}/{number}/publish-review endpoint (success + 422 + 500)
"""
import asyncio
import json
import sys
import os
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(severity="HIGH", title="SQL Injection", description="Not sanitized.",
                file="app/db.py", line=42, fix="cursor.execute(query, (v,))", type_="security"):
    return {"severity": severity, "title": title, "description": description,
            "file": file, "line": line, "fix": fix, "type": type_}


def _mock_review_result(review_id=789456):
    return {"status": "success", "review_id": review_id, "data": {"id": review_id}}


# ---------------------------------------------------------------------------
# Unit tests: _build_review_body
# ---------------------------------------------------------------------------

class TestBuildReviewBody:

    def test_no_issues_all_clear(self):
        from services.review_publisher import _build_review_body
        body = _build_review_body("SAFE", [], summary=None)
        assert "No significant issues detected" in body

    def test_block_contains_emoji_and_decision(self):
        from services.review_publisher import _build_review_body
        body = _build_review_body("BLOCK", [_make_issue("HIGH")])
        assert "BLOCK" in body
        assert "🚫" in body
        assert "must be addressed" in body

    def test_review_required_body(self):
        from services.review_publisher import _build_review_body
        body = _build_review_body("REVIEW_REQUIRED", [_make_issue("MEDIUM")])
        assert "REVIEW_REQUIRED" in body
        assert "⚠️" in body

    def test_safe_body(self):
        from services.review_publisher import _build_review_body
        body = _build_review_body("SAFE", [_make_issue("LOW")])
        assert "SAFE" in body and "✅" in body

    def test_severity_counts(self):
        from services.review_publisher import _build_review_body
        issues = [_make_issue("HIGH"), _make_issue("HIGH"), _make_issue("MEDIUM")]
        body = _build_review_body("BLOCK", issues)
        assert "HIGH: **2**" in body
        assert "MEDIUM: **1**" in body

    def test_body_capped_at_65536(self):
        from services.review_publisher import _build_review_body
        issues = [_make_issue(description="x" * 1000) for _ in range(100)]
        assert len(_build_review_body("BLOCK", issues)) <= 65536


# ---------------------------------------------------------------------------
# Unit tests: _build_inline_comments
# ---------------------------------------------------------------------------

class TestBuildInlineComments:

    def test_valid_issues_become_comments(self):
        from services.review_publisher import _build_inline_comments
        issues = [
            _make_issue(file="app/db.py", line=42, severity="HIGH"),
            _make_issue(file="app/utils.py", line=10, severity="LOW", fix=""),
        ]
        comments = _build_inline_comments(issues, "abc123")
        assert len(comments) == 2
        assert comments[0]["path"] == "app/db.py"
        assert comments[0]["line"] == 42
        assert comments[0]["side"] == "RIGHT"
        assert "suggestion" in comments[0]["body"]
        assert "manual review required" in comments[1]["body"]

    def test_invalid_line_zero_skipped(self):
        from services.review_publisher import _build_inline_comments
        issues = [_make_issue(file="app/db.py", line=0),
                  _make_issue(file="app/db.py", line=-1),
                  _make_issue(file="app/db.py", line="abc"),
                  _make_issue(file="app/db.py", line=None)]
        assert len(_build_inline_comments(issues, "x")) == 0

    def test_missing_file_path_skipped(self):
        from services.review_publisher import _build_inline_comments
        issues = [{"severity": "HIGH", "title": "T", "description": "D", "file": "", "line": 5},
                  {"severity": "HIGH", "title": "T", "description": "D", "file": None, "line": 5}]
        assert len(_build_inline_comments(issues, "x")) == 0

    def test_severity_emojis(self):
        from services.review_publisher import _build_inline_comments
        for sev, emoji in [("HIGH", "🔴"), ("MEDIUM", "🟡"), ("LOW", "🟢")]:
            comments = _build_inline_comments([_make_issue(severity=sev, line=1)], "sha")
            assert emoji in comments[0]["body"]


# ---------------------------------------------------------------------------
# Integration tests: publish_review() using asyncio.run()
# ---------------------------------------------------------------------------

class TestPublishReview:

    def test_successful_block_review_request_changes(self):
        """BLOCK → REQUEST_CHANGES event + inline comments + DB update."""
        async def _run():
            issues = [_make_issue("HIGH", line=10, file="app/db.py")]
            mock_gh = MagicMock()
            mock_gh.post_pull_request_review = AsyncMock(return_value=_mock_review_result(111222))
            mock_app = MagicMock()
            mock_app.get_installation_access_token = AsyncMock(return_value="ghs_tok")

            with patch("services.github_service._github_service_instance", mock_gh), \
                 patch("auth.store.update_pull_request_review_published", new_callable=AsyncMock) as mock_db, \
                 patch("auth.app_service.get_app_service", return_value=mock_app):

                from services.review_publisher import publish_review
                result = await publish_review(
                    github_pr_id=5001, owner="acme", repo="backend", pr_number=42,
                    head_sha="deadbeef", decision="BLOCK",
                    issues_json=json.dumps(issues), review_summary="Found 1 HIGH.", installation_id=99,
                )

            assert result["status"] == "success"
            assert result["review_id"] == 111222
            assert result["comments_posted"] == 1
            kw = mock_gh.post_pull_request_review.call_args.kwargs
            assert kw["event"] == "REQUEST_CHANGES"
            assert kw["commit_sha"] == "deadbeef"
            assert len(kw["comments"]) == 1
            mock_db.assert_called_once()
        asyncio.run(_run())

    def test_safe_review_approve_no_comments(self):
        """SAFE → APPROVE, zero comments, all-clear body."""
        async def _run():
            mock_gh = MagicMock()
            mock_gh.post_pull_request_review = AsyncMock(return_value=_mock_review_result(222333))
            mock_app = MagicMock()
            mock_app.get_installation_access_token = AsyncMock(return_value="tok")

            with patch("services.github_service._github_service_instance", mock_gh), \
                 patch("auth.store.update_pull_request_review_published", new_callable=AsyncMock), \
                 patch("auth.app_service.get_app_service", return_value=mock_app):

                from services.review_publisher import publish_review
                result = await publish_review(
                    github_pr_id=5002, owner="acme", repo="backend", pr_number=43,
                    head_sha="cafecafe", decision="SAFE", issues_json="[]", installation_id=99,
                )

            assert result["status"] == "success"
            assert result["comments_posted"] == 0
            kw = mock_gh.post_pull_request_review.call_args.kwargs
            assert kw["event"] == "APPROVE"
            assert kw["comments"] == []
            assert "No significant issues detected" in kw["body"]
        asyncio.run(_run())

    def test_review_required_uses_comment_event(self):
        """REVIEW_REQUIRED → COMMENT event."""
        async def _run():
            issues = [_make_issue("MEDIUM", line=5, file="app/utils.py")]
            mock_gh = MagicMock()
            mock_gh.post_pull_request_review = AsyncMock(return_value=_mock_review_result(333444))
            mock_app = MagicMock()
            mock_app.get_installation_access_token = AsyncMock(return_value="tok")

            with patch("services.github_service._github_service_instance", mock_gh), \
                 patch("auth.store.update_pull_request_review_published", new_callable=AsyncMock), \
                 patch("auth.app_service.get_app_service", return_value=mock_app):

                from services.review_publisher import publish_review
                result = await publish_review(
                    github_pr_id=5003, owner="acme", repo="backend", pr_number=44,
                    head_sha="abc111", decision="REVIEW_REQUIRED",
                    issues_json=json.dumps(issues), installation_id=99,
                )

            assert result["status"] == "success"
            kw = mock_gh.post_pull_request_review.call_args.kwargs
            assert kw["event"] == "COMMENT"
            assert len(kw["comments"]) == 1
        asyncio.run(_run())

    def test_invalid_lines_skipped_in_inline_comments(self):
        """Issues with line=0 or empty file are excluded from GitHub comments."""
        async def _run():
            issues = [
                _make_issue("HIGH", file="", line=0),
                _make_issue("HIGH", file="app/db.py", line=0),
                _make_issue("HIGH", file="app/db.py", line=99),
            ]
            mock_gh = MagicMock()
            mock_gh.post_pull_request_review = AsyncMock(return_value=_mock_review_result(444555))
            mock_app = MagicMock()
            mock_app.get_installation_access_token = AsyncMock(return_value="tok")

            with patch("services.github_service._github_service_instance", mock_gh), \
                 patch("auth.store.update_pull_request_review_published", new_callable=AsyncMock), \
                 patch("auth.app_service.get_app_service", return_value=mock_app):

                from services.review_publisher import publish_review
                result = await publish_review(
                    github_pr_id=5004, owner="acme", repo="backend", pr_number=45,
                    head_sha="def456", decision="BLOCK",
                    issues_json=json.dumps(issues), installation_id=99,
                )

            assert result["status"] == "success"
            assert result["comments_posted"] == 1
        asyncio.run(_run())

    def test_github_api_failure_returns_error_dict(self):
        """RuntimeError from GitHub API → error dict, DB not updated."""
        async def _run():
            mock_gh = MagicMock()
            mock_gh.post_pull_request_review = AsyncMock(
                side_effect=RuntimeError("GitHub API Error posting review: 401 Unauthorized")
            )
            mock_app = MagicMock()
            mock_app.get_installation_access_token = AsyncMock(return_value="tok")

            with patch("services.github_service._github_service_instance", mock_gh), \
                 patch("auth.store.update_pull_request_review_published", new_callable=AsyncMock) as mock_db, \
                 patch("auth.app_service.get_app_service", return_value=mock_app):

                from services.review_publisher import publish_review
                result = await publish_review(
                    github_pr_id=5005, owner="acme", repo="backend", pr_number=46,
                    head_sha="fail000", decision="BLOCK", issues_json="[]", installation_id=99,
                )

            assert result["status"] == "error"
            assert result["review_id"] is None
            assert result["comments_posted"] == 0
            assert "GitHub API Error" in result["error"]
            mock_db.assert_not_called()
        asyncio.run(_run())

    def test_persistence_failure_is_not_reported_as_published(self):
        """A GitHub success is not a local success unless pull_requests is updated."""
        async def _run():
            mock_gh = MagicMock()
            mock_gh.post_pull_request_review = AsyncMock(return_value=_mock_review_result(4918559018))
            mock_app = MagicMock()
            mock_app.get_installation_access_token = AsyncMock(return_value="tok")

            with patch("services.github_service._github_service_instance", mock_gh), \
                 patch("auth.store.update_pull_request_review_published", new_callable=AsyncMock, return_value=None), \
                 patch("auth.app_service.get_app_service", return_value=mock_app):
                from services.review_publisher import publish_review
                result = await publish_review(
                    github_pr_id=5007, owner="acme", repo="backend", pr_number=48,
                    head_sha="persist000", decision="BLOCK", issues_json="[]", installation_id=99,
                )

            assert result["status"] == "error"
            assert result["review_id"] == 4918559018
            assert "local publication state was not saved" in result["error"]
        asyncio.run(_run())

    def test_token_refresh_fallback_to_github_token(self):
        """Empty installation token → fall back to GITHUB_TOKEN env var."""
        async def _run():
            mock_app = MagicMock()
            mock_app.get_installation_access_token = AsyncMock(return_value="")
            mock_gh = MagicMock()
            mock_gh.post_pull_request_review = AsyncMock(return_value=_mock_review_result(555666))

            with patch("services.github_service._github_service_instance", mock_gh), \
                 patch("auth.store.update_pull_request_review_published", new_callable=AsyncMock), \
                 patch("auth.app_service.get_app_service", return_value=mock_app), \
                 patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_fallback"}):

                from services.review_publisher import publish_review
                result = await publish_review(
                    github_pr_id=5006, owner="acme", repo="backend", pr_number=47,
                    head_sha="fb123", decision="SAFE", issues_json="[]", installation_id=99,
                )

            assert result["status"] == "success"
            kw = mock_gh.post_pull_request_review.call_args.kwargs
            assert kw["token"] == "ghp_fallback"
        asyncio.run(_run())


class TestGitHubReviewEventPreservation:

    def test_rejected_request_changes_is_not_retried_as_comment(self):
        """A BLOCK event remains REQUEST_CHANGES even when GitHub rejects it."""
        class RejectedResponse:
            status_code = 422
            text = "Review event is not permitted"
            headers = {}

        class RecordingClient:
            def __init__(self):
                self.payloads = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, headers, json):
                self.payloads.append(json)
                return RejectedResponse()

        async def _run():
            client = RecordingClient()
            with patch("services.github_service.httpx.AsyncClient", return_value=client):
                from services.github_service import GitHubService
                service = GitHubService()
                with pytest.raises(RuntimeError, match="HTTP 422"):
                    await service.post_pull_request_review(
                        owner="acme", repo="backend", pr_number=1,
                        event="REQUEST_CHANGES", body="BLOCK", comments=[],
                    )

            assert len(client.payloads) == 1
            assert client.payloads[0]["event"] == "REQUEST_CHANGES"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Integration tests: PRService.publish_pr_review()
# ---------------------------------------------------------------------------

class TestPRServicePublishReview:

    def test_duplicate_publish_prevention(self):
        """review_posted=True → returns already_published without GitHub API call."""
        async def _run():
            from services.pr_service import PRService
            mock_pr = {
                "github_pr_id": 9001, "review_posted": True,
                "github_review_id": 111, "review_posted_at": "2026-08-07T00:00:00Z",
                "issues_json": "[]",
            }
            with patch("services.pr_service.store_get_pull_request", new_callable=AsyncMock, return_value=mock_pr):
                result = await PRService.publish_pr_review("acme", "backend", 901)
            assert result["status"] == "already_published"
            assert result["review_id"] == 111
        asyncio.run(_run())

    def test_review_not_complete_raises_value_error(self):
        """Pending/processing AI review raises ValueError."""
        async def _run():
            from services.pr_service import PRService
            mock_pr = {
                "github_pr_id": 9002, "review_posted": False,
                "review_status": "pending", "decision": "PENDING",
            }
            with patch("services.pr_service.store_get_pull_request", new_callable=AsyncMock, return_value=mock_pr):
                with pytest.raises(ValueError, match="not yet complete"):
                    await PRService.publish_pr_review("acme", "backend", 902)
        asyncio.run(_run())

    def test_pr_not_found_raises_value_error(self):
        """Missing PR in DB raises ValueError."""
        async def _run():
            from services.pr_service import PRService
            with patch("services.pr_service.store_get_pull_request", new_callable=AsyncMock, return_value=None):
                with pytest.raises(ValueError, match="not found in database"):
                    await PRService.publish_pr_review("acme", "backend", 903)
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Endpoint tests: POST /api/prs/{owner}/{repo}/{number}/publish-review
# ---------------------------------------------------------------------------

def _make_authed_client():
    """Create TestClient with overridden require_auth dependency."""
    from fastapi.testclient import TestClient
    from main import app
    from auth.dependencies import require_auth
    from auth.models import User

    mock_user = User(
        id=70001,
        github_id=70001,
        login="review_publisher_tester",
        name="Review Publisher",
        email="reviewer@test.com",
        created_at="2026-08-07T00:00:00Z",
        updated_at="2026-08-07T00:00:00Z",
    )

    app.dependency_overrides[require_auth] = lambda: mock_user
    client = TestClient(app, raise_server_exceptions=False)
    return client





class TestPublishReviewEndpoint:

    def test_publish_review_endpoint_success(self):
        """POST /publish-review → 200 with review_id and comments_posted."""
        mock_result = {"status": "success", "review_id": 987654, "comments_posted": 3}

        with patch("services.pr_service.PRService.publish_pr_review", new_callable=AsyncMock, return_value=mock_result):
            client = _make_authed_client()
            resp = client.post("/api/prs/acme/backend/1001/publish-review")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["review_id"] == 987654
        assert body["comments_posted"] == 3

    def test_publish_review_endpoint_422_when_pending(self):
        """Returns 422 when AI review not complete."""
        with patch("services.pr_service.PRService.publish_pr_review", new_callable=AsyncMock,
                   side_effect=ValueError("AI review is not yet complete")):
            client = _make_authed_client()
            resp = client.post("/api/prs/acme/backend/1002/publish-review")

        assert resp.status_code == 422

    def test_publish_review_endpoint_500_on_github_failure(self):
        """Returns 500 on unexpected RuntimeError."""
        with patch("services.pr_service.PRService.publish_pr_review", new_callable=AsyncMock,
                   side_effect=RuntimeError("GitHub connection error")):
            client = _make_authed_client()
            resp = client.post("/api/prs/acme/backend/1003/publish-review")

        assert resp.status_code == 500

