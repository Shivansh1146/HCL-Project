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
from typing import Any, Dict, List, Optional, Set

import httpx

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

    Suggestion-block validation invariant (enforced here as the final gate):
      - fix must be non-empty and non-None
      - fix.strip() must not be empty
      - fix.strip() must not equal the current source line (new_content)
      - fix.strip() must not equal the old source line (old_content)
      If any check fails, the issue is posted as a textual comment without a suggestion.
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

        # -----------------------------------------------------------------------
        # Suggestion validation gate
        # Priority 1: use the pre-validated suggestion string set by
        #             DiffValidator.generate_suggestion() in main.py pipeline
        #             (stored as issue["_validated_suggestion"]).
        # Priority 2: fall back to raw fix field ONLY after strict validation.
        # If neither passes, emit a textual comment with no suggestion block.
        # -----------------------------------------------------------------------
        suggestion_block: str = ""

        validated_suggestion = issue.get("_validated_suggestion")
        if validated_suggestion and isinstance(validated_suggestion, str) and validated_suggestion.strip():
            # Already validated upstream by DiffValidator.generate_suggestion
            suggestion_block = validated_suggestion
            logger.info(
                f"[SUGGESTION_VALIDATION] PASSED (pre-validated) — {file_path}:{line}"
            )
        else:
            # Fallback: validate raw fix field before using it
            fix = issue.get("fix") or ""
            fix_str = fix.strip() if isinstance(fix, str) else ""

            if not fix_str or fix_str.lower() == "none":
                logger.info(
                    f"[SUGGESTION_VALIDATION] REJECTED (empty fix) — {file_path}:{line}"
                )
            else:
                old_code = (issue.get("_old_content") or "").strip()
                new_code = (issue.get("_new_content") or "").strip()

                if new_code and fix_str == new_code:
                    logger.warning(
                        f"[SUGGESTION_VALIDATION] REJECTED: fix == current source line "
                        f"(no-op suggestion) for {file_path}:{line}"
                    )
                elif old_code and fix_str == old_code:
                    logger.warning(
                        f"[SUGGESTION_VALIDATION] REJECTED: fix == old source line "
                        f"for {file_path}:{line}"
                    )
                else:
                    suggestion_block = f"```suggestion\n{fix_str}\n```"
                    logger.info(
                        f"[SUGGESTION_VALIDATION] PASSED (raw fix) — {file_path}:{line}"
                    )

        if suggestion_block:
            comment_body = (
                f"{severity_emoji} **[{severity}] {title}**\n\n"
                f"{description}\n\n"
                f"{suggestion_block}"
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


async def _fetch_pr_changed_files(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> Optional[Set[str]]:
    """
    Fetch the set of filenames actually changed in this PR from GitHub.
    Returns None if the request fails (caller should treat all paths as unverifiable).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            files = {f["filename"] for f in resp.json() if "filename" in f}
            logger.info(f"[ReviewPublisher] PR #{pr_number} changed files: {files}")
            return files
        logger.warning(
            f"[ReviewPublisher] Could not fetch PR files ({resp.status_code}): {resp.text[:200]}"
        )
    except Exception as exc:
        logger.warning(f"[ReviewPublisher] Exception fetching PR files: {exc}")
    return None


def _resolve_path_against_files(
    ai_path: str,
    changed_files: Set[str],
) -> Optional[str]:
    """
    Resolve an AI-supplied path against the authoritative set of changed files.

    Rules:
    1. Exact match → return as-is.
    2. Exactly one file in changed_files contains ai_path as a suffix, or
       ai_path (without extension) matches exactly one file → return that file.
    3. Otherwise → return None (drop the inline comment).
    """
    if ai_path in changed_files:
        return ai_path

    # Strip extension from ai_path and try to match
    ai_stem = ai_path.rsplit(".", 1)[0] if "." in ai_path else ai_path

    candidates = [
        f for f in changed_files
        if f == ai_stem                          # exact stem match (security.py → security)
        or f.endswith("/" + ai_path)            # path suffix (src/security.py)
        or f.endswith("/" + ai_stem)            # stem suffix  (src/security)
        or ai_path.endswith("/" + f)            # ai_path is longer but ends with actual file
    ]

    if len(candidates) == 1:
        logger.info(
            f"[ReviewPublisher] Resolved path '{ai_path}' → '{candidates[0]}'"
        )
        return candidates[0]

    if len(candidates) > 1:
        logger.warning(
            f"[ReviewPublisher] Ambiguous path '{ai_path}' matches {candidates} — dropping inline comment"
        )
    else:
        logger.warning(
            f"[ReviewPublisher] Path '{ai_path}' not found in PR changed files {changed_files} — dropping inline comment"
        )
    return None


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
    # Build the review body unconditionally — this is always posted regardless of inline comments.
    review_body = _build_review_body(decision, issues, review_summary)

    # Resolve installation access token
    token: Optional[str] = None
    if installation_id:
        try:
            app_service = get_app_service()
            token = await app_service.get_installation_access_token(installation_id)
            if token:
                logger.info(f"[ReviewPublisher] Got installation token for installation={installation_id}")
            else:
                logger.warning(f"[ReviewPublisher] Empty token from app_service for installation={installation_id}, falling back to GITHUB_TOKEN")
        except Exception as exc:
            logger.warning(f"[ReviewPublisher] Token fetch failed: {exc}. Falling back to GITHUB_TOKEN.")

    if not token:
        token = os.getenv("GITHUB_TOKEN", "")

    # ------------------------------------------------------------------
    # Path validation: fetch the actual changed-file list from GitHub and
    # resolve / drop each issue path BEFORE building inline comments.
    # This is the authoritative gate — it runs at publish time so that
    # stale DB data (AI-hallucinated extensions like security.py) cannot
    # reach the GitHub reviews API.
    # ------------------------------------------------------------------
    changed_files: Optional[Set[str]] = await _fetch_pr_changed_files(
        owner, repo, pr_number, token
    )

    if changed_files is not None:
        resolved_issues: List[Dict[str, Any]] = []
        for issue in issues:
            ai_path = issue.get("file") or issue.get("path") or ""
            if not ai_path:
                resolved_issues.append(issue)  # no path → will be skipped by _build_inline_comments
                continue
            resolved = _resolve_path_against_files(ai_path, changed_files)
            if resolved is not None:
                # Overwrite with the authoritative GitHub path
                issue = dict(issue)
                issue["file"] = resolved
                issue["path"] = resolved
                resolved_issues.append(issue)
            else:
                logger.warning(
                    f"[ReviewPublisher] Dropping inline comment for unresolvable path '{ai_path}'"
                )
        issues_for_inline = resolved_issues
    else:
        # Could not fetch file list — proceed without inline comments to avoid 422
        logger.warning(
            "[ReviewPublisher] Could not verify changed files — posting review body only (no inline comments)"
        )
        issues_for_inline = []

    inline_comments = _build_inline_comments(issues_for_inline, head_sha)

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
        persisted_pr = await update_pull_request_review_published(
            github_pr_id=github_pr_id,
            review_id=review_id,
            posted_at=now_str,
            repository_name=f"{owner}/{repo}",
            number=pr_number,
        )
        if persisted_pr is None:
            raise RuntimeError("No matching pull_requests row was updated.")
    except Exception as exc:
        logger.error(f"[ReviewPublisher] DB persistence of review_posted failed: {exc}")
        return {
            "status": "error",
            "review_id": review_id,
            "comments_posted": len(inline_comments),
            "error": f"GitHub review was created, but local publication state was not saved: {exc}",
        }

    logger.info(
        f"✅ [ReviewPublisher] Review published for {owner}/{repo}#{pr_number}: "
        f"review_id={review_id}, event={github_event}, comments={len(inline_comments)}"
    )
    return {
        "status": "success",
        "review_id": review_id,
        "comments_posted": len(inline_comments),
    }
