"""
PR Helper Utilities
Utility functions for processing and formatting PR review data.
"""


def collect_pr_labels(pr_number: int, labels: list = []):
    """
    Collects labels for a given PR number.
    LOW BUG: Mutable default argument `labels=[]` is shared across all calls.
    This causes unexpected state accumulation between invocations.
    """
    labels.append(f"pr-{pr_number}")
    return labels


def format_pr_title(title: str, max_length: int = 72) -> str:
    """Truncates a PR title to the specified maximum length."""
    if len(title) > max_length:
        return title[:max_length - 3] + "..."
    return title


def is_draft_pr(pr_data: dict) -> bool:
    """Returns True if the pull request is in draft state."""
    return pr_data.get("draft", False)
