import logging
import re
from typing import Dict, Set, Tuple, Optional, Any

logger = logging.getLogger("backend")


class DiffValidator:
    """Parses unified diffs to validate AI-suggested line mappings and generate GitHub suggestions."""

    @staticmethod
    def parse_diff_mapping(diff_text: str) -> Dict[str, Dict[int, Tuple[str, str]]]:
        """
        Parses unified diff and returns detailed mapping:
        {
            "file.py": {
                line_num: (old_content, new_content)
            }
        }
        """
        mapping = {}
        if not diff_text:
            return mapping

        current_file = None
        lines = diff_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect file header
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                mapping[current_file] = {}
                i += 1
                continue

            # Detect hunk header: @@ -start,len +start,len @@
            hunk_match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk_match and current_file:
                new_line_num = int(hunk_match.group(2))
                i += 1

                # Use a buffer to handle changed lines (old followed by new)
                old_buffer = []
                while i < len(lines) and not lines[i].startswith(("diff --git", "+++", "---", "@@")):
                    current = lines[i]
                    if current.startswith("+"):
                        new_content = current[1:]
                        # Try to pair with an old line if one is buffered
                        old_content = old_buffer.pop(0) if old_buffer else ""
                        mapping[current_file][new_line_num] = (old_content, new_content)
                        new_line_num += 1
                    elif current.startswith("-"):
                        old_buffer.append(current[1:])
                    else:
                        # Context line
                        old_buffer = [] # Clear buffer on context
                        mapping[current_file][new_line_num] = (current, current)
                        new_line_num += 1
                    i += 1
                continue
            i += 1

        return mapping

    @staticmethod
    def validate_issue(issue: Dict[str, Any], mapping: Dict[str, Dict[int, Tuple[str, str]]]) -> bool:
        """Checks if the issue's file and line exist in the diff mapping."""
        file_path = issue.get("file")
        try:
            line_num = int(issue.get("line", -1))
        except (ValueError, TypeError):
            return False

        if not file_path:
            return False

        # Flexible file matching
        matched_key = DiffValidator._find_matching_file(file_path, mapping)
        if not matched_key:
            logger.warning(f"[DiffValidator] File not in diff: {file_path}")
            return False

        # Check if line exists in mapping
        if line_num in mapping[matched_key]:
            return True

        # Lenient line matching with tolerance
        valid_lines = sorted(mapping[matched_key].keys())
        for valid_line in valid_lines:
            if abs(valid_line - line_num) <= 5:
                # If the line was added or modified (diff contents not the same)
                old, new = mapping[matched_key][valid_line]
                if old != new:
                    logger.info(f"[DiffValidator] Adjusted line from {line_num} to {valid_line}")
                    issue["line"] = valid_line
                    return True

        logger.warning(f"[DiffValidator] Line {line_num} not found/unmodified for {file_path}")
        return False

    @staticmethod
    def generate_suggestion(issue: Dict[str, Any], mapping: Dict[str, Dict[int, Tuple[str, str]]]) -> Optional[str]:
        """
        Generates GitHub suggestion format for an issue.
        """
        file_path = issue.get("file")
        line_num = issue.get("line")
        fix_code = issue.get("fix", "")

        matched_key = DiffValidator._find_matching_file(file_path, mapping)
        if not matched_key or line_num not in mapping[matched_key]:
            return None

        old_content, new_content = mapping[matched_key][line_num]

        # Use AI's fix if provided and looks valid, otherwise use diff content
        if fix_code and len(fix_code.strip()) > 2:
            suggestion_code = DiffValidator._clean_code(fix_code)
        elif new_content and new_content != old_content:
            suggestion_code = new_content
        else:
            return None

        if not suggestion_code or len(suggestion_code.strip()) < 1:
            return None

        return f"```suggestion\n{suggestion_code}\n```"

    @staticmethod
    def _find_matching_file(file_path: str, mapping: Dict[str, Any]) -> Optional[str]:
        if not file_path: return None
        if file_path in mapping: return file_path
        for key in mapping:
            if key.endswith(file_path) or file_path.endswith(key) or file_path in key or key in file_path:
                return key
        return None

    @staticmethod
    def _clean_code(code: str) -> str:
        if not code: return ""
        # Aggressively scrub common AI preamble
        code = re.sub(r'^(?:Fix|Suggested fix|Code|Suggestion|Use|Try|Here is the fix|Correct code):\s*', '', code, flags=re.IGNORECASE | re.MULTILINE)

        # Scrub line number prefixes like "5 - " or "5 + " or "5 | "
        code = re.sub(r'^\s*\d+\s*[-+|]\s*', '', code, flags=re.MULTILINE)

        # Scrub markdown code blocks
        code = re.sub(r'^```\w*\s*\n?', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n?```\s*$', '', code)

        code = code.strip()

        # If it still looks like natural language (starts with "Use "), it's probably not a good fix
        if code.lower().startswith("use ") and len(code.split()) > 5:
            return "" # Don't suggest text as code

        lines = code.splitlines()
        if len(lines) > 1:
            min_indent = float('inf')
            for line in lines:
                if line.strip():
                    min_indent = min(min_indent, len(line) - len(line.lstrip()))
            if min_indent != float('inf') and min_indent > 0:
                lines = [line[min_indent:] if len(line) > min_indent else line for line in lines]
                code = '\n'.join(lines)
        return code
