import os
import json
import asyncio
import string
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv
from groq import AsyncGroq, GroqError

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger("backend")

class AIService:
    """Service to handle AI interactions using Groq (free tier)."""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("Groq API key is not set. Set GROQ_API_KEY in .env")
            self.client = None
        else:
            self.client = AsyncGroq(api_key=self.api_key)

    def _is_similar(self, desc1: str, desc2: str) -> bool:
        """Normalizes descriptions and performs semantic similarity matching."""
        def normalize(t: str) -> str:
            t = t.lower()
            return t.translate(str.maketrans('', '', string.punctuation)).strip()

        norm1 = normalize(desc1)
        norm2 = normalize(desc2)

        if not norm1 or not norm2:
            return False

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

    async def _analyze_chunk_with_retry(self, diff_chunk: str) -> Dict[str, Any]:
        """Calls Groq with JSON mode and system prompt."""
        system_prompt = """You are a Senior Production-Grade Security Engineer.
Analyze code diffs for REAL issues. Return a RAW JSON object with NO external text.

STRICT SEVERITY CALIBRATION:
- HIGH: RCE, SQLi, Hardcoded Secrets/Auth Bypass, Severe Data Leakage.
- MEDIUM: Logic flaws, XSS, unsafe resource handling, broken state machines.
- LOW: Quality, style, efficiency, minor best practice violations.

ENGINEERING-FIRST REMEDIATION:
- Provide high-engineering fixes: restrict access, sanitize input, isolate logic, or use secure libraries.
- DO NOT suggest "deleting the endpoint" unless the entire feature is inherently unsafe.
- Be precise and technical. Avoid dramatic language like "system may be completely compromised."

JSON STRUCTURE:
{
"issues": [
  {
    "severity": "HIGH|MEDIUM|LOW",
    "type": "security|bug|performance|quality",
    "title": "Precise name",
    "description": "Exactly what is wrong",
    "impact": "Realistic technical consequence",
    "fix": "RAW code snippet or specific technical instruction"
  }
]
}

STRICT CONSTRAINTS:
- No preamble like "Here is the JSON...". Return ONLY the JSON object.
- If unsure, return {"issues": []}.
- The 'fix' field must be valid code or highly specific technical remediation.
"""

        user_prompt = f"Code Diff Chunk:\n{diff_chunk}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    timeout=15.0
                )

                content = response.choices[0].message.content.strip()
                logger.info(f"[DEBUG] Raw AI Content: {content[:500]}...")
                parsed_json = json.loads(content)
                logger.info(f"[analyze_code] success on attempt {attempt + 1}")
                return parsed_json

            except (json.JSONDecodeError, GroqError, Exception) as e:
                logger.error(f"[analyze_code] error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)

        logger.error("[analyze_code] Failed after retries")
        return None  # Return None to signal total failure

    def _get_hunk_aware_chunks(self, diff: str, max_size: int = 4000) -> list:
        """Splits diff into chunks by hunk, preserving file context."""
        lines = diff.splitlines()
        chunks = []
        current_chunk = []
        current_file_header = ""
        current_size = 0

        for line in lines:
            # Capture file header
            if line.startswith("+++ b/"):
                current_file_header = line

            line_size = len(line) + 1
            if current_size + line_size > max_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                # Start new chunk with the same file header for context
                current_chunk = [current_file_header] if current_file_header else []
                current_size = len(current_file_header) + 1 if current_file_header else 0

            current_chunk.append(line)
            current_size += line_size

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    async def analyze_code(self, diff: str) -> Dict[str, Any]:
        """Analyzes code diff content using AI, handling large diff chunking."""
        if not diff:
            return {"status": "failed", "reason": "EMPTY_DIFF", "issues": []}

        if not self.client:
            return {"status": "failed", "reason": "CLIENT_NOT_INITIALIZED", "issues": []}

        chunks = self._get_hunk_aware_chunks(diff)
        all_issues = []
        seen_descriptions = []

        for chunk in chunks:
            result = await self._analyze_chunk_with_retry(chunk)
            if result is None:
                # STRICT RELIABILITY: Any chunk failure = Total analysis failure
                return {"status": "failed", "reason": "CHUNK_PROCESSING_ERROR", "issues": []}

            issues = result.get("issues", [])

            # If we got a result (even empty issues), it's a success for this chunk
            if isinstance(issues, list):
                any_success = True
            else:
                continue

            for issue in issues:
                desc = issue.get("description", "").strip()
                fix = issue.get("fix", "").strip()

                # Basic validation: must have desc and fix, and fix shouldn't be "no fix needed"
                if not desc or not fix or "no fix needed" in fix.lower():
                    continue

                is_duplicate = False
                for seen_desc in seen_descriptions:
                    if self._is_similar(desc, seen_desc):
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_descriptions.append(desc)
                    all_issues.append(issue)

        return {"status": "success", "issues": all_issues}

def get_ai_service() -> AIService:
    return AIService()

_ai_service_instance = AIService()

async def analyze_code(diff: str) -> Dict[str, Any]:
    return await _ai_service_instance.analyze_code(diff)
