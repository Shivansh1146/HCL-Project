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

def parse_and_filter_issues(analysis_result: dict) -> list:
    """Extracts and filters valid issues from AI analysis using a strict scoring system."""
    logger.info("[filter_service] Filtering issues")

    if not analysis_result or "issues" not in analysis_result:
        return []

    vague_words = ["improve", "optimize", "better", "clean", "suggest", "consider", "style"]
    valid_issues = []

    for issue in analysis_result.get("issues", []):
        severity = str(issue.get("severity", "")).lower()
        description = str(issue.get("description", "")).lower()
        fix = str(issue.get("fix", "")).lower()

        # Rule 1: Fields must be present and non-empty
        if not (description and fix):
            continue

        # Rule 2: Contradiction Check - No "no fix needed" or empty fixes
        if "no fix needed" in fix or "no issues" in description:
            continue

        score = 0
        # Rule 3: Severity-based baseline
        if severity == "high":
            score += 2
        elif severity == "medium":
            score += 1
        elif severity == "low":
            score += 0.5 # Low severity needs more signals to pass

        # Rule 4: Descriptive Signal
        if len(description) > 40:
            score += 1

        # Rule 5: Vague word penalty (Stricter)
        if any(word in description for word in vague_words):
            score -= 1.5

        # Rule 6: Fix Signal - Ensure fix isn't just a comment
        if fix.strip().startswith("#") and len(fix.splitlines()) == 1:
            score -= 1

        # Final Threshold: Must be > 0
        if score > 0:
            valid_issues.append(issue)
        else:
            logger.info(f"[filter_service] REJECTED (score {score}): {description[:50]}...")

    logger.info(f"✅ FILTER PASSED: {len(valid_issues)} issues")
    return valid_issues
