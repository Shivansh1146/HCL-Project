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
    repo: Optional[str] = Query(None, description="Filter by repository full name"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by review status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_auth)
):
    """Lists PR reviews with optional repository and status filtering."""
    try:
        return await list_prs(repo=repo, status_filter=status_filter, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Error fetching PRs list: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pull request list."
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
