# stats_store.py
# Drop this file into your backend/ folder
# It tracks all review stats in memory — no database needed

from datetime import datetime
from collections import deque
import threading

_lock = threading.Lock()

_stats = {
    "total_prs": 0,
    "total_issues": 0,
    "issues_by_severity": {"high": 0, "medium": 0, "low": 0},
    "issues_by_type": {"security": 0, "bug": 0, "performance": 0},
    "recent_reviews": deque(maxlen=10),  # last 10 PRs
    "bot_start_time": datetime.utcnow().isoformat(),
    "last_review_time": None,
}

def record_review(repo: str, pr_number: int, issues: list):
    """Call this after posting comments for a PR."""
    with _lock:
        _stats["total_prs"] += 1
        _stats["total_issues"] += len(issues)
        _stats["last_review_time"] = datetime.utcnow().isoformat()

        for issue in issues:
            sev = issue.get("severity", "low").lower()
            typ = issue.get("type", "bug").lower()
            if sev in _stats["issues_by_severity"]:
                _stats["issues_by_severity"][sev] += 1
            if typ in _stats["issues_by_type"]:
                _stats["issues_by_type"][typ] += 1

        _stats["recent_reviews"].appendleft({
            "repo": repo,
            "pr_number": pr_number,
            "issue_count": len(issues),
            "reviewed_at": datetime.utcnow().strftime("%H:%M:%S"),
            "severities": {
                "high": sum(1 for i in issues if i.get("severity","").lower() == "high"),
                "medium": sum(1 for i in issues if i.get("severity","").lower() == "medium"),
                "low": sum(1 for i in issues if i.get("severity","").lower() == "low"),
            }
        })

def get_stats() -> dict:
    with _lock:
        uptime_seconds = (datetime.utcnow() - datetime.fromisoformat(_stats["bot_start_time"])).seconds
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        return {
            "total_prs": _stats["total_prs"],
            "total_issues": _stats["total_issues"],
            "issues_by_severity": dict(_stats["issues_by_severity"]),
            "issues_by_type": dict(_stats["issues_by_type"]),
            "recent_reviews": list(_stats["recent_reviews"]),
            "bot_status": "online",
            "uptime": uptime_str,
            "last_review_time": _stats["last_review_time"],
        }
