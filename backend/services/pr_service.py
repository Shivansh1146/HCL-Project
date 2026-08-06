"""
services/pr_service.py — Enterprise Pull Request Processing Service.

Responsibilities:
1. Extract pull request metadata from GitHub webhook payloads.
2. Filter & process supported PR actions: opened, edited, reopened, ready_for_review, closed, synchronize.
3. Perform database persistence (upsert) to store PR state, author details, branches, SHAs, and change metrics.
4. Provide accessors for listing paginated PRs, retrieving PR details, and compiling PR metrics/stats.

NO AI review generation or Groq/OpenAI calls in Phase 1.7.
"""

import logging
from typing import Any, Dict, List, Optional

from auth.store import (
    get_pr_stats as store_get_pr_stats,
    get_pull_request as store_get_pull_request,
    list_pull_requests as store_list_pull_requests,
    upsert_pull_request as store_upsert_pull_request,
)

logger = logging.getLogger("backend")

SUPPORTED_PR_ACTIONS = {
    "opened",
    "edited",
    "reopened",
    "ready_for_review",
    "closed",
    "synchronize",
}


class PRService:
    """Service layer handling pull request webhook ingestion and queries."""

    @classmethod
    async def process_pull_request_event(
        cls, payload: Dict[str, Any], delivery_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses GitHub `pull_request` webhook payload and updates local database.

        Supported actions: opened, edited, reopened, ready_for_review, closed, synchronize.
        """
        action = payload.get("action", "").lower()
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

        return {
            "status": "processed",
            "event": "pull_request",
            "action": action,
            "pr_number": number,
            "repository": normalized_data["repository_name"],
            "state": state,
            "merged": is_merged,
            "draft": is_draft,
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
        cls, page: int = 1, per_page: int = 20, state_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves paginated PRs with optional state filter."""
        return await store_list_pull_requests(page=page, per_page=per_page, state_filter=state_filter)

    @classmethod
    async def get_pr_stats(cls) -> Dict[str, int]:
        """Retrieves PR metrics summary."""
        return await store_get_pr_stats()
