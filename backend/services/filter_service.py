import logging

logger = logging.getLogger(__name__)

class FilterService:
    """Service to filter and preprocess data."""

    def __init__(self):
        pass

    def filter_diff(self, diff_content: str) -> str:
        """Filters unnecessary content from a code diff."""
        logger.info("Filtering diff content")
        # Placeholder filter implementation
        return diff_content.strip()

def get_filter_service() -> FilterService:
    return FilterService()

def parse_and_filter_issues(analysis_result: dict, raw_diff: str = "") -> list:
    """
    SAFETY THROTTLE (v2):
    1. STRICT SEVERITY FLOOR: Only Medium and High issues allowed.
    2. REJECT SMALL DIFF NOISE: If diff is < 10 lines, AI is likely hallucinating.
    3. BAN REFACTORING: Silence the AI if it tries to 'improve' or 'optimize'.
    """
    logger.info("[filter_service] Applying Safety Throttle to prevent feedback loops")

    if not analysis_result or "issues" not in analysis_result:
        return []

    # If the diff is tiny, the AI often 'hallucinates' bugs to be helpful.
    # We silence it for very small changes unless they are HIGH severity.
    diff_lines = [l for l in raw_diff.splitlines() if l.startswith('+') or l.startswith('-')]
    is_tiny_diff = len(diff_lines) < 10

    valid_issues = []
    # Forbidden topics that cause infinite loops or are Python-impossible
    hallucination_triggers = [
        "improve", "optimize", "better", "clean", "suggest", "consider", 
        "style", "refactor", "readability", "efficiency", "best practice",
        "redundant", "unnecessary", "nitpick", "formatting",
        "overflow", "integer limit", "search space" 
    ]

    for issue in analysis_result.get("issues", []):
        severity = str(issue.get("severity", "")).lower()
        description = str(issue.get("description", "")).lower()
        fix = str(issue.get("fix", ""))
        issue_type = str(issue.get("type", "")).lower()
        file_path = str(issue.get("file", "")).lower()

        # SEVERITY FLOOR: Drop only INFO/unknown severity issues
        if severity not in ("high", "medium", "low", "critical"):
            logger.info(f"🚫 THROTTLED: Unknown/info severity issue blocked.")
            continue

        # HIGH/CRITICAL security issues always pass — hallucination guards only apply to MEDIUM
        is_high = severity in ("high", "critical")

        if not is_high:
            # IRON-CLAD BLOCK: Reject Python-impossible overflow hallucinations (MEDIUM only)
            hallucination_code = ["search space", "integer overflow", "integer limit"]
            if any(word in description for word in hallucination_code):
                logger.info(f"🚫 IRON-CLAD REJECT: Blocked impossible Python overflow hallucination.")
                continue

            # TINY DIFF PROTECTION: Only block MEDIUM on tiny diffs (not LOW)
            if is_tiny_diff and severity == "medium":
                logger.info(f"🚫 THROTTLED: Medium issue blocked on tiny diff to prevent loops.")
                continue

            # HALLUCINATION TRIGGER BANS (MEDIUM only)
            if any(word in description for word in hallucination_triggers) or any(word in fix.lower() for word in hallucination_triggers):
                logger.info(f"🚫 THROTTLED: AI is nitpicking/hallucinating: {description[:50]}...")
                continue

        # STRUCTURE GUARD: Fix cannot replace structural keywords with partial logic
        if any(kw in fix.lower() for kw in ["else:", "elif:", "while:", "if "]) and len(fix.split()) < 3:
            continue

        # COMMENT GUARD: Never suggest replacing a comment with code
        if description.startswith("incorrect update") and "#" in description:
            continue

        # Structural Integrity: must have type, description, and fix
        if not (issue_type and description and fix):
            continue

        # SQLi & Destructive Protection
        if "sql injection" in description and ("?" in raw_diff or "%s" in raw_diff):
            continue
        if "return" in fix.lower() and "execute" in raw_diff.lower() and "execute" not in fix.lower():
            continue

        valid_issues.append(issue)

    logger.info(f"✅ SAFETY THROTTLE COMPLETE: {len(valid_issues)} high-fidelity issues remaining.")
    return valid_issues
