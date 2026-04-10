import logging
import re

logger = logging.getLogger("backend")


class DiffValidator:
    """Parses unified diffs to validate AI-suggested line mappings."""

    @staticmethod
    def parse_diff_mapping(diff_text: str) -> dict:
        """
        Parses a unified diff and returns a mapping of {file_path: set(added_line_numbers)}.
        This is used to verify that AI isn't hallucinating line numbers.
        """
        mapping = {}
        current_file = None
        current_line_in_file = 0

        lines = diff_text.splitlines()
        for line in lines:
            # Detect file header
            if line.startswith("+++ b/"):
                current_file = line[6:]
                mapping[current_file] = set()
                continue

            # Detect hunk header: @@ -start,len +start,len @@
            hunk_match = re.match(r"^@@ -\d+,\d+ \+(\d+),\d+ @@", line)
            if hunk_match:
                current_line_in_file = int(hunk_match.group(1))
                continue

            if current_file:
                if line.startswith("+"):
                    mapping[current_file].add(current_line_in_file)
                    current_line_in_file += 1
                elif line.startswith("-"):
                    continue
                else:
                    current_line_in_file += 1

        return mapping

    @staticmethod
    def validate_issue(issue: dict, mapping: dict) -> bool:
        """Checks if the issue's file and line exist in the diff mapping."""
        file_path = issue.get("file")
        try:
            line_num = int(issue.get("line", -1))
        except (ValueError, TypeError):
            return False

        if not file_path:
            return False

        # Flexible file matching — handles path prefix mismatches
        matched_key = None
        for key in mapping:
            if key.endswith(file_path) or file_path.endswith(key) or file_path in key:
                matched_key = key
                break

        if not matched_key:
            logger.warning(f"[DiffValidator] File not in diff: {file_path}")
            return False

        # Lenient line matching — allow ±5 lines tolerance
        valid_lines = mapping[matched_key]
        for valid_line in valid_lines:
            if abs(valid_line - line_num) <= 5:
                return True

        logger.warning(
            f"[DiffValidator] Line {line_num} not in added lines for {file_path}"
        )
        return False
