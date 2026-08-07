"""
tests/test_ai_review_pipeline.py — Unit & Integration tests for Feature 2.1 AI Review Pipeline Integration.

Tests cover:
1. Webhook background task dispatch on PR actions: opened, reopened, ready_for_review, synchronize.
2. Background AI review task execution with successful AI analysis and decision persistence.
3. Background AI review task execution with failed AI analysis handling.
4. Database persistence of review status, decision, severity metrics, and issue findings on pull_requests table.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from auth.store import (
    initialize_auth_db,
    get_pull_request,
    upsert_pull_request,
)
from services.pr_service import PRService, run_ai_review_task


def setup_module(module):
    """Initializes Auth DB synchronously before test suite execution."""
    asyncio.run(initialize_auth_db())


TEST_PR_ID = 988001
TEST_REPO = "Shivansh1146/HCL-Project"
TEST_PR_NUMBER = 901


async def _create_test_pr(number: int = TEST_PR_NUMBER, pr_id: int = TEST_PR_ID) -> dict:
    pr_payload = {
        "github_pr_id": pr_id,
        "repository_id": 999,
        "repository_name": TEST_REPO,
        "owner": "Shivansh1146",
        "number": number,
        "title": "Feature: Add AI pipeline integration",
        "body": "Testing Phase 2.1 AI review pipeline persistence",
        "state": "open",
        "draft": False,
        "merged": False,
        "author_login": "testdev",
        "base_branch": "main",
        "head_branch": "feature/ai-pipeline",
        "head_sha": "abc123456def7890",
        "base_sha": "0000000000000000",
    }
    return await upsert_pull_request(pr_payload)


class TestAIReviewPipelineIntegration:
    """Test suite for Phase 2.1 AI Review Pipeline Integration."""

    def test_background_task_dispatch_on_supported_pr_actions(self):
        """Verify background task dispatch for opened, reopened, ready_for_review, synchronize."""
        async def _run():
            await initialize_auth_db()
            mock_background_tasks = MagicMock()

            trigger_actions = ["opened", "reopened", "ready_for_review", "synchronize"]
            for act in trigger_actions:
                mock_background_tasks.reset_mock()
                payload = {
                    "action": act,
                    "pull_request": {"id": TEST_PR_ID, "number": TEST_PR_NUMBER, "state": "open"},
                    "repository": {"full_name": TEST_REPO, "owner": {"login": "Shivansh1146"}, "name": "HCL-Project"},
                    "sender": {"login": "Shivansh1146"},
                }

                res = await PRService.process_pull_request_event(
                    payload=payload,
                    delivery_id=f"delivery-{act}",
                    background_tasks=mock_background_tasks,
                )

                assert res["status"] == "processed"
                assert res["ai_review_dispatched"] is True
                mock_background_tasks.add_task.assert_called_once()

            # Non-trigger action e.g. closed
            mock_background_tasks.reset_mock()
            closed_payload = {
                "action": "closed",
                "pull_request": {"id": TEST_PR_ID, "number": TEST_PR_NUMBER, "state": "closed"},
                "repository": {"full_name": TEST_REPO, "owner": {"login": "Shivansh1146"}, "name": "HCL-Project"},
                "sender": {"login": "Shivansh1146"},
            }
            res_closed = await PRService.process_pull_request_event(
                payload=closed_payload,
                delivery_id="delivery-closed",
                background_tasks=mock_background_tasks,
            )
            assert res_closed["status"] == "processed"
            assert res_closed["ai_review_dispatched"] is False
            mock_background_tasks.add_task.assert_not_called()

        asyncio.run(_run())

    def test_run_ai_review_task_successful_analysis(self):
        """Verify run_ai_review_task executes AIService.analyze_code and persists findings/decision."""
        async def _run():
            await initialize_auth_db()
            pr_data = await _create_test_pr(number=902, pr_id=988002)

            sample_diff = (
                "diff --git a/app.py b/app.py\n"
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,3 +1,3 @@\n"
                " def main():\n"
                "-    pass\n"
                "+    eval(input())\n"
            )

            mock_analysis = {
                "status": "success",
                "total_chunks": 1,
                "processed_chunks": 1,
                "coverage": 100.0,
                "issues": [
                    {
                        "file": "app.py",
                        "line": 2,
                        "severity": "high",
                        "type": "security",
                        "description": "Use of eval() detected, allowing arbitrary code execution.",
                        "fix": "# Avoid eval()",
                        "suggested_fix": "# Avoid eval()",
                    }
                ],
            }

            mock_ai_service = MagicMock()
            mock_ai_service.analyze_code = AsyncMock(return_value=mock_analysis)
            mock_ai_service.is_configured = MagicMock(return_value=True)

            with patch("services.pr_service.fetch_diff", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = sample_diff
                with patch("services.pr_service.get_ai_service", return_value=mock_ai_service):
                    await run_ai_review_task(
                        github_pr_id=988002,
                        owner="Shivansh1146",
                        repo="HCL-Project",
                        pr_number=902,
                    )

            updated_pr = await get_pull_request(902)
            assert updated_pr is not None
            assert updated_pr["review_status"] == "success"
            assert updated_pr["decision"] == "BLOCK"
            assert updated_pr["issues_count"] == 1
            assert updated_pr["high_count"] == 1
            assert updated_pr["coverage_percentage"] == 100.0
            assert updated_pr["reviewed_at"] is not None

            issues = json.loads(updated_pr["issues_json"])
            assert len(issues) == 1
            assert issues[0]["severity"] == "high"

        asyncio.run(_run())

    def test_run_ai_review_task_failed_analysis(self):
        """Verify handling when AIService.analyze_code returns failed status."""
        async def _run():
            await initialize_auth_db()
            await _create_test_pr(number=903, pr_id=988003)

            sample_diff = "diff --git a/main.py b/main.py\n+ print('hello')"

            mock_analysis = {
                "status": "failed",
                "reason": "RATE_LIMIT",
            }

            mock_ai_service = MagicMock()
            mock_ai_service.analyze_code = AsyncMock(return_value=mock_analysis)
            mock_ai_service.is_configured = MagicMock(return_value=True)

            with patch("services.pr_service.fetch_diff", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = sample_diff
                with patch("services.pr_service.get_ai_service", return_value=mock_ai_service):
                    await run_ai_review_task(
                        github_pr_id=988003,
                        owner="Shivansh1146",
                        repo="HCL-Project",
                        pr_number=903,
                    )

            updated_pr = await get_pull_request(903)
            assert updated_pr is not None
            assert updated_pr["review_status"] == "failed"
            assert updated_pr["decision"] == "ANALYSIS_INCOMPLETE"
            assert "AI analysis failed: RATE_LIMIT" in updated_pr["review_summary"]

        asyncio.run(_run())

    def test_run_ai_review_task_fetch_diff_failure(self):
        """Verify handling when fetch_diff fails (returns None)."""
        async def _run():
            await initialize_auth_db()
            await _create_test_pr(number=904, pr_id=988004)

            with patch("services.pr_service.fetch_diff", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = None
                await run_ai_review_task(
                    github_pr_id=988004,
                    owner="Shivansh1146",
                    repo="HCL-Project",
                    pr_number=904,
                )

            updated_pr = await get_pull_request(904)
            assert updated_pr is not None
            assert updated_pr["review_status"] == "failed"
            assert updated_pr["decision"] == "ERROR"
            assert "Failed to fetch git diff" in updated_pr["review_summary"]

        asyncio.run(_run())

    def test_run_ai_review_task_missing_api_key(self):
        """Verify handling when GROQ_API_KEY is missing."""
        async def _run():
            await initialize_auth_db()
            await _create_test_pr(number=905, pr_id=988005)

            sample_diff = "diff --git a/main.py b/main.py\n+ print('hello')"

            mock_ai_service = MagicMock()
            mock_ai_service.is_configured = MagicMock(return_value=False)

            with patch("services.pr_service.fetch_diff", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = sample_diff
                with patch("services.pr_service.get_ai_service", return_value=mock_ai_service):
                    await run_ai_review_task(
                        github_pr_id=988005,
                        owner="Shivansh1146",
                        repo="HCL-Project",
                        pr_number=905,
                    )

            updated_pr = await get_pull_request(905)
            assert updated_pr is not None
            assert updated_pr["review_status"] == "failed"
            assert updated_pr["decision"] == "ERROR"
            assert "AI service not configured" in updated_pr["review_summary"]

        asyncio.run(_run())

    def test_run_ai_review_task_expired_api_key(self):
        """Verify handling when GROQ_API_KEY is expired/invalid."""
        async def _run():
            await initialize_auth_db()
            await _create_test_pr(number=906, pr_id=988006)

            sample_diff = "diff --git a/main.py b/main.py\n+ print('hello')"

            mock_analysis = {
                "status": "failed",
                "reason": "AUTH_ERROR",
            }

            mock_ai_service = MagicMock()
            mock_ai_service.analyze_code = AsyncMock(return_value=mock_analysis)
            mock_ai_service.is_configured = MagicMock(return_value=True)

            with patch("services.pr_service.fetch_diff", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = sample_diff
                with patch("services.pr_service.get_ai_service", return_value=mock_ai_service):
                    await run_ai_review_task(
                        github_pr_id=988006,
                        owner="Shivansh1146",
                        repo="HCL-Project",
                        pr_number=906,
                    )

            updated_pr = await get_pull_request(906)
            assert updated_pr is not None
            assert updated_pr["review_status"] == "failed"
            assert updated_pr["decision"] == "ERROR"
            assert "AUTH_ERROR" in updated_pr["review_summary"]

        asyncio.run(_run())

    def test_run_ai_review_task_quota_exceeded(self):
        """Verify handling when Groq API quota is exceeded."""
        async def _run():
            await initialize_auth_db()
            await _create_test_pr(number=907, pr_id=988007)

            sample_diff = "diff --git a/main.py b/main.py\n+ print('hello')"

            mock_analysis = {
                "status": "failed",
                "reason": "QUOTA_EXCEEDED",
            }

            mock_ai_service = MagicMock()
            mock_ai_service.analyze_code = AsyncMock(return_value=mock_analysis)
            mock_ai_service.is_configured = MagicMock(return_value=True)

            with patch("services.pr_service.fetch_diff", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = sample_diff
                with patch("services.pr_service.get_ai_service", return_value=mock_ai_service):
                    await run_ai_review_task(
                        github_pr_id=988007,
                        owner="Shivansh1146",
                        repo="HCL-Project",
                        pr_number=907,
                    )

            updated_pr = await get_pull_request(907)
            assert updated_pr is not None
            assert updated_pr["review_status"] == "failed"
            assert updated_pr["decision"] == "ERROR"
            assert "QUOTA_EXCEEDED" in updated_pr["review_summary"]

        asyncio.run(_run())

    def test_run_ai_review_task_safe_decision_persistence(self):
        """Verify safe PR (no issues found) is persisted with decision SAFE."""
        async def _run():
            await initialize_auth_db()
            await _create_test_pr(number=905, pr_id=988005)

            sample_diff = (
                "diff --git a/utils.py b/utils.py\n"
                "--- a/utils.py\n"
                "+++ b/utils.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def add(a, b):\n"
                "-    return a + b\n"
                "+    return int(a) + int(b)\n"
            )

            mock_analysis = {
                "status": "success",
                "total_chunks": 1,
                "processed_chunks": 1,
                "coverage": 100.0,
                "issues": [],
            }

            mock_ai_service = MagicMock()
            mock_ai_service.analyze_code = AsyncMock(return_value=mock_analysis)

            with patch("services.pr_service.fetch_diff", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = sample_diff
                with patch("services.pr_service.get_ai_service", return_value=mock_ai_service):
                    await run_ai_review_task(
                        github_pr_id=988005,
                        owner="Shivansh1146",
                        repo="HCL-Project",
                        pr_number=905,
                    )

            updated_pr = await get_pull_request(905)
            assert updated_pr is not None
            assert updated_pr["review_status"] == "success"
            assert updated_pr["decision"] == "SAFE"
            assert updated_pr["issues_count"] == 0
            assert updated_pr["high_count"] == 0
            assert updated_pr["medium_count"] == 0
            assert updated_pr["low_count"] == 0

        asyncio.run(_run())
