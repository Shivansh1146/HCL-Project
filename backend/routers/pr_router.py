"""
routers/pr_router.py — FastAPI endpoints for Pull Request reviews and AI details.

Routes:
- GET  /api/prs -> List PR reviews with status/repo filter and search
- GET  /api/prs/{owner}/{repo}/{pr_number} -> Fetch detailed PR analysis and issues list
- POST /api/prs/{owner}/{repo}/{pr_number}/review -> Trigger AI code review re-run
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from auth.models import User
from auth.dependencies import require_auth
from stats_store import list_prs, get_pr_details, upsert_review

logger = logging.getLogger("backend")

router = APIRouter(prefix="/api/prs", tags=["Pull Requests"])


@router.get("")
async def get_pull_requests(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    state: Optional[str] = Query(None, description="Filter by state (open, closed, merged, draft, all)"),
    repo: Optional[str] = Query(None, description="Filter by repository name"),
    author: Optional[str] = Query(None, description="Filter by author username"),
    decision: Optional[str] = Query(None, description="Filter by AI decision (SAFE, BLOCK, REVIEW_REQUIRED, ERROR, all)"),
    review_status: Optional[str] = Query(None, description="Filter by review status (pending, processing, completed, failed, all)"),
    sort: Optional[str] = Query("newest", description="Sort order (newest, oldest, highest_severity, highest_coverage)"),
    date_range: Optional[str] = Query(None, description="Filter by date range (7d, 30d, 90d, all)"),
    q: Optional[str] = Query(None, description="Free text search query"),
    user: User = Depends(require_auth)
):
    """
    GET /api/prs

    Returns a paginated, searchable, and filterable list of PR reviews for the dashboard.
    """
    try:
        from services.pr_service import PRService
        return await PRService.list_pull_requests(
            page=page,
            per_page=per_page,
            state_filter=state,
            repository_name=repo,
            author=author,
            decision=decision,
            review_status=review_status,
            sort=sort,
            date_range=date_range,
            search_query=q,
        )
    except Exception as e:
        logger.error(f"Error fetching PRs list: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pull request list."
        )


@router.get("/stats")
async def get_pull_request_stats(
    user: User = Depends(require_auth)
):
    """
    GET /api/prs/stats

    Returns aggregated metrics for PR state and AI Review Dashboard.
    """
    try:
        from services.pr_service import PRService
        return await PRService.get_pr_stats()
    except Exception as e:
        logger.error(f"Error fetching PR stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve PR statistics."
        )


@router.get("/{number}")
async def get_pull_request_by_number(
    number: int,
    repo: Optional[str] = Query(None, description="Repository name filter"),
    user: User = Depends(require_auth)
):
    """
    GET /api/prs/{number}

    Returns full details for a single pull request by number.
    """
    try:
        from services.pr_service import PRService
        pr = await PRService.get_pull_request(number, repository_name=repo)
        if not pr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pull request #{number} not found."
            )
        return pr
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching PR #{number}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve PR #{number}."
        )


@router.get("/{owner}/{repo}/{pr_number}")
async def get_pull_request_details(
    owner: str,
    repo: str,
    pr_number: int,
    user: User = Depends(require_auth)
):
    """Fetches detailed PR analysis, issues list, decision metrics, and findings JSON."""
    full_name = f"{owner}/{repo}"
    pr = await get_pr_details(full_name, pr_number)
    if not pr:
        from services.pr_service import PRService
        pr_item = await PRService.get_pull_request(pr_number, repository_name=full_name)
        if not pr_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pull request #{pr_number} for {full_name} not found."
            )
        import json
        raw_issues = pr_item.get("issues_json") or "[]"
        issues_list = json.loads(raw_issues) if isinstance(raw_issues, str) else raw_issues
        return {
            "id": pr_item.get("id"),
            "repo": pr_item.get("repository_name") or full_name,
            "owner": pr_item.get("owner") or owner,
            "pr_number": pr_item.get("number") or pr_number,
            "title": pr_item.get("title"),
            "author_login": pr_item.get("author_login"),
            "author_avatar": pr_item.get("author_avatar"),
            "status": pr_item.get("review_status", "pending"),
            "decision": pr_item.get("decision", "PENDING"),
            "reviewed_at": pr_item.get("reviewed_at") or pr_item.get("updated_at"),
            "high_count": pr_item.get("high_count", 0),
            "medium_count": pr_item.get("medium_count", 0),
            "low_count": pr_item.get("low_count", 0),
            "coverage_percentage": pr_item.get("coverage_percentage", 100.0),
            "processing_time_sec": pr_item.get("processing_time_sec", 3.8),
            "review_summary": pr_item.get("review_summary"),
            "issues": issues_list,
            "previous_issues_json": pr_item.get("previous_issues_json"),
            "previous_review_summary": pr_item.get("previous_review_summary"),
            "review_posted": bool(pr_item.get("review_posted")),
            "review_posted_at": pr_item.get("review_posted_at"),
            "github_review_id": pr_item.get("github_review_id"),
            "html_url": pr_item.get("html_url"),
            "raw_payload": pr_item,
        }
    return pr



@router.post("/{owner}/{repo}/{pr_number}/review")
async def trigger_pr_review(
    owner: str,
    repo: str,
    pr_number: int,
    user: User = Depends(require_auth)
):
    """Triggers an on-demand AI code review re-run for a PR."""
    full_name = f"{owner}/{repo}"
    try:
        pr_id = await upsert_review(full_name, pr_number, status="pending")
        return {
            "status": "queued",
            "message": f"AI code review queued for {full_name}#{pr_number}",
            "pr_id": pr_id
        }
    except Exception as e:
        logger.error(f"Error queuing PR review: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue PR review."
        )


@router.post("/{owner}/{repo}/{pr_number}/publish-review")
async def publish_pr_review(
    owner: str,
    repo: str,
    pr_number: int,
    user: User = Depends(require_auth),
):
    """
    POST /api/prs/{owner}/{repo}/{pr_number}/publish-review

    Publishes the completed AI review to the corresponding GitHub Pull Request.
    Reads validated AI results from the database and posts a GitHub PR Review
    with inline comments, a summary body, and the appropriate event type
    (APPROVE / COMMENT / REQUEST_CHANGES) based on the AI decision.

    Returns:
        {
            "status": "success" | "already_published" | "error",
            "review_id": <int>,
            "comments_posted": <int>
        }
    """
    try:
        from services.pr_service import PRService
        result = await PRService.publish_pr_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
        )
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(
            f"Error publishing PR review for {owner}/{repo}#{pr_number}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish review to GitHub: {str(e)}",
        )

