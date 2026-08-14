"""
tests/test_suggestion_validation.py

Tests for the suggestion-generation and validation layer.

Tests that the invariant `old_code != new_code` (GitHub-visible) is enforced by
both DiffValidator.generate_suggestion and review_publisher._build_inline_comments.

These tests do NOT require DATABASE_URL or a live Groq API key.
"""
import pytest
from services.diff_validator import DiffValidator
from services.review_publisher import _build_inline_comments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mapping(file_path: str, line: int, old_content: str, new_content: str) -> dict:
    """Build a minimal diff mapping for one file/line pair."""
    return {file_path: {line: (old_content, new_content)}}


def _make_issue(file: str, line: int, fix: str, severity: str = "HIGH") -> dict:
    return {
        "file": file,
        "line": line,
        "fix": fix,
        "severity": severity,
        "type": "security",
        "title": "Test issue",
        "description": "Test description",
    }


# ---------------------------------------------------------------------------
# TEST 1 — old_code == new_code (no-op suggestion)
# The AI returned the same code as the existing line.
# generate_suggestion MUST return None.
# ---------------------------------------------------------------------------
def test_identical_fix_and_new_content_is_rejected():
    existing_line = "subprocess.run(user_input.split(), capture_output=True, text=True, check=True)"
    mapping = _make_mapping("demo.py", 5, "", existing_line)  # pure addition
    issue = _make_issue("demo.py", 5, fix=existing_line)

    result = DiffValidator.generate_suggestion(issue, mapping)
    assert result is None, (
        "generate_suggestion must return None when fix == current source line"
    )


# ---------------------------------------------------------------------------
# TEST 2 — fix is genuinely different
# generate_suggestion MUST return a non-None suggestion string.
# ---------------------------------------------------------------------------
def test_genuine_fix_is_accepted():
    existing_line = "    subprocess.run(user_input.split(), capture_output=True, text=True)"
    fixed_line = "    # SAFE: validate input before execution\n    subprocess.run(['git', 'status'], capture_output=True, text=True)"
    mapping = _make_mapping("demo.py", 3, "", existing_line)
    issue = _make_issue("demo.py", 3, fix=fixed_line)

    result = DiffValidator.generate_suggestion(issue, mapping)
    assert result is not None, "generate_suggestion must return a suggestion when fix != source line"
    assert "```suggestion" in result
    assert "git" in result


# ---------------------------------------------------------------------------
# TEST 3 — old_code not found in diff (wrong file/line)
# generate_suggestion MUST return None.
# ---------------------------------------------------------------------------
def test_file_not_in_diff_is_rejected():
    mapping = _make_mapping("other_file.py", 10, "", "some_code()")
    issue = _make_issue("missing_file.py", 10, fix="safe_code()")

    result = DiffValidator.generate_suggestion(issue, mapping)
    assert result is None, "generate_suggestion must return None when file is not in diff"


# ---------------------------------------------------------------------------
# TEST 4 — new_code is empty (AI returned blank fix)
# generate_suggestion MUST return None.
# ---------------------------------------------------------------------------
def test_empty_fix_is_rejected():
    existing_line = "os.system(cmd)"
    mapping = _make_mapping("script.py", 7, "", existing_line)
    issue = _make_issue("script.py", 7, fix="")

    result = DiffValidator.generate_suggestion(issue, mapping)
    assert result is None, "generate_suggestion must return None when fix is empty"


# ---------------------------------------------------------------------------
# TEST 5 — old_code is empty (pure addition, valid fix)
# Should behave the same as TEST 2 — valid fix passes.
# ---------------------------------------------------------------------------
def test_pure_addition_with_valid_fix_is_accepted():
    existing_line = "    eval(user_input)"
    safe_fix = "    result = ast.literal_eval(user_input)"
    mapping = _make_mapping("app.py", 12, "", existing_line)  # old == ""
    issue = _make_issue("app.py", 12, fix=safe_fix)

    result = DiffValidator.generate_suggestion(issue, mapping)
    assert result is not None, "generate_suggestion must accept valid fix for a pure addition"
    assert "ast.literal_eval" in result


# ---------------------------------------------------------------------------
# TEST 6 — AI returns malformed/prose fix (natural language)
# generate_suggestion MUST return None; textual issue should remain.
# ---------------------------------------------------------------------------
def test_prose_fix_is_rejected():
    existing_line = "    os.chmod(path, 0o777)"
    prose_fix = "Use more restrictive permissions like 0o644 instead of 0o777"
    mapping = _make_mapping("util.py", 2, "", existing_line)
    issue = _make_issue("util.py", 2, fix=prose_fix)

    result = DiffValidator.generate_suggestion(issue, mapping)
    assert result is None, (
        "generate_suggestion must return None for prose/natural-language fix"
    )


# ---------------------------------------------------------------------------
# TEST 7 — Multiple issues; each gets its own independent suggestion
# ---------------------------------------------------------------------------
def test_multiple_issues_each_validated_independently():
    mapping = {
        "app.py": {
            5: ("", "    eval(data)"),
            10: ("", "    os.chmod(f, 0o777)"),
        }
    }

    issue_a = _make_issue("app.py", 5, fix="    result = ast.literal_eval(data)")
    issue_b = _make_issue("app.py", 10, fix="    os.chmod(f, 0o644)")

    result_a = DiffValidator.generate_suggestion(issue_a, mapping)
    result_b = DiffValidator.generate_suggestion(issue_b, mapping)

    assert result_a is not None, "Valid fix for issue A must be accepted"
    assert result_b is not None, "Valid fix for issue B must be accepted"
    assert "ast.literal_eval" in result_a
    assert "0o644" in result_b


# ---------------------------------------------------------------------------
# TEST 8 — Issue has no safe concrete fix (empty fix field)
# Textual review must be posted; no suggestion block emitted.
# _build_inline_comments must NOT emit a suggestion block.
# ---------------------------------------------------------------------------
def test_no_safe_fix_produces_textual_comment_only():
    issue = _make_issue("risky.py", 3, fix="")
    issue["description"] = "This pattern requires manual remediation."

    comments = _build_inline_comments([issue], commit_sha="abc123")
    assert len(comments) == 1
    assert "```suggestion" not in comments[0]["body"]
    assert "manual review required" in comments[0]["body"]


# ---------------------------------------------------------------------------
# TEST 9 — Valid security issue produces a real suggestion
# _build_inline_comments must emit a ```suggestion block when fix is valid.
# _validated_suggestion is pre-set to simulate the main.py pipeline.
# ---------------------------------------------------------------------------
def test_valid_security_fix_produces_suggestion_block():
    issue = _make_issue("app.py", 5, fix="    result = ast.literal_eval(data)")
    issue["_validated_suggestion"] = "```suggestion\n    result = ast.literal_eval(data)\n```"
    issue["_old_content"] = ""
    issue["_new_content"] = "    eval(data)"

    comments = _build_inline_comments([issue], commit_sha="abc123")
    assert len(comments) == 1
    assert "```suggestion" in comments[0]["body"]
    assert "ast.literal_eval" in comments[0]["body"]


# ---------------------------------------------------------------------------
# TEST 10 — fix == new_content via _build_inline_comments fallback path
# When _validated_suggestion is absent and fix == _new_content, must be rejected.
# ---------------------------------------------------------------------------
def test_build_inline_comments_rejects_noop_fix():
    existing_line = "subprocess.run(user_input.split(), capture_output=True, text=True)"
    issue = _make_issue("demo.py", 5, fix=existing_line)
    issue["_new_content"] = existing_line  # same as fix → no-op

    comments = _build_inline_comments([issue], commit_sha="abc123")
    assert len(comments) == 1
    assert "```suggestion" not in comments[0]["body"], (
        "_build_inline_comments must NOT emit a suggestion when fix == new_content"
    )
    assert "manual review required" in comments[0]["body"]
