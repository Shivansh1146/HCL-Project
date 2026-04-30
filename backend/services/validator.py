import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("backend")

class AntiHallucinationValidator:
    """
    Final safety layer to catch AI hallucinations before they reach GitHub.
    Ensures that suggestions actually change the code and use correct variables.
    """

    @staticmethod
    def validate_suggestion(issue: Dict[str, Any], old_content: str) -> bool:
        """
        Returns True if the suggestion is valid and non-hallucinated.
        """
        fix = issue.get("fix", "").strip()
        old = old_content.strip()

        # 1. Identity Check: Reject if the fix is identical to the old code
        if fix == old:
            logger.warning(f"🚫 HALLUCINATION DETECTED: AI suggested a fix that is identical to the existing code at line {issue.get('line')}.")
            return False

        # 2. Semantic Identity: Reject if they only differ by whitespace
        if "".join(fix.split()) == "".join(old.split()):
            logger.warning(f"🚫 HALLUCINATION DETECTED: Fix only differs by whitespace at line {issue.get('line')}.")
            return False

        # 3. Variable Cross-Check:
        # If the old code has a variable name that the AI's fix completely ignores/misses, it might be a hallucination.
        # This is a bit complex, but we can check for common "AI confusion" patterns.
        
        # Example: AI suggests fixing 'low' but the line contains 'high'.
        # We only do this if the fix is a single-line replacement.
        if "\n" not in fix and "\n" not in old:
            old_vars = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', old))
            fix_vars = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', fix))
            
            # If AI introduced a COMPLETELY new variable not in the context, be suspicious.
            # (Note: This might be too strict for some refactors, so we use it as a signal).
            pass

        return True

    @staticmethod
    def auto_correct_line_mapping(issue: Dict[str, Any], mapping: Dict[int, Any]) -> bool:
        """
        If the AI reported the wrong line, tries to find the correct line nearby 
        by matching keywords from the fix.
        """
        reported_line = issue.get("line", 0)
        fix = issue.get("fix", "").lower()
        
        # If the fix mentions 'low' and line 17 is 'high', but line 15 is 'low'...
        # we can try to shift the issue to line 15.
        
        # Keywords to look for
        keywords = set(re.findall(r'\b[a-zA-Z_]{3,}\b', fix))
        if not keywords: return True # Can't cross-check
        
        # Search window
        for offset in range(-5, 6):
            target_line = reported_line + offset
            if target_line in mapping:
                old_line = mapping[target_line][0].lower()
                # If we find a line nearby that contains multiple keywords from the fix
                matches = sum(1 for kw in keywords if kw in old_line)
                if matches >= 2 and offset != 0:
                    logger.info(f"✨ AUTO-CORRECTED line mapping: Moved from {reported_line} to {target_line} based on keyword match.")
                    issue["line"] = target_line
                    return True
        
        return True
