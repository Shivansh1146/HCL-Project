import asyncio
import logging
import os
import json
import re
import string
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from groq import AsyncGroq, GroqError

logger = logging.getLogger("backend")

class AIService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Groq client with validation."""
        if not self.api_key:
            logger.error("✗ GROQ_API_KEY missing - AI review service disabled")
            return
        
        if not self.api_key.strip():
            logger.error("✗ GROQ_API_KEY is empty - AI review service disabled")
            return
        
        if len(self.api_key) < 10:
            logger.error("✗ GROQ_API_KEY appears invalid (too short) - AI review service disabled")
            return
        
        try:
            self.client = AsyncGroq(api_key=self.api_key)
            logger.info(f"✓ GROQ_API_KEY loaded - Model: {self.model}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Groq client: {str(e)}")
            self.client = None

    def is_configured(self) -> bool:
        """Check if AI service is properly configured."""
        return self.client is not None and self.api_key is not None

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Groq API connectivity."""
        if not self.is_configured():
            return {
                "groq_configured": False,
                "groq_reachable": False,
                "model": self.model,
                "status": "error",
                "reason": "GROQ_API_KEY not configured or invalid"
            }
        
        try:
            # Simple test request to verify connectivity
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                timeout=5.0
            )
            return {
                "groq_configured": True,
                "groq_reachable": True,
                "model": self.model,
                "status": "ok"
            }
        except GroqError as e:
            logger.error(f"Groq health check failed: {str(e)}")
            return {
                "groq_configured": True,
                "groq_reachable": False,
                "model": self.model,
                "status": "error",
                "reason": str(e)
            }
        except Exception as e:
            logger.error(f"Groq health check error: {str(e)}")
            return {
                "groq_configured": True,
                "groq_reachable": False,
                "model": self.model,
                "status": "error",
                "reason": f"Unexpected error: {str(e)}"
            }

    def _is_similar(self, issue1: Dict[str, Any], issue2: Dict[str, Any]) -> bool:
        """
        Normalizes descriptions and performs semantic similarity matching.
        HARDENING: Allows deduplication on nearby lines (within 3 lines) if description matches.
        """
        # File must be the same
        if issue1.get("file") != issue2.get("file"):
            return False
            
        # Line distance check: If lines are > 3 apart, assume different issues
        try:
            line1 = int(issue1.get("line", 0))
            line2 = int(issue2.get("line", 0))
            if abs(line1 - line2) > 3:
                return False
        except (ValueError, TypeError):
            return False

        def normalize(t: str) -> str:
            t = t.lower()
            return t.translate(str.maketrans('', '', string.punctuation)).strip()

        norm1 = normalize(issue1.get("description", ""))
        norm2 = normalize(issue2.get("description", ""))

        if not norm1 or not norm2:
            return False
            
        # Hardening: If description is too short, avoid semantic dedup to prevent generic collisions
        if len(norm1) < 20 or len(norm2) < 20:
            return norm1 == norm2

        # Jaccard similarity for better deduplication
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        stop_words = {"is", "are", "the", "a", "an", "this", "that", "it", "to", "in", "on", "of", "for", "and", "or", "found", "should", "could", "be"}
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return norm1 == norm2

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        score = len(intersection) / len(union)
        
        # If lines are identical, threshold is 0.6. 
        # If lines are different (but nearby), threshold is 0.8 (higher bar for dedup)
        threshold = 0.6 if line1 == line2 else 0.8
        return score >= threshold

    def _is_structurally_valid(self, issue: Dict[str, Any]) -> bool:
        """Strict schema enforcement to prevent 'garbage' data from malformed AI blocks."""
        if not isinstance(issue, dict):
            return False
            
        required_keys = {"severity", "type", "title", "description", "fix"}
        for key in required_keys:
            val = issue.get(key)
            if not isinstance(val, str) or not val.strip():
                return False
            
        # Strict enum check
        if issue["severity"].upper() not in {"HIGH", "MEDIUM", "LOW"}:
            return False
            
        return True

    async def _analyze_chunk_with_retry(self, diff_chunk: str) -> Optional[Dict[str, Any]]:
        """Sends a single diff chunk to Groq with retry logic and JSON validation."""
        logger.info("📤 Sending prompt to Groq")
        
        if not self.is_configured():
            logger.error("❌ GROQ_API_KEY is invalid, expired, or quota exceeded")
            return {"status": "error", "reason": "API_KEY_INVALID", "issues": []}
        
        system_prompt = """
You are a strict, deterministic code reviewer.

Rules:
1. DO NOT report the same issue again if it was already fixed in previous commits.
2. DO NOT invent new issues after a correct fix.
3. Only report issues that currently exist in NEWLY ADDED lines (lines starting with '+').
4. If the code is already correct, return {"issues": []}.
5. You MUST report issues in all categories (security, bug, performance, quality) if they exist.
6. Use 'performance' for inefficient code and 'quality' for style, naming, or readability issues that impact maintainability.
7. DO NOT change logic unless it is clearly and provably incorrect.
8. Fix must be minimal and directly related to the issue.
9. If no real bug exists, output: {"issues": []}

IMPORTANT - This is a git diff:
- Lines starting with '+' are NEWLY ADDED. Analyze ONLY these.
- Lines starting with '-' are REMOVED. DO NOT analyze them.
- Lines with no prefix are CONTEXT. DO NOT analyze them.

- Minor stylistic or cosmetic changes.
- Readability suggestions that do not improve code quality or performance.
- Any issue where the fix is identical to the existing code.

Stability is more important than completeness. When in doubt, return {"issues": []}.

FIX FIELD RULES (strictly enforced by the backend — violations will be rejected):
- The "fix" field MUST contain valid source code, NOT prose or English explanations.
- The "fix" field MUST be genuinely different from the current source line being flagged.
- Do NOT copy the existing line unchanged into "fix".
- Do NOT reproduce the same code as the existing line — that is a no-op and will be rejected.
- The "fix" must actually remediate the reported issue (e.g. add validation, change the call, remove unsafe code).
- If no safe, concrete, code-level fix exists for the issue, set "fix" to "" and do NOT include a suggestion.
- Do NOT invent source code that is not present in the diff context.
- Preserve indentation and surrounding code structure.

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "HIGH|MEDIUM|LOW",
      "type": "security|bug|performance|quality",
      "title": "Precise name",
      "description": "Exactly what is wrong",
      "line": 3,
      "file": "filename.py",
      "fix": "replacement code ONLY — must differ from current line, or empty string if no safe fix"
    }
  ]
}

SEVERITY GUIDELINES:
- HIGH: Security vulnerabilities (injection, hardcoded secrets, unsafe permissions) or critical logic bugs that cause crashes.
- MEDIUM: Significant logic errors, potential bugs, or noticeable performance issues.
- LOW: Quality issues, style/PEP8 violations, naming convention issues, missing documentation, or minor optimizations.
"""

        user_prompt = f"Code Diff Chunk:\n{diff_chunk}"

        max_retries = 3
        base_delay = 2  # Base delay for exponential backoff
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Groq API attempt {attempt + 1}/{max_retries}")
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    timeout=30.0
                )

                content = response.choices[0].message.content.strip()
                parsed_json = json.loads(content)
                logger.info("✅ Groq response received")
                return parsed_json

            except GroqError as e:
                error_str = str(e).lower()
                logger.error(f"❌ Groq API error on attempt {attempt + 1}: {error_str}")
                
                # Explicit error handling for different Groq errors
                if "rate_limit_exceeded" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"⚠️ Rate limit hit. Backing off for {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("❌ Rate limit exceeded after all retries")
                        return {"status": "error", "reason": "RATE_LIMIT", "issues": []}
                
                elif "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                    logger.error("❌ GROQ_API_KEY is invalid or expired")
                    return {"status": "error", "reason": "AUTH_ERROR", "issues": []}
                
                elif "quota" in error_str or "credit" in error_str:
                    logger.error("❌ Groq API quota exceeded")
                    return {"status": "error", "reason": "QUOTA_EXCEEDED", "issues": []}
                
                elif "timeout" in error_str or "timed out" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        logger.warning(f"⚠️ Request timeout. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("❌ Request timeout after all retries")
                        return {"status": "error", "reason": "TIMEOUT", "issues": []}

            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse Groq response as JSON: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay)
                else:
                    return {"status": "error", "reason": "JSON_PARSE_ERROR", "issues": []}

            except Exception as e:
                error_str = str(e).lower()
                logger.error(f"❌ Unexpected error on attempt {attempt + 1}: {error_str}")
                
                # Check for HTTP 5xx errors (transient failures)
                if any(code in error_str for code in ["500", "502", "503", "504"]):
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        logger.warning(f"⚠️ Server error detected. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("❌ Server error after all retries")
                        return {"status": "error", "reason": "SERVER_ERROR", "issues": []}
                
                # Generic retry for other errors
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay)
                else:
                    logger.error(f"❌ Unknown error after all retries: {str(e)}")
                    return {"status": "error", "reason": "UNKNOWN_ERROR", "details": str(e), "issues": []}

        logger.error("❌ Failed to analyze chunk after all retries")
        return {"status": "error", "reason": "MAX_RETRIES_EXCEEDED", "issues": []}

    def _get_hunk_aware_chunks(self, diff: str, max_size: int = 1000) -> list:
        """Splits diff into chunks by hunk, preserving file context."""
        lines = diff.splitlines()
        chunks = []
        current_chunk = []
        current_file_header = ""
        current_size = 0

        for line in lines:
            if line.startswith("+++ b/"):
                current_file_header = line

            line_size = len(line) + 1
            if current_size + line_size > max_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [current_file_header, line] if current_file_header else [line]
                current_size = len(current_file_header) + line_size if current_file_header else line_size
            else:
                current_chunk.append(line)
                current_size += line_size

        if current_chunk:
            chunks.append("\n".join(current_chunk))
        return chunks

    def _rule_based_scan(self, diff: str) -> List[Dict[str, Any]]:
        """Lightweight static scan for critical security patterns with exact file+line extraction."""
        rules = [
            (
                r"\beval\(",
                "Unsafe eval() — Remote Code Execution (RCE) vulnerability. eval() executes arbitrary user-supplied code, allowing attackers to run any system command.",
                "HIGH", "security",
                "# SAFE: Use ast.literal_eval() for safe parsing, or json.loads() for JSON data\nresult = ast.literal_eval(user_input)"
            ),
            (
                r"(password|api_key|secret|token|private_key)\s*=\s*['\"](?!\$|os\.|getenv|environ).{4,}['\"]",
                "Hardcoded credential/secret detected. Secrets in source code are exposed in version control and logs.",
                "HIGH", "security",
                "# SAFE: Load from environment variable instead\nvalue = os.getenv('YOUR_SECRET_KEY')"
            ),
            (
                r"verify=False",
                "SSL certificate verification disabled. This enables man-in-the-middle attacks on HTTPS connections.",
                "HIGH", "security",
                "# SAFE: Always verify SSL certificates\nrequests.get(url, verify=True)"
            ),
            (
                r"os\.chmod\(.*0o777\)",
                "Insecure file permissions (0o777) — world-writable files allow any user to modify them.",
                "HIGH", "security",
                "# SAFE: Use restrictive permissions\nos.chmod(path, 0o644)"
            ),
        ]
        issues = []
        current_file = "unknown"
        current_line = 0
        diff_line_counter = 0

        lines = diff.splitlines()
        for line in lines:
            # Track current file from diff header
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                diff_line_counter = 0
                continue
            # Track line numbers from hunk headers e.g. @@ -1,3 +5,10 @@
            hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk_match:
                diff_line_counter = int(hunk_match.group(1)) - 1
                continue
            # Count added lines
            if line.startswith("+") and not line.startswith("+++"):
                diff_line_counter += 1
                code_line = line[1:]  # Strip leading '+'
                for pattern, desc, sev, itype, fix in rules:
                    if re.search(pattern, code_line, re.IGNORECASE):
                        # Avoid duplicate detections on the same file:line
                        already_found = any(
                            i["file"] == current_file and i["line"] == diff_line_counter
                            for i in issues
                        )
                        if not already_found:
                            issues.append({
                                "severity": sev,
                                "type": itype,
                                "title": f"[Security] {pattern[:30].strip()}",
                                "description": desc,
                                "fix": fix,
                                "file": current_file,
                                "line": diff_line_counter
                            })
            elif not line.startswith("-"):
                diff_line_counter += 1

        return issues

    async def analyze_code(self, diff: str, progress_callback=None) -> Dict[str, Any]:
        """
        Analyzes a git diff using Groq AI.
        Splits diff into hunks, processes each hunk/chunk sequentially with a delay to respect rate limits.
        """
        logger.info("🚀 Starting AI code analysis")
        
        if not diff:
            logger.warning("⚠️ Empty diff provided, skipping analysis")
            return {"status": "failed", "reason": "EMPTY_DIFF", "issues": [],
                    "total_chunks": 0, "processed_chunks": 0, "file_coverage": {}}

        if not self.is_configured():
            logger.error("❌ AI service not configured - GROQ_API_KEY missing or invalid")
            return {"status": "failed", "reason": "CLIENT_NOT_INITIALIZED", "issues": [],
                    "total_chunks": 0, "processed_chunks": 0, "file_coverage": {}}

        all_chunks = self._get_hunk_aware_chunks(diff)
        
        total_chunks = len(all_chunks)
        chunks_to_process = all_chunks
        
        logger.info(f"📊 Analysis plan: {total_chunks} chunks to process")
        
        all_files = set(re.findall(r"^\+\+\+ b/(.*)$", diff, re.MULTILINE))
        file_chunks = {f: {"total": 0, "processed": 0} for f in all_files}
        for chunk in all_chunks:
            chunk_files = set(re.findall(r"^\+\+\+ b/(.*)$", chunk, re.MULTILINE))
            for f in chunk_files:
                file_chunks[f]["total"] += 1

        total_chunks = len(all_chunks)
        processed_chunks = 0
        
        logger.info("🔍 Running rule-based security scan")
        rule_issues = self._rule_based_scan(diff)
        logger.info(f"✅ Rule-based scan found {len(rule_issues)} security issues")
        
        all_issues = list(rule_issues)
        seen_descriptions = list(rule_issues)
        reason = "SUCCESS"

        for chunk_index, chunk in enumerate(chunks_to_process):
            chunk_files = set(re.findall(r"^\+\+\+ b/(.*)$", chunk, re.MULTILINE))
            logger.info(f"🔄 Processing chunk {chunk_index + 1}/{total_chunks}")
            
            result = await self._analyze_chunk_with_retry(chunk)
            await asyncio.sleep(2.0) # Sequential processing delay to avoid rate limits
            
            if result is None or (isinstance(result, dict) and result.get("status") == "error"):
                reason = result.get("reason", "CHUNK_ERROR") if isinstance(result, dict) else "CHUNK_ERROR"
                logger.error(f"❌ Chunk processing failed: {reason}")
                break

            processed_chunks += 1
            logger.info(f"✅ Processed {processed_chunks}/{total_chunks} chunks")
            
            if progress_callback:
                await progress_callback(processed_chunks, total_chunks)

            # Mark files in this chunk as partially processed
            for f in chunk_files:
                file_chunks[f]["processed"] += 1

            chunk_issues = result.get("issues", [])
            if isinstance(chunk_issues, list):
                for issue in chunk_issues:
                    if not self._is_structurally_valid(issue): continue
                    desc = issue.get("description", "").strip()
                    fix = issue.get("fix", "").strip()
                    if not desc or len(desc) < 10 or not fix or "no fix needed" in fix.lower(): continue
                    
                    if not any(self._is_similar(issue, seen) for seen in seen_descriptions):
                        seen_descriptions.append(issue)
                        all_issues.append(issue)



        # Calculate final file-level coverage status
        file_coverage = {}
        for f, stats in file_chunks.items():
            if stats["total"] > 0 and stats["processed"] == stats["total"]:
                file_coverage[f] = "FULLY_ANALYZED"
            elif stats["processed"] > 0:
                file_coverage[f] = "PARTIAL"
            else:
                file_coverage[f] = "SKIPPED"

        # Confidence Kill Switch: Never trust silence on large diffs
        decision_status = "SAFE"
        if not all_issues and len(diff) > 3000:
            decision_status = "REVIEW_REQUIRED"
            logger.warning(f"⚠️ Confidence Kill Switch Triggered: Large diff ({len(diff)} chars) with 0 issues. Forcing REVIEW_REQUIRED.")

        logger.info(f"🏁 AI analysis complete: {len(all_issues)} issues found, decision={decision_status}")
        
        return {
            "status": "success" if processed_chunks == total_chunks else "partial",
            "reason": reason,
            "issues": all_issues,
            "decision_status": decision_status,
            "rule_based_count": len(rule_issues),
            "total_chunks": total_chunks,
            "processed_chunks": processed_chunks,
            "file_coverage": file_coverage
        }

def get_ai_service() -> AIService:
    return AIService()
