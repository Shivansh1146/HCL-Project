"""Application-wide constants for the AI Code Reviewer backend.

This module centralises all magic numbers, threshold values, and
configuration defaults used across the application. Keeping them
in one place makes auditing and tuning straightforward.
"""


# ---------------------------------------------------------------------------
# Decision Engine Thresholds
# ---------------------------------------------------------------------------

HIGH_SEVERITY_BLOCK_THRESHOLD = 1
"""Minimum number of high-severity issues that triggers a BLOCK decision."""

MEDIUM_SEVERITY_REVIEW_THRESHOLD = 3
"""Minimum number of medium-severity issues that triggers REVIEW_REQUIRED."""

COVERAGE_WARNING_PERCENT = 10
"""Coverage percentage below which a critical warning is shown."""


# ---------------------------------------------------------------------------
# API and Rate Limiting
# ---------------------------------------------------------------------------

MAX_CONCURRENT_ANALYSES = 5
"""Maximum number of parallel AI analysis tasks allowed."""

SHA_STALE_MINUTES = 60
"""Minutes after which a pending or failed SHA claim becomes stale."""

DB_RETRY_ATTEMPTS = 3
"""Number of times a failed database operation is retried."""

DB_RETRY_BASE_DELAY = 1
"""Base delay in seconds between database retry attempts."""


# ---------------------------------------------------------------------------
# Display and Formatting
# ---------------------------------------------------------------------------

MAX_FILE_COVERAGE_DISPLAY = 10
"""Maximum number of files shown in the coverage status report."""

DEFAULT_STATS_PAGE_SIZE = 15
"""Default number of recent reviews returned by the stats endpoint."""

DASHBOARD_TITLE = "AI Code Reviewer"
"""Title displayed on the dashboard header."""

DASHBOARD_SUBTITLE = "Intelligent Feedback Command Center"
"""Subtitle displayed beneath the dashboard title."""


# ---------------------------------------------------------------------------
# Severity and Category Labels
# ---------------------------------------------------------------------------

SEVERITY_LEVELS = ("high", "medium", "low")
"""Ordered tuple of recognised severity levels."""

ISSUE_CATEGORIES = ("security", "bug", "performance", "quality")
"""Ordered tuple of recognised issue type categories."""

DECISION_STATUSES = ("BLOCK", "REVIEW_REQUIRED", "SAFE", "PERFECT")
"""Ordered tuple of possible PR decision outcomes."""
