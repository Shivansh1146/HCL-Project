"""
tests/test_ai_review_dashboard.py — Suite testing Phase 2.3 AI Review Dashboard & History API endpoints.

Covers:
1. GET /api/prs with multi-field filters (repo, author, decision, review_status, date_range, sort, search query)
2. GET /api/prs/stats returning AI review metrics (total_reviews, safe_count, block_count, review_required_count, error_count, avg_coverage, avg_processing_time_sec, total_comments_published)
3. GET /api/prs/{owner}/{repo}/{pr_number} returning full review analysis, summary, issues list, and raw findings
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from main import app
from auth.models import User
from auth.dependencies import require_auth


def override_require_auth():
    """Bypasses OAuth authentication guard for testing."""
    return User(
        id=1,
        github_id=99999,
        login="test-engineer",
        name="Test Engineer",
        email="engineer@example.com",
        avatar_url="https://github.com/test-engineer.png",
        created_at="2026-08-05T00:00:00Z",
        updated_at="2026-08-05T00:00:00Z",
    )



app.dependency_overrides[require_auth] = override_require_auth
client = TestClient(app)


MOCK_PRS = [
    {
        "id": 1,
        "github_pr_id": 1001,
        "repository_name": "acme/backend",
        "owner": "acme",
        "number": 101,
        "title": "Fix database timeout in pool engine",
        "state": "open",
        "draft": False,
        "merged": False,
        "author_login": "alice",
        "author_avatar": "https://github.com/alice.png",
        "review_status": "success",
        "decision": "SAFE",
        "issues_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "coverage_percentage": 100.0,
        "processing_time_sec": 2.4,
        "review_summary": "All tests passed with zero high risk issues.",
        "issues_json": "[]",
        "reviewed_at": "2026-08-05T12:00:00Z",
        "review_posted": 1,
        "review_posted_at": "2026-08-05T12:05:00Z",
        "github_review_id": 98765,
        "html_url": "https://github.com/acme/backend/pull/101",
        "created_at": "2026-08-05T10:00:00Z",
        "updated_at": "2026-08-05T12:00:00Z"
    },
    {
        "id": 2,
        "github_pr_id": 1002,
        "repository_name": "acme/backend",
        "owner": "acme",
        "number": 102,
        "title": "Add SQL query executor without validation",
        "state": "open",
        "draft": False,
        "merged": False,
        "author_login": "bob",
        "author_avatar": "https://github.com/bob.png",
        "review_status": "success",
        "decision": "BLOCK",
        "issues_count": 1,
        "high_count": 1,
        "medium_count": 0,
        "low_count": 0,
        "coverage_percentage": 92.0,
        "processing_time_sec": 4.1,
        "review_summary": "Critical SQL Injection flaw identified in query handler.",
        "issues_json": '[{"file": "db.py", "line": 42, "severity": "high", "category": "security", "description": "Unsanitized input in query", "suggestion": "Use parameterized query"}]',
        "reviewed_at": "2026-08-06T14:00:00Z",
        "review_posted": 0,
        "review_posted_at": None,
        "github_review_id": None,
        "html_url": "https://github.com/acme/backend/pull/102",
        "created_at": "2026-08-06T13:00:00Z",
        "updated_at": "2026-08-06T14:00:00Z"
    }
]


def test_list_pull_requests_with_filters():
    """Verifies GET /api/prs returns list with multi-field filtering options."""
    async def mock_list(*args, **kwargs):
        return {
            "items": MOCK_PRS,
            "total": 2,
            "page": 1,
            "per_page": 20,
            "total_pages": 1
        }

    with patch("services.pr_service.PRService.list_pull_requests", side_effect=mock_list):
        response = client.get("/api/prs?decision=SAFE&sort=newest&q=timeout")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["items"][0]["decision"] == "SAFE"


def test_get_pull_request_stats_dashboard_metrics():
    """Verifies GET /api/prs/stats returns telemetry stats for AI review cards."""
    mock_stats = {
        "total": 10,
        "open": 5,
        "closed": 3,
        "merged": 2,
        "draft": 0,
        "total_reviews": 8,
        "safe_count": 5,
        "block_count": 2,
        "review_required_count": 1,
        "error_count": 0,
        "avg_coverage": 96.5,
        "avg_processing_time_sec": 3.4,
        "total_comments_published": 4
    }

    async def mock_get_stats():
        return mock_stats

    with patch("services.pr_service.PRService.get_pr_stats", side_effect=mock_get_stats):
        response = client.get("/api/prs/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_reviews"] == 8
        assert data["safe_count"] == 5
        assert data["block_count"] == 2
        assert data["avg_coverage"] == 96.5
        assert data["avg_processing_time_sec"] == 3.4


def test_get_pull_request_details_extended():
    """Verifies GET /api/prs/{owner}/{repo}/{pr_number} returns detailed analysis & findings."""
    async def mock_get_pr(number, repository_name=None):
        return MOCK_PRS[1]

    async def mock_get_pr_details_none(full_name, pr_number):
        return None

    with patch("routers.pr_router.get_pr_details", side_effect=mock_get_pr_details_none), \
         patch("services.pr_service.PRService.get_pull_request", side_effect=mock_get_pr):
        response = client.get("/api/prs/acme/backend/102")
        assert response.status_code == 200
        data = response.json()
        assert data["pr_number"] == 102
        assert data["decision"] == "BLOCK"
        assert data["high_count"] == 1
        assert len(data["issues"]) == 1
        assert data["issues"][0]["file"] == "db.py"

