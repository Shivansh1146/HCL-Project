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
    STRICT 3-LAYER FILTERING:
    1. Reject generic/style advice.
    2. Reject false-positive SQLi (parameterized queries).
    3. Reject destructive/unrelated fixes.
    """
    logger.info("[filter_service] Executing strict post-AI validation")

    if not analysis_result or "issues" not in analysis_result:
        return []

    valid_issues = []
    vague_words = ["improve", "optimize", "better", "clean", "suggest", "consider", "style", "refactor"]

    for issue in analysis_result.get("issues", []):
        severity = str(issue.get("severity", "")).lower()
        description = str(issue.get("description", "")).lower()
        fix = str(issue.get("fix", ""))
        
        # 1. Structural Check
        if not (issue.get("type") and description and fix):
            continue

        # 2. SQL Injection False Positive Protection
        # ❌ Reject SQLi if the diff contains parameterized query indicators (?, %s)
        if "sql injection" in description and ("?" in raw_diff or "%s" in raw_diff):
            logger.info(f"🚫 REJECTED: False positive SQLi on parameterized query.")
            continue

        # 3. Destructive Fix Protection
        # ❌ Reject if the fix seems to delete logic (e.g., returns early or replaces execute with nothing)
        if "return" in fix.lower() and "execute" in raw_diff.lower() and "execute" not in fix.lower():
             logger.info(f"🚫 REJECTED: Destructive fix detected (replaces execution with return).")
             continue

        # 4. Generic Advice Filter
        # ❌ Reject if fix is just text or too long/generic
        if len(fix.split()) > 50 or any(word in description for word in vague_words):
            logger.info(f"🚫 REJECTED: Generic or non-actionable advice.")
            continue

        # 5. Content Contradiction
        if "no fix needed" in fix.lower() or "already mitigated" in description:
            continue

        # Success: Passed all strict layers
        valid_issues.append(issue)

    logger.info(f"✅ STRICT FILTER COMPLETE: {len(valid_issues)} high-fidelity issues remaining.")
    return valid_issues
