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
    user: User = Depends(require_auth)
):
    """
    GET /api/prs

    Returns a paginated list of ingested GitHub pull requests for the authenticated user.
    """
    try:
        from services.pr_service import PRService
        return await PRService.list_pull_requests(page=page, per_page=per_page, state_filter=state)
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

    Returns aggregated metrics:
    - total: total PRs ingested
    - open: open non-draft PRs
    - closed: closed non-merged PRs
    - merged: merged PRs
    - draft: draft PRs
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
    """Fetches detailed PR analysis, issues list, and decision metrics."""
    full_name = f"{owner}/{repo}"
    pr = await get_pr_details(full_name, pr_number)
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull request #{pr_number} for {full_name} not found."
        )
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
