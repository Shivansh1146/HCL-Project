"""
auth/models.py — Pydantic models and typed dataclasses for auth domain.

Follows Single Responsibility: pure data contracts, no business logic.
All fields typed; optional fields use Optional[T] = None pattern.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AccountType(str, Enum):
    """GitHub account type for an installation target."""
    USER = "User"
    ORGANIZATION = "Organization"


class InstallationStatus(str, Enum):
    """Lifecycle status of a GitHub App installation."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AuditSeverity(str, Enum):
    """Severity classification for security and compliance audit logs."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SyncStatus(str, Enum):
    """Synchronization state of a repository or installation."""
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Domain Models (returned by service layer, stored in DB)
# ---------------------------------------------------------------------------

class User(BaseModel):
    """Represents an authenticated GitHub user."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_id: int
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class OAuthToken(BaseModel):
    """OAuth token record (access token stored encrypted)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    access_token: str
    token_type: str = "bearer"
    scope: str = ""
    created_at: datetime
    expires_at: Optional[datetime] = None


class Installation(BaseModel):
    """GitHub App installation record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    installation_id: int          # GitHub's numeric installation ID
    account_login: str            # Owner login (user or org)
    account_type: AccountType
    target_id: int                # GitHub account ID of the owner
    target_type: str
    status: InstallationStatus = InstallationStatus.ACTIVE
    user_id: Optional[int] = None # The user who triggered install (may be None for org-level)
    suspended_at: Optional[datetime] = None
    removed_at: Optional[datetime] = None
    last_token_refresh: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SelectedRepo(BaseModel):
    """A repository selected by a user for AI review coverage."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    installation_id: int          # FK → installations.id (our internal id)
    repo_full_name: str           # e.g. "Shivansh1146/hcl-project"
    repo_id: int                  # GitHub's numeric repo ID
    enabled: bool = True
    added_at: datetime


class Organization(BaseModel):
    """Represents a GitHub Organization or Personal Account container."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_org_id: int
    login: str
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    user_id: int
    created_at: datetime
    updated_at: datetime


class Repository(BaseModel):
    """Cached repository metadata for rich enterprise repo management."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_repo_id: int
    installation_id: int
    full_name: str
    name: str
    owner_login: str
    private: bool = False
    default_branch: str = "main"
    language: Optional[str] = None
    stargazers_count: int = 0
    archived: bool = False
    disabled: bool = False
    fork: bool = False
    open_pr_count: int = 0
    reviewed_pr_count: int = 0
    blocked_pr_count: int = 0
    last_reviewed_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.IDLE
    last_sync_error: Optional[str] = None
    enabled: bool = False
    created_at: datetime
    updated_at: datetime


class AuditLog(BaseModel):
    """Audit log entry for compliance and security tracking."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    user_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    severity: AuditSeverity = AuditSeverity.INFO
    details_json: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Request / Response Schemas (API surface)
# ---------------------------------------------------------------------------

class LoginURLResponse(BaseModel):
    """Response for GET /auth/login — contains the GitHub OAuth redirect URL."""
    authorization_url: str
    state: str


class CallbackRequest(BaseModel):
    """Query params received at GET /auth/callback from GitHub."""
    code: str
    state: str


class UserProfile(BaseModel):
    """Public-facing user profile for dashboard consumption."""
    github_id: int
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    organizations: List[str] = Field(default_factory=list)
    repositories_count: int = 0


class InstallationResponse(BaseModel):
    """API representation of a GitHub App installation."""
    installation_id: int
    account_login: str
    account_type: AccountType
    status: InstallationStatus
    repositories: List[RepoResponse] = Field(default_factory=list)


class RepoResponse(BaseModel):
    """API representation of an accessible repository."""
    repo_id: int
    full_name: str
    name: str = ""
    owner_login: str = ""
    private: bool = False
    default_branch: str = "main"
    language: Optional[str] = None
    stargazers_count: int = 0
    enabled: bool = False         # Whether selected for AI review


class SelectReposRequest(BaseModel):
    """Body for POST /api/app/installations/{installation_id}/repos/select."""
    repo_full_names: List[str] = Field(
        ...,
        min_length=1,
        description="List of full repo names to enable (e.g. ['owner/repo']).",
    )


class SelectReposResponse(BaseModel):
    """Confirmation after saving selected repositories."""
    installation_id: int
    enabled_repos: List[str]
    disabled_repos: List[str]


class WebhookInstallationPayload(BaseModel):
    """
    Subset of the GitHub App installation webhook payload we care about.
    GitHub sends this when a user installs / uninstalls the app.
    """
    action: str                   # "created" | "deleted" | "suspend" | "unsuspend"
    installation: InstallationInfo
    sender: SenderInfo


class InstallationInfo(BaseModel):
    id: int
    account: AccountInfo
    target_id: int
    target_type: str
    suspended_at: Optional[str] = None


class AccountInfo(BaseModel):
    login: str
    id: int
    type: str                     # "User" | "Organization"


class SenderInfo(BaseModel):
    login: str
    id: int


# Resolve forward reference for InstallationResponse
InstallationResponse.model_rebuild()
