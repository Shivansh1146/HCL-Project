import aiosqlite
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
        if not self.api_key:
            logger.error("GROQ_API_KEY not found in environment")
            self.client = None
        else:
            self.client = AsyncGroq(api_key=self.api_key)

    def _is_similar(self, issue1: Dict[str, Any], issue2: Dict[str, Any]) -> bool:
        """Normalizes descriptions and performs semantic similarity matching.
        Ensures issues on different lines/files are NEVER marked as duplicates."""
        
        # Exact line/file check prevents dropping valid identical bugs in different locations
        if issue1.get("file") != issue2.get("file") or issue1.get("line") != issue2.get("line"):
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
        return score > 0.6 # Stricter threshold

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
        system_prompt = """
You are a senior security-focused code reviewer. Act as a static analyzer, not a teacher.

Rules:
1. DO NOT report issues that are already mitigated.
   - Example: Parameterized SQL queries are SAFE -> do not flag SQL injection.

2. ONLY report real, exploitable issues. 
   - No hypothetical or generic advice.

3. Fix must:
   - Modify ONLY the affected line(s).
   - Keep original logic intact.
   - Be minimal and correct.
   - NEVER replace unrelated code.
   - Fix must look like a precise code patch, NOT a full rewrite.

4. If you are NOT 100% sure -> DO NOT report the issue.

5. NEVER give generic suggestions like:
   - "use ORM"
   - "improve performance"
   - "refactor code"

6. Output ONLY valid JSON in this format:
{
  "issues": [
    {
      "severity": "HIGH|MEDIUM|LOW",
      "type": "security|bug|performance|quality",
      "title": "Precise name",
      "description": "Exactly what is wrong",
      "line": 3,
      "file": "filename.py",
      "fix": "replacement code ONLY"
    }
  ]
}
"""

        user_prompt = f"Code Diff Chunk:\n{diff_chunk}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    timeout=15.0
                )

                content = response.choices[0].message.content.strip()
                parsed_json = json.loads(content)
                return parsed_json

            except Exception as e:
                error_str = str(e).lower()
                logger.error(f"[analyze_code] error on attempt {attempt + 1}: {error_str}")
                
                # Explicit Rate Limit Detection
                if "rate_limit_exceeded" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"⚠️ Rate limit hit. Backing off for {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return {"status": "error", "reason": "RATE_LIMIT", "issues": []}

                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return {"status": "error", "reason": "UNKNOWN_ERROR", "issues": []}

        return None

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
        """Lightweight static scan for critical security patterns (passwords, unsafe calls)."""
        # Multiline support: Normalize diff by merging lines to catch patterns split across lines
        normalized_diff = diff.replace("\n+", " ").replace("\n-", " ").replace("\n", " ")
        
        rules = [
            (r"(password|api_key|secret|token|private_key)\s*=\s*['\"].*?['\"]", "Hardcoded credential/secret", "HIGH", "security"),
            (r"verify=False", "SSL verification disabled", "MEDIUM", "security"),
            (r"eval\(", "Unsafe eval() usage", "HIGH", "security"),
            (r"os\.chmod\(.*0o777\)", "Insecure file permissions (777)", "HIGH", "security"),
        ]
        issues = []
        
        # 1. Scan normalized diff for multiline patterns
        for pattern, desc, sev, itype in rules:
            if re.search(pattern, normalized_diff, re.IGNORECASE):
                issues.append({
                    "severity": sev, "type": itype,
                    "title": "Rule-based Guard",
                    "description": f"Security risk detected: {desc}",
                    "fix": "Rotate secrets and use environment variables.",
                    "file": "Security Scan", "line": 0
                })
        
        return issues

    async def analyze_code(self, diff: str, progress_callback=None) -> Dict[str, Any]:
        """
        Analyzes a git diff using Groq AI.
        Splits diff into hunks, processes each hunk/chunk sequentially with a delay to respect rate limits.
        """
        if not diff:
            return {"status": "failed", "reason": "EMPTY_DIFF", "issues": [],
                    "total_chunks": 0, "processed_chunks": 0, "file_coverage": {}}

        if not self.client:
            return {"status": "failed", "reason": "CLIENT_NOT_INITIALIZED", "issues": [],
                    "total_chunks": 0, "processed_chunks": 0, "file_coverage": {}}

        all_chunks = self._get_hunk_aware_chunks(diff)
        
        total_chunks = len(all_chunks)
        chunks_to_process = all_chunks
        
        all_files = set(re.findall(r"^\+\+\+ b/(.*)$", diff, re.MULTILINE))
        file_chunks = {f: {"total": 0, "processed": 0} for f in all_files}
        for chunk in all_chunks:
            chunk_files = set(re.findall(r"^\+\+\+ b/(.*)$", chunk, re.MULTILINE))
            for f in chunk_files:
                file_chunks[f]["total"] += 1

        total_chunks = len(all_chunks)
        processed_chunks = 0
        rule_issues = self._rule_based_scan(diff)
        all_issues = list(rule_issues)
        seen_descriptions = list(rule_issues)
        reason = "SUCCESS"

        for chunk in chunks_to_process:
            chunk_files = set(re.findall(r"^\+\+\+ b/(.*)$", chunk, re.MULTILINE))
            result = await self._analyze_chunk_with_retry(chunk)
            await asyncio.sleep(2.0) # Sequential processing delay to avoid rate limits
            
            if result is None or (isinstance(result, dict) and result.get("status") == "error"):
                reason = result.get("reason", "CHUNK_ERROR") if isinstance(result, dict) else "CHUNK_ERROR"
                break

            processed_chunks += 1
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
