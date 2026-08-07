"""
services/pr_service.py — Enterprise Pull Request Processing & AI Review Service.

Responsibilities:
1. Extract pull request metadata from GitHub webhook payloads.
2. Filter & process supported PR actions: opened, edited, reopened, ready_for_review, closed, synchronize.
3. Perform database persistence (upsert) to store PR state, author details, branches, SHAs, and change metrics.
4. Launch background AI review tasks (using BackgroundTasks) for PR actions: opened, reopened, ready_for_review, synchronize.
5. Invoke AIService.analyze_code() and multi-layer validators (DiffValidator, FilterService, SyntaxValidator).
6. Persist review results, decision, and findings to the database.
7. (Phase 2.2) Automatically publish GitHub PR reviews after successful AI analysis.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks

from auth.store import (
    get_pr_stats as store_get_pr_stats,
    get_pull_request as store_get_pull_request,
    list_pull_requests as store_list_pull_requests,
    upsert_pull_request as store_upsert_pull_request,
    update_pull_request_review_results,
    update_pull_request_review_published,
    get_installation_id_for_repo,
)
from services.ai_service import get_ai_service
from services.diff_validator import DiffValidator
from services.filter_service import parse_and_filter_issues
from services.github_service import fetch_diff
from services.syntax_validator import SyntaxValidator
from services.review_publisher import publish_review

logger = logging.getLogger("backend")

SUPPORTED_PR_ACTIONS = {
    "opened",
    "edited",
    "reopened",
    "ready_for_review",
    "closed",
    "synchronize",
}

AI_TRIGGER_ACTIONS = {
    "opened",
    "reopened",
    "ready_for_review",
    "synchronize",
}


async def run_ai_review_task(
    github_pr_id: int,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: Optional[str] = None,
    installation_id: Optional[int] = None,
):
    """
    Background task worker executing AI code review + GitHub review publish.

    Pipeline:
    1. Mark PR review status as 'processing'.
    2. Fetch PR diff via GitHub API.
    3. Analyze diff using AIService.analyze_code().
    4. Filter & validate issues using FilterService, DiffValidator, SyntaxValidator.
    5. Compute final risk decision (SAFE / REVIEW_REQUIRED / BLOCK).
    6. Persist review status, decision, metrics, and findings into SQLite.
    7. (Phase 2.2) Publish GitHub PR review via ReviewPublisher.
    """
    logger.info(f"🤖 [AI_REVIEW_TASK] ========== STARTING AI REVIEW TASK ==========")
    logger.info(f"🤖 [AI_REVIEW_TASK] Parameters: github_pr_id={github_pr_id}, owner={owner}, repo={repo}, pr_number={pr_number}, head_sha={head_sha}")
    logger.info("📊 PR pipeline initiated")

    await update_pull_request_review_results(
        github_pr_id=github_pr_id,
        review_status="processing",
        decision="PROCESSING",
    )

    try:
        logger.info("📥 Fetching PR files from GitHub")
        diff = await fetch_diff(owner, repo, pr_number)
        if diff is None:
            logger.warning(f"⚠️ [AI_REVIEW_TASK] Could not fetch diff for {owner}/{repo} PR #{pr_number}")
            await update_pull_request_review_results(
                github_pr_id=github_pr_id,
                review_status="failed",
                decision="ERROR",
                review_summary="Failed to fetch git diff from GitHub API.",
            )
            return

        if not diff.strip():
            logger.info(f"⏭️ [AI_REVIEW_TASK] Empty diff for {owner}/{repo} PR #{pr_number} — marked SAFE.")
            await update_pull_request_review_results(
                github_pr_id=github_pr_id,
                review_status="success",
                decision="SAFE",
                issues_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                coverage_percentage=100.0,
                review_summary="No code changes found in diff.",
                issues_json="[]",
            )
            return

        logger.info("📥 PR files downloaded successfully")
        
        ai_service = get_ai_service()
        if not ai_service.is_configured():
            logger.error("❌ AI service not configured - skipping analysis")
            await update_pull_request_review_results(
                github_pr_id=github_pr_id,
                review_status="failed",
                decision="ERROR",
                review_summary="AI service not configured: GROQ_API_KEY missing or invalid",
                issues_json="[]",
            )
            return
        
        analysis = await ai_service.analyze_code(diff)

        status_flag = analysis.get("status", "success")
        if status_flag == "failed":
            reason = analysis.get("reason", "Unknown AI error")
            logger.warning(f"❌ [AI_REVIEW_TASK] AI analysis failed for PR #{pr_number}: {reason}")
            await update_pull_request_review_results(
                github_pr_id=github_pr_id,
                review_status="failed",
                decision="ANALYSIS_INCOMPLETE" if reason == "RATE_LIMIT" else "ERROR",
                review_summary=f"AI analysis failed: {reason}",
                issues_json="[]",
            )
            return

        # Normalize issue dictionary keys for filter_service requirements
        raw_issues = analysis.get("issues", [])
        for issue in raw_issues:
            if "fix" not in issue and "suggested_fix" in issue:
                issue["fix"] = issue["suggested_fix"]
            if "type" not in issue:
                issue["type"] = issue.get("category", issue.get("severity", "security"))

        filtered_issues = parse_and_filter_issues({"issues": raw_issues}, diff)

        diff_mapping = DiffValidator.parse_diff_mapping(diff)
        valid_issues = []
        high_c = 0
        medium_c = 0
        low_c = 0

        for issue in filtered_issues:
            file_path = issue.get("file", "")
            fix_code = issue.get("suggested_fix") or issue.get("fix", "")

            # DiffValidator.validate_issue checks line presence & updates issue['line'] in-place if nearby
            if not DiffValidator.validate_issue(issue, diff_mapping):
                continue

            if fix_code and file_path.endswith(".py"):
                if not SyntaxValidator.is_valid_python(fix_code):
                    continue

            valid_issues.append(issue)
            sev = str(issue.get("severity", "medium")).lower()
            if sev == "high" or sev == "critical":
                high_c += 1
            elif sev == "low":
                low_c += 1
            else:
                medium_c += 1

        if high_c > 0:
            decision = "BLOCK"
        elif medium_c > 0:
            decision = "REVIEW_REQUIRED"
        else:
            decision = "SAFE"

        coverage = float(analysis.get("coverage", 100.0))
        total_chunks = analysis.get("total_chunks", 1)
        processed_chunks = analysis.get("processed_chunks", 1)
        if total_chunks > 0 and coverage == 100.0:
            coverage = round((processed_chunks / total_chunks) * 100.0, 1)

        summary = f"Analyzed {len(valid_issues)} issues across diff. Decision: {decision}."

        issues_json_str = json.dumps(valid_issues)
        await update_pull_request_review_results(
            github_pr_id=github_pr_id,
            review_status="success",
            decision=decision,
            issues_count=len(valid_issues),
            high_count=high_c,
            medium_count=medium_c,
            low_count=low_c,
            coverage_percentage=coverage,
            review_summary=summary,
            issues_json=issues_json_str,
        )
        logger.info(f"✅ [AI_REVIEW_TASK] Completed AI review for PR #{pr_number}: decision={decision}, issues={len(valid_issues)}")

        # Phase 2.2 — Publish review to GitHub
        logger.info("📤 Posting review to GitHub")
        try:
            install_id = installation_id
            if not install_id:
                install_id = await get_installation_id_for_repo(owner, repo)

            pub_result = await publish_review(
                github_pr_id=github_pr_id,
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                head_sha=head_sha or "",
                decision=decision,
                issues_json=issues_json_str,
                review_summary=summary,
                installation_id=install_id,
            )
            if pub_result.get("status") == "success":
                logger.info(
                    f"📝 [AI_REVIEW_TASK] GitHub review published: "
                    f"review_id={pub_result.get('review_id')}, "
                    f"comments={pub_result.get('comments_posted')}"
                )
                logger.info("✅ Review successfully created")
            else:
                logger.warning(f"⚠️ [AI_REVIEW_TASK] GitHub review publish failed: {pub_result.get('error')}")
        except Exception as pub_exc:
            logger.error(f"💥 [AI_REVIEW_TASK] ReviewPublisher raised: {pub_exc}", exc_info=True)

    except Exception as e:
        logger.error(f"💥 [AI_REVIEW_TASK] Exception during review for PR #{pr_number}: {str(e)}", exc_info=True)
        await update_pull_request_review_results(
            github_pr_id=github_pr_id,
            review_status="failed",
            decision="ERROR",
            review_summary=f"Internal error during review: {str(e)}",
        )


class PRService:
    """Service layer handling pull request webhook ingestion and queries."""

    @classmethod
    async def process_pull_request_event(
        cls,
        payload: Dict[str, Any],
        delivery_id: Optional[str] = None,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        """
        Parses GitHub `pull_request` webhook payload and updates local database.

        Supported actions: opened, edited, reopened, ready_for_review, closed, synchronize.
        Launches background AI review task for: opened, reopened, ready_for_review, synchronize.
        """
        logger.info(f"🚀 [PR_SERVICE] process_pull_request_event() called with delivery_id={delivery_id}")
        
        action = payload.get("action", "").lower()
        logger.info(f"📋 [PR_SERVICE] Action: {action}")
        
        if action not in SUPPORTED_PR_ACTIONS:
            logger.info(f"ℹ️ [PR_SERVICE] Safe ignore: unsupported PR action '{action}'")
            return {
                "status": "ignored",
                "reason": f"unsupported action: {action}",
                "action": action,
            }

        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})
        sender_data = payload.get("sender", {})
        
        logger.info(f"📋 [PR_SERVICE] PR data keys: {list(pr_data.keys())}")
        logger.info(f"📋 [PR_SERVICE] Repo data: {repo_data.get('full_name')}")

        if not pr_data:
            logger.warning("❌ [PR_SERVICE] Webhook payload missing 'pull_request' object.")
            return {"status": "error", "reason": "missing pull_request object"}

        github_pr_id = pr_data.get("id") or pr_data.get("number")
        number = pr_data.get("number") or 0
        repo_full_name = repo_data.get("full_name", "")
        owner_name = repo_data.get("owner", {}).get("login", "")

        if not github_pr_id:
            github_pr_id = (hash(f"{repo_full_name}#{number}") & 0x7FFFFFFF) or 1

        if not owner_name and "/" in repo_full_name:
            owner_name = repo_full_name.split("/")[0]

        repo_name = repo_data.get("name", "")
        if not repo_name and "/" in repo_full_name:
            repo_name = repo_full_name.split("/")[1]

        # Determine state & merge status
        raw_state = pr_data.get("state", "open").lower()
        is_merged = bool(pr_data.get("merged", False))
        if action == "closed" and is_merged:
            state = "closed"
        else:
            state = raw_state

        is_draft = bool(pr_data.get("draft", False))

        # Extract branches and SHAs
        head_data = pr_data.get("head", {})
        base_data = pr_data.get("base", {})

        head_branch = head_data.get("ref", "")
        head_sha = head_data.get("sha", "")
        base_branch = base_data.get("ref", "main")
        base_sha = base_data.get("sha", "")

        author_data = pr_data.get("user", {})
        author_login = author_data.get("login") or sender_data.get("login", "unknown")
        author_avatar = author_data.get("avatar_url", "")

        # Labels & Reviewers
        labels = [l.get("name") for l in pr_data.get("labels", []) if isinstance(l, dict)]
        requested_reviewers = [
            r.get("login") for r in pr_data.get("requested_reviewers", []) if isinstance(r, dict)
        ]

        normalized_data = {
            "github_pr_id": github_pr_id,
            "repository_id": repo_data.get("id"),
            "repository_name": repo_full_name or f"{owner_name}/{repo_name}",
            "owner": owner_name,
            "number": number,
            "title": pr_data.get("title", ""),
            "body": pr_data.get("body", ""),
            "state": state,
            "draft": is_draft,
            "merged": is_merged,
            "mergeable": pr_data.get("mergeable", True),
            "author_login": author_login,
            "author_avatar": author_avatar,
            "base_branch": base_branch,
            "head_branch": head_branch,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "created_at": pr_data.get("created_at"),
            "updated_at": pr_data.get("updated_at"),
            "closed_at": pr_data.get("closed_at"),
            "merged_at": pr_data.get("merged_at"),
            "html_url": pr_data.get("html_url", ""),
            "api_url": pr_data.get("url", ""),
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "changed_files": pr_data.get("changed_files", 0),
            "commits": pr_data.get("commits", 0),
            "labels": labels,
            "requested_reviewers": requested_reviewers,
            "raw_payload": payload,
        }

        stored_pr = await store_upsert_pull_request(normalized_data)
        logger.info(
            f"✅ [PR_SERVICE] Upserted PR #{number} ({state}, merged={is_merged}, draft={is_draft}) "
            f"for '{normalized_data['repository_name']}'"
        )

        # Dispatch background AI review task for supported trigger actions
        ai_task_dispatched = False
        logger.info(f"🔍 [PR_SERVICE] Checking AI task dispatch: background_tasks={background_tasks is not None}, action in AI_TRIGGER_ACTIONS={action in AI_TRIGGER_ACTIONS}")
        logger.info(f"🔍 [PR_SERVICE] background_tasks type: {type(background_tasks)}")
        logger.info(f"🔍 [PR_SERVICE] AI_TRIGGER_ACTIONS: {AI_TRIGGER_ACTIONS}")
        
        if background_tasks is not None and action in AI_TRIGGER_ACTIONS:
            logger.info(f"🚀 [PR_SERVICE] ===== ABOUT TO ADD BACKGROUND TASK FOR PR #{number} =====")
            logger.info(f"🚀 [PR_SERVICE] Task parameters: github_pr_id={github_pr_id}, owner={owner_name}, repo={repo_name}, pr_number={number}, head_sha={head_sha}")
            background_tasks.add_task(
                run_ai_review_task,
                github_pr_id=github_pr_id,
                owner=owner_name,
                repo=repo_name,
                pr_number=number,
                head_sha=head_sha,
            )
            ai_task_dispatched = True
            logger.info(f"✅ [PR_SERVICE] ===== BACKGROUND TASK ADDED FOR PR #{number} =====")
            logger.info(f"✅ [PR_SERVICE] Scheduled background AI review task for PR #{number} (action='{action}')")
        else:
            logger.warning(f"⚠️ [PR_SERVICE] AI task NOT dispatched: background_tasks={background_tasks is not None}, action={action}, trigger_actions={AI_TRIGGER_ACTIONS}")
            if background_tasks is None:
                logger.error(f"❌ [PR_SERVICE] background_tasks is None - this prevents AI review execution")
            if action not in AI_TRIGGER_ACTIONS:
                logger.warning(f"⚠️ [PR_SERVICE] Action '{action}' not in AI_TRIGGER_ACTIONS {AI_TRIGGER_ACTIONS}")

        return {
            "status": "processed",
            "event": "pull_request",
            "action": action,
            "pr_number": number,
            "repository": normalized_data["repository_name"],
            "state": state,
            "merged": is_merged,
            "draft": is_draft,
            "ai_review_dispatched": ai_task_dispatched,
            "delivery_id": delivery_id,
        }

    @classmethod
    async def get_pull_request(
        cls, number: int, repository_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieves single PR details."""
        return await store_get_pull_request(number, repository_name)

    @classmethod
    async def list_pull_requests(
        cls,
        page: int = 1,
        per_page: int = 20,
        state_filter: Optional[str] = None,
        repository_name: Optional[str] = None,
        author: Optional[str] = None,
        decision: Optional[str] = None,
        review_status: Optional[str] = None,
        sort: Optional[str] = "newest",
        date_range: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves paginated PRs with optional multi-field filters, search, and sorting."""
        return await store_list_pull_requests(
            page=page,
            per_page=per_page,
            state_filter=state_filter,
            repository_name=repository_name,
            author=author,
            decision=decision,
            review_status=review_status,
            sort=sort,
            date_range=date_range,
            search_query=search_query,
        )

    @classmethod
    async def get_pr_stats(cls) -> Dict[str, Any]:
        """Retrieves PR metrics summary & AI dashboard telemetry."""
        return await store_get_pr_stats()


    @classmethod
    async def publish_pr_review(
        cls,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        """
        On-demand review publisher for POST /api/prs/{owner}/{repo}/{number}/publish-review.

        Fetches the latest AI analysis results from DB for the given PR and
        publishes them to GitHub. Prevents duplicate submission.
        """
        # Resolve PR record from DB
        pr = await store_get_pull_request(pr_number, repository_name=f"{owner}/{repo}")
        if not pr:
            raise ValueError(f"Pull request {owner}/{repo}#{pr_number} not found in database.")

        github_pr_id = pr.get("github_pr_id")
        if not github_pr_id:
            raise ValueError(f"github_pr_id missing for {owner}/{repo}#{pr_number}.")

        # Duplicate publish guard
        if pr.get("review_posted"):
            existing_review_id = pr.get("github_review_id")
            existing_comments = len(json.loads(pr.get("issues_json") or "[]"))
            logger.info(
                f"[PRService] Review already posted for {owner}/{repo}#{pr_number} "
                f"(review_id={existing_review_id}). Returning cached result."
            )
            return {
                "status": "already_published",
                "review_id": existing_review_id,
                "comments_posted": existing_comments,
                "review_posted_at": pr.get("review_posted_at"),
            }

        decision = pr.get("decision") or "PENDING"
        if decision in ("PENDING", "PROCESSING", "ERROR", ""):
            raise ValueError(
                f"AI review is not yet complete for {owner}/{repo}#{pr_number} "
                f"(current status: {pr.get('review_status')}, decision: {decision}). "
                f"Wait for the background task to finish."
            )

        install_id = await get_installation_id_for_repo(owner, repo)

        result = await publish_review(
            github_pr_id=github_pr_id,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            head_sha=pr.get("head_sha") or "",
            decision=decision,
            issues_json=pr.get("issues_json") or "[]",
            review_summary=pr.get("review_summary"),
            installation_id=install_id,
        )
        return result
