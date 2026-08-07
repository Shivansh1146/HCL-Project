"""
routers/app_router.py — FastAPI endpoints for GitHub App management.

Routes:
- GET  /api/app/installations -> List all installations accessible to user/orgs
- GET  /api/app/installations/{installation_id}/repos -> List repos for installation
- POST /api/app/installations/{installation_id}/repos/select -> Save repository selections
- POST /api/app/webhook -> Webhook receiver for GitHub App installation events
"""

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, List

from auth.app_service import GitHubAppService, get_app_service
from auth.dependencies import get_current_user_optional, require_auth
from auth.models import (
    AccountType,
    InstallationResponse,
    InstallationStatus,
    InstallationTokenResponse,
    RepoResponse,
    SelectReposRequest,
    SelectReposResponse,
    User,
)
from auth.store import (
    get_installation_by_id,
    get_installations_for_user,
    get_oauth_token,
    get_repos_for_user,
    get_selected_repos_for_installation,
    sync_repos_in_db,
    upsert_installation,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger("backend")

router = APIRouter(prefix="/api/app", tags=["GitHub App"])


@router.get("/installations", response_model=List[InstallationResponse])
async def list_user_installations(
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """
    Lists all GitHub App installations associated with the authenticated user across personal & org accounts.
    """
    oauth_token = await get_oauth_token(user.id)
    user_access_token = oauth_token.access_token if oauth_token else ""
    await app_service.sync_user_installations(user.id, user_access_token)
    db_installations = await get_installations_for_user(user.id)
    results: List[InstallationResponse] = []

    for inst in db_installations:
        # Fetch repos for this installation

        repos_raw = await app_service.list_installation_repos(
            installation_id=inst.installation_id
        )

        selected_repos = await get_selected_repos_for_installation(inst.id)
        enabled_set = {r.repo_full_name.lower() for r in selected_repos}

        repo_models = [
            RepoResponse(
                repo_id=r.get("repo_id") or r.get("id", 0),
                full_name=r.get("full_name", ""),
                name=r.get("name", ""),
                owner_login=r.get("owner", {}).get("login", ""),
                private=r.get("private", False),
                default_branch=r.get("default_branch", "main"),
                enabled=(r.get("full_name", "").lower() in enabled_set),
            )
            for r in repos_raw
        ]

        results.append(
            InstallationResponse(
                installation_id=inst.installation_id,
                account_login=inst.account_login,
                account_type=inst.account_type,
                status=inst.status,
                repositories=repo_models,
            )
        )

    return results


@router.get("/installations/{installation_id}/repos", response_model=List[RepoResponse])
async def list_installation_repos_endpoint(
    installation_id: int,
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """Lists all repositories available for a specific installation."""
    inst = await get_installation_by_id(installation_id)
    if not inst:
        # Try syncing directly from GitHub App API if not in local DB yet
        inst = await app_service.sync_installation_from_github(
            installation_id, user_id=user.id
        )
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation {installation_id} not found.",
            )

    oauth_token = await get_oauth_token(user.id)
    user_access_token = oauth_token.access_token if oauth_token else None

    repos_raw = await app_service.list_installation_repos(
        installation_id=installation_id
    )

    selected = await get_selected_repos_for_installation(inst.id)
    enabled_set = {r.repo_full_name.lower() for r in selected}

    return [
        RepoResponse(
            repo_id=r.get("repo_id") or r.get("id", 0),
            full_name=r.get("full_name", ""),
            name=r.get("name", ""),
            owner_login=r.get("owner", {}).get("login", ""),
            private=r.get("private", False),
            default_branch=r.get("default_branch", "main"),
            enabled=(r.get("full_name", "").lower() in enabled_set),
        )
        for r in repos_raw
    ]


@router.post(
    "/installations/{installation_id}/sync", response_model=InstallationResponse
)
async def sync_installation_endpoint(
    installation_id: int,
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """
    Performs an explicit synchronization of GitHub App installation metadata & repositories from GitHub API.
    """
    inst = await app_service.sync_installation_from_github(
        installation_id, user_id=user.id
    )
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unable to sync installation {installation_id} from GitHub API.",
        )

    repos_raw = await app_service.list_installation_repos(
        installation_id=installation_id
    )

    db_rows = await sync_repos_in_db(inst.id, repos_raw)
    logger.info(
        "Installation sync saved %d repositories for installation_id=%s",
        len(db_rows),
        installation_id,
    )

    selected = await get_selected_repos_for_installation(inst.id)
    enabled_set = {r.repo_full_name.lower() for r in selected}

    repo_models = [
        RepoResponse(
            repo_id=r.get("repo_id") or r.get("id", 0),
            full_name=r.get("full_name", ""),
            name=r.get("name", ""),
            owner_login=r.get("owner", {}).get("login", ""),
            private=r.get("private", False),
            default_branch=r.get("default_branch", "main"),
            enabled=(r.get("full_name", "").lower() in enabled_set),
        )
        for r in repos_raw
    ]

    return InstallationResponse(
        installation_id=inst.installation_id,
        account_login=inst.account_login,
        account_type=inst.account_type,
        status=inst.status,
        repositories=repo_models,
    )


@router.get("/installations/{installation_id}/token-status")
async def get_token_status(
    installation_id: int,
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """
    GET /api/app/installations/{installation_id}/token-status

    Returns the current cache state for the installation access token.
    Never makes a network request — purely diagnostic.

    Response fields:
      - cached          : bool   — token is in cache
      - valid           : bool   — token is non-expired (accounting for 5 min buffer)
      - expires_at      : str?   — ISO-8601 UTC expiry time
      - seconds_until_expiry : float? — seconds remaining until actual expiry
      - fetched_at      : str?   — when the token was last fetched
      - refresh_buffer_seconds : int — proactive refresh window (default 300)
    """
    # Validate the installation belongs to this user
    inst = await get_installation_by_id(installation_id)
    if not inst or inst.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Installation {installation_id} not found.",
        )

    ts = app_service.get_token_status(installation_id)
    return ts.as_dict()


@router.post(
    "/installations/{installation_id}/access_tokens",
    response_model=InstallationTokenResponse,
)
async def create_installation_access_token(
    installation_id: int,
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """Create or return a cached GitHub installation access token."""
    inst = await get_installation_by_id(installation_id)
    if not inst or inst.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Installation {installation_id} not found.",
        )

    try:
        return await app_service.create_installation_access_token_response(
            installation_id
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/installations/{installation_id}/token-invalidate")
async def invalidate_token_cache(
    installation_id: int,
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """
    POST /api/app/installations/{installation_id}/token-invalidate

    Forces the token cache to discard the stored token for this installation.
    The next call to any GitHub API that requires this installation's token
    will request a fresh one from GitHub.

    Useful for:
      - Forcing token rotation after a suspected compromise.
      - Testing refresh behavior.
    """
    inst = await get_installation_by_id(installation_id)
    if not inst or inst.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Installation {installation_id} not found.",
        )

    app_service.invalidate_token(installation_id)
    return {
        "status": "invalidated",
        "installation_id": installation_id,
        "message": "Token cache cleared. Next request will fetch a fresh token from GitHub.",
    }


app_router = APIRouter(prefix="/app", tags=["GitHub App Alias"])


@app_router.post(
    "/installations/{installation_id}/access_tokens",
    response_model=InstallationTokenResponse,
)
async def create_installation_access_token_public(
    installation_id: int,
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    return await create_installation_access_token(
        installation_id=installation_id,
        user=user,
        app_service=app_service,
    )


@router.post(
    "/installations/{installation_id}/repos/select", response_model=SelectReposResponse
)
async def select_repositories_endpoint(
    installation_id: int,
    body: SelectReposRequest,
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """Saves selected repositories for an installation to enable AI code review coverage."""
    try:
        enabled, disabled = await app_service.update_selected_repositories(
            installation_id=installation_id, repo_full_names=body.repo_full_names
        )
        return SelectReposResponse(
            installation_id=installation_id,
            enabled_repos=enabled,
            disabled_repos=disabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error saving repository selections: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update repository selections.",
        )


@router.post("/webhook")
async def app_lifecycle_webhook(request: Request):
    """
    Handles GitHub App installation lifecycle webhook events (created, deleted, suspend, unsuspend).
    Updates local installation state in SQLite automatically.
    """
    await _verify_webhook_signature(request)
    payload = await request.json()
    action = payload.get("action")
    installation = payload.get("installation", {})
    inst_id = installation.get("id")

    if not inst_id:
        return {"status": "ignored", "reason": "NO_INSTALLATION_ID"}

    account = installation.get("account", {})

    if action in ("created", "unsuspend"):
        await upsert_installation(
            installation_id=inst_id,
            account_login=account.get("login", "unknown"),
            account_type=account.get("type", "User"),
            target_id=installation.get("target_id", account.get("id", 0)),
            target_type=installation.get("target_type", account.get("type", "User")),
            status="active",
        )
        logger.info(
            f"GitHub App installation {inst_id} ({account.get('login')}) registered/activated."
        )
    elif action in ("deleted", "suspend"):
        await upsert_installation(
            installation_id=inst_id,
            account_login=account.get("login", "unknown"),
            account_type=account.get("type", "User"),
            target_id=installation.get("target_id", account.get("id", 0)),
            target_type=installation.get("target_type", account.get("type", "User")),
            status="suspended" if action == "suspend" else "deleted",
        )
        logger.info(f"GitHub App installation {inst_id} marked as {action}.")

    return {"status": "success", "action": action, "installation_id": inst_id}


@router.get("/install")
async def get_install_url(
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """Return the GitHub App installation URL for the authenticated user."""
    install_url = app_service.get_installation_url()
    if not install_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "GitHub App installation URL is not configured.",
                "missing_configuration": app_service.get_configuration_issues(),
            },
        )
    return {
        "install_url": install_url,
        "configured": app_service.has_app_credentials(),
        "has_install_url": True,
        "missing_configuration": app_service.get_configuration_issues(),
    }


@router.get("/callback")
async def installation_callback(
    installation_id: int | None = None,
    setup_action: str | None = None,
    user: User | None = Depends(get_current_user_optional),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """Return from GitHub App setup, sync accessible installations, and open the dashboard."""
    if user:
        oauth_token = await get_oauth_token(user.id)
        await app_service.sync_user_installations(
            user.id, oauth_token.access_token if oauth_token else ""
        )
        if installation_id and app_service.is_configured():
            await app_service.sync_installation_from_github(
                installation_id, user_id=user.id
            )
    return RedirectResponse(url="/#/dashboard", status_code=status.HTTP_302_FOUND)


async def _verify_webhook_signature(request: Request) -> None:
    """Verify GitHub's sha256 webhook signature before accepting lifecycle events."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured.",
        )
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = (
        "sha256="
        + hmac.new(secret.encode(), await request.body(), hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub webhook signature.",
        )


# Convenience / Alias Endpoints


@router.get("/status")
async def get_app_status_endpoint(
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """Returns general GitHub App installation status."""

    # First try syncing directly from the GitHub App API using the app JWT.
    synced_installations = await app_service.sync_installations_from_github_app(user.id)

    # If direct app sync yielded nothing, fall back to the user OAuth token flow.
    if not synced_installations:
        oauth_token = await get_oauth_token(user.id)
        user_access_token = oauth_token.access_token if oauth_token else ""
        await app_service.sync_user_installations(user.id, user_access_token)

    installations = await get_installations_for_user(user.id)
    active_count = sum(
        1 for i in installations if i.status == InstallationStatus.ACTIVE
    )
    install_url = app_service.get_installation_url()
    return {
        "status": (
            "installed"
            if active_count > 0
            else (
                "not_configured"
                if not app_service.has_app_credentials()
                else "not_installed"
            )
        ),
        "installations_count": len(installations),
        "active_installations": active_count,
        "connected_account": installations[0].account_login if installations else None,
        "configured": app_service.has_app_credentials(),
        "install_url": install_url or None,
        "has_install_url": bool(install_url),
        "missing_configuration": app_service.get_configuration_issues(),
    }


# Router aliases mounted directly under /api prefix for repository and org management
repo_alias_router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


@repo_alias_router.get("")
async def alias_list_repositories(
    user: User = Depends(require_auth),
):
    """
    GET /api/repositories
    Returns all active repositories across all installations for the authenticated user.
    Reads from the local database (sync first with POST /api/repositories/sync).
    """
    repos = await get_repos_for_user(user.id)
    return repos


@repo_alias_router.post("/sync")
async def sync_repositories(
    user: User = Depends(require_auth),
    app_service: GitHubAppService = Depends(get_app_service),
):
    """
    POST /api/repositories/sync
    Uses the GitHub App installation token to call GET /installation/repositories,
    stores/updates all repos in the DB, marks removed repos as inactive,
    and returns the refreshed repo list.
    """
    try:
        repos = await app_service.sync_all_repositories(user.id)
        logger.info(
            "Repository sync completed for user_id=%s with %d repositories saved",
            user.id,
            len(repos),
        )
        return {
            "status": "success",
            "synced_count": len(repos),
            "repositories": repos,
        }
    except Exception as exc:
        logger.error("Repository sync failed: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repository sync failed: {str(exc)}",
        )


@repo_alias_router.get("/organizations")
async def alias_list_organizations(user: User = Depends(require_auth)):
    """Lists organization accounts associated with user's installations."""
    installations = await get_installations_for_user(user.id)
    orgs = [
        {
            "id": inst.id,
            "login": inst.account_login,
            "type": inst.account_type.value,
            "status": inst.status.value,
        }
        for inst in installations
    ]
    return {"organizations": orgs}
