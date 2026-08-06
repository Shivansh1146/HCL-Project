"""
services/review_publisher.py — Phase 2.2: GitHub PR Review Publisher.

Responsibilities:
1. Retrieve AI analysis results and validated issues from the database.
2. Build GitHub Pull Request Review API payload (event, body, inline comments).
3. Obtain installation access token via GitHubAppService / InstallationTokenCache.
4. Publish review to GitHub using GitHubService.post_pull_request_review().
5. Update database with review_posted, review_posted_at, github_review_id.
6. Handle all error scenarios gracefully without crashing the webhook.

Decision → GitHub event mapping:
  SAFE            → APPROVE
  REVIEW_REQUIRED → COMMENT
  BLOCK           → REQUEST_CHANGES
  (anything else) → COMMENT
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("backend.review_publisher")

# Maximum characters for the PR review body sent to GitHub
MAX_REVIEW_BODY_CHARS = 65536

# GitHub event mapping by decision
DECISION_TO_EVENT = {
    "SAFE": "APPROVE",
    "REVIEW_REQUIRED": "COMMENT",
    "BLOCK": "REQUEST_CHANGES",
    "ANALYSIS_INCOMPLETE": "COMMENT",
    "ERROR": "COMMENT",
}


def _build_review_body(decision: str, issues: List[Dict[str, Any]], summary: Optional[str] = None) -> str:
    """Compose the pull request review top-level body."""
    if not issues:
        body = "✅ **AI Review completed.** No significant issues detected.\n\n*This automated review was performed by HCL AI Code Reviewer.*"
        return body

    severity_counts: Dict[str, int] = {}
    for issue in issues:
        sev = (issue.get("severity") or "unknown").upper()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    decision_emoji = {
        "SAFE": "✅",
        "REVIEW_REQUIRED": "⚠️",
        "BLOCK": "🚫",
    }.get(decision, "🤖")

    title = {
        "SAFE": "All issues are minor — no blocking concerns.",
        "REVIEW_REQUIRED": "Issues found that require human review.",
        "BLOCK": "Critical issues found — changes must be addressed before merging.",
    }.get(decision, "Review complete.")

    lines = [
        f"## {decision_emoji} AI Code Review — `{decision}`",
        "",
        f"**{title}**",
        "",
        "### Summary",
    ]

    if summary:
        lines.append(summary)
    else:
        lines.append(f"Found **{len(issues)}** issue(s) across the diff.")

    sev_parts = []
    for sev in ("HIGH", "MEDIUM", "LOW"):
        count = severity_counts.get(sev, 0)
        if count:
            emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "🔍")
            sev_parts.append(f"{emoji} {sev}: **{count}**")
    if sev_parts:
        lines.append("")
        lines.append(" · ".join(sev_parts))

    lines.extend([
        "",
        "---",
        "*Automated review by [HCL AI Code Reviewer](https://github.com). Inline comments are attached below.*",
    ])

    body = "\n".join(lines)
    return body[:MAX_REVIEW_BODY_CHARS]


def _build_inline_comments(issues: List[Dict[str, Any]], commit_sha: str) -> List[Dict[str, Any]]:
    """
    Build the GitHub 'comments' array for the PR Review payload.
    Only includes issues that have been validated by DiffValidator (line is set and valid).
    Issues without a valid path or line number are silently skipped.
    """
    comments = []
    for issue in issues:
        file_path = issue.get("file") or issue.get("path") or ""
        if not file_path:
            logger.debug(f"Skipping issue without file path: {issue.get('title')}")
            continue

        try:
            line = int(issue.get("line", 0) or 0)
        except (ValueError, TypeError):
            line = 0

        if line <= 0:
            logger.debug(f"Skipping issue with invalid line={line}: {issue.get('title')} in {file_path}")
            continue

        severity = (issue.get("severity") or "medium").upper()
        severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "🔍")
        title = issue.get("title") or "Code Issue"
        description = issue.get("description") or ""

        fix = issue.get("fix") or ""
        if fix and isinstance(fix, str) and fix.strip() and fix.strip() != "None":
            comment_body = (
                f"{severity_emoji} **[{severity}] {title}**\n\n"
                f"{description}\n\n"
                f"```suggestion\n{fix}\n```"
            )
        else:
            comment_body = (
                f"{severity_emoji} **[{severity}] {title}**\n\n"
                f"{description}\n\n"
                f"*No automated fix available — manual review required.*"
            )

        comments.append({
            "path": file_path,
            "line": line,
            "side": "RIGHT",
            "body": comment_body,
        })

    logger.info(f"Built {len(comments)} inline comment(s) from {len(issues)} validated issue(s).")
    return comments


async def publish_review(
    github_pr_id: int,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    decision: str,
    issues_json: str,
    review_summary: Optional[str] = None,
    installation_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Publish AI review results to GitHub as a Pull Request Review.

    Args:
        github_pr_id:    The local DB primary key for this PR.
        owner:           Repository owner (login).
        repo:            Repository name.
        pr_number:       GitHub PR number.
        head_sha:        Commit SHA (HEAD of the PR branch).
        decision:        Review decision string: SAFE / REVIEW_REQUIRED / BLOCK / etc.
        issues_json:     JSON string of validated issues (from FilterService/DiffValidator).
        review_summary:  Optional text summary from AI analysis.
        installation_id: GitHub App installation ID (for token resolution).

    Returns:
        dict with keys: status, review_id, comments_posted
    """
    # Lazy imports to avoid circular dependencies and enable mocking in tests
    from auth.app_service import get_app_service
    from auth.store import update_pull_request_review_published
    from services.github_service import _github_service_instance

    try:
        issues: List[Dict[str, Any]] = json.loads(issues_json or "[]") if issues_json else []
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"[ReviewPublisher] Invalid issues_json for PR #{pr_number}, treating as empty.")
        issues = []

    github_event = DECISION_TO_EVENT.get(decision, "COMMENT")
    review_body = _build_review_body(decision, issues, review_summary)
    inline_comments = _build_inline_comments(issues, head_sha)

    # Resolve installation access token
    token: Optional[str] = None
    if installation_id:
        try:
            app_service = get_app_service()
            token = await app_service.get_installation_access_token(installation_id)
            if token:
                logger.debug(f"[ReviewPublisher] Got installation token for installation={installation_id}")
            else:
                logger.warning(f"[ReviewPublisher] Empty token from app_service for installation={installation_id}, falling back to GITHUB_TOKEN")
        except Exception as exc:
            logger.warning(f"[ReviewPublisher] Token fetch failed: {exc}. Falling back to GITHUB_TOKEN.")

    if not token:
        token = os.getenv("GITHUB_TOKEN", "")

    # Post review to GitHub
    try:
        result = await _github_service_instance.post_pull_request_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            event=github_event,
            body=review_body,
            comments=inline_comments,
            commit_sha=head_sha,
            token=token,
        )
    except RuntimeError as exc:
        logger.error(f"[ReviewPublisher] Failed to post review to GitHub for PR #{pr_number}: {exc}")
        return {
            "status": "error",
            "review_id": None,
            "comments_posted": 0,
            "error": str(exc),
        }

    review_id = result.get("review_id")
    now_str = datetime.now(timezone.utc).isoformat()

    # Persist publish state
    try:
        await update_pull_request_review_published(
            github_pr_id=github_pr_id,
            review_id=review_id,
            posted_at=now_str,
        )
    except Exception as exc:
        logger.error(f"[ReviewPublisher] DB persistence of review_posted failed: {exc}")

    logger.info(
        f"✅ [ReviewPublisher] Review published for {owner}/{repo}#{pr_number}: "
        f"review_id={review_id}, event={github_event}, comments={len(inline_comments)}"
    )
    return {
        "status": "success",
        "review_id": review_id,
        "comments_posted": len(inline_comments),
    }
