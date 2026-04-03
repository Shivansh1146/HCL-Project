import os
import json
import time
import string
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from groq import Groq, GroqError

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger(__name__)

class AIService:
    """Service to handle AI interactions using Groq (free tier)."""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("Groq API key is not set. Set GROQ_API_KEY in .env")
            self.client = None
        else:
            self.client = Groq(api_key=self.api_key)

    def _is_similar(self, desc1: str, desc2: str) -> bool:
        """Normalizes descriptions and performs similarity matching."""
        def normalize(t: str) -> str:
            t = t.lower()
            return t.translate(str.maketrans('', '', string.punctuation)).strip()

        norm1 = normalize(desc1)
        norm2 = normalize(desc2)

        if not norm1 or not norm2:
            return False

        # Simple contains match
        if norm1 in norm2 or norm2 in norm1:
            return True

        # Word overlap match for inverted syntax cases
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        stop_words = {"is", "are", "the", "a", "an", "this", "that", "it", "to", "in", "on", "of", "for", "and", "or", "found"}
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        # If they share at least 2 significant keyword roots, treat as same
        if len(intersection) >= 2:
            return True

        return False

    def _analyze_chunk_with_retry(self, diff_chunk: str) -> Dict[str, Any]:
        """Calls OpenAI with retry logic."""
        prompt = f"""You are a Senior Security Engineer reviewing production code.

Analyze the code diff below and return ONLY valid JSON:

{{
  "issues": [
    {{
      "type": "bug|security|performance",
      "severity": "low|medium|high",
      "file": "file_path_from_diff",
      "line": 12,
      "description": "...",
      "fix": "..."
    }}
  ]
}}

STRICT RULES:
- limit output to MAX 3 issues per chunk
- ONLY return real issues (no suggestions like "improve readability", best practices, or stylistic suggestions)
- Focus strictly on: security vulnerabilities, logical bugs, and severe performance issues
- Be specific (mention variable/function exact names)
- Clearly explain WHY it is a problem
- Provide a REAL fix (actual code, not detailed explanation)
- Reject vague advice
- 'file' must match actual file name from diff
- 'line' must be approximate location of issue (int). do NOT leave empty, if unsure, provide best guess

Code Diff:
{diff_chunk}
"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                )

                content = response.choices[0].message.content.strip()

                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                parsed_json = json.loads(content)
                logger.info(f"[analyze_code] success on attempt {attempt + 1}")
                return parsed_json

            except json.JSONDecodeError as e:
                logger.error(f"[analyze_code] error on attempt {attempt + 1}: invalid JSON")
            except GroqError as e:
                logger.error(f"[analyze_code] error on attempt {attempt + 1}: API failure - {str(e)}")
                print(f"❌ GROQ ERROR: {str(e)}")
            except Exception as e:
                logger.error(f"[analyze_code] error on attempt {attempt + 1}: Unexpected - {str(e)}")

            # If we reach here, an exception occurred
            if attempt < max_retries - 1:
                logger.info(f"[analyze_code] Retrying in 1 second...")
                time.sleep(1)

        # Exhausted retries
        logger.error("[analyze_code] Failed after 3 attempts, skipping chunk")
        return {"issues": []}

    def analyze_code(self, diff: str) -> Dict[str, Any]:
        """Analyzes code diff content using AI, handling large diff chunking."""
        if not diff:
            logger.error("[analyze_code] error: empty response. No diff provided.")
            return {"issues": []}

        if not self.client:
            logger.error("[analyze_code] error: OpenAI client not initialized (missing API key)")
            return {"issues": []}

        MAX_CHUNK_SIZE = 4000
        THRESHOLD = 8000

        chunks = []
        if len(diff) > THRESHOLD:
            logger.info(f"[analyze_code] Diff is {len(diff)} chars, splitting into chunks")
            chunks = [diff[i:i + MAX_CHUNK_SIZE] for i in range(0, len(diff), MAX_CHUNK_SIZE)]
        else:
            chunks = [diff]

        all_issues = []
        seen_descriptions = []

        for idx, chunk in enumerate(chunks):
            result = self._analyze_chunk_with_retry(chunk)

            # Merge and deduplicate using normalized matching
            for issue in result.get("issues", []):
                desc = issue.get("description", "").strip()
                if not desc:
                    continue

                is_duplicate = False
                for seen_desc in seen_descriptions:
                    if self._is_similar(desc, seen_desc):
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_descriptions.append(desc)
                    all_issues.append(issue)

        return {"issues": all_issues}

def get_ai_service() -> AIService:
    return AIService()

_ai_service_instance = AIService()

def analyze_code(diff: str) -> Dict[str, Any]:
    return _ai_service_instance.analyze_code(diff)
