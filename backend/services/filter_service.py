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
    print("🔍 RAW AI RESULT:", analysis_result)

    if not analysis_result or "issues" not in analysis_result:
        print("❌ FILTER: No 'issues' key in AI result")
        return []

    vague_words = ["improve", "optimize", "better", "clean"]

    valid_issues = []
    for issue in analysis_result.get("issues", []):
        print(f"🔎 EVALUATING ISSUE: severity={issue.get('severity')}, desc_len={len(str(issue.get('description', '')))}")
        if issue.get("type") and issue.get("description") and issue.get("fix"):
            score = 0
            severity = str(issue.get("severity", "")).lower()
            description = str(issue.get("description", "")).lower()

            # Apply Scoring Logic
            if severity == "high":
                score += 2
            elif severity == "medium":
                score += 1

            if len(description) > 30:
                score += 1

            if any(word in description for word in vague_words):
                score -= 2

            print(f"   SCORE: {score} | severity={severity}")

            # Filter boundary — lowered to 0 to allow medium severity issues through
            if score >= 0:
                valid_issues.append(issue)
            else:
                print(f"   ❌ REJECTED: score={score} too low. desc={description[:40]}")
        else:
            print(f"   ❌ REJECTED: missing required fields (type/description/fix). Issue: {issue}")

    print(f"✅ FILTER PASSED: {len(valid_issues)} issues")
    return valid_issues
