import asyncio
import os
import logging
from typing import Tuple, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

class GitHubService:
    """Service to interact with GitHub APIs."""

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.error("GITHUB_TOKEN is not set in environment variables")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def extract_pr_data(self, payload: Dict[str, Any]) -> Tuple[str, str, int]:
        """Extracts owner, repo, and PR number from a webhook payload."""
        try:
            full_name = payload["repository"]["full_name"]
            owner, repo = full_name.split('/')
            pr_number = payload["pull_request"]["number"]
            return owner, repo, pr_number
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to extract PR data from payload: {str(e)}")
            raise ValueError("Invalid GitHub webhook payload format") from e

    async def fetch_diff(self, owner: str, repo: str, pr_number: int) -> Optional[str]:
        """Fetches the code diff of a specific pull request securely using the Pulls API."""
        logger.info(f"Fetching diff for {owner}/{repo} PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.diff"

        try:
            async with httpx.AsyncClient() as client:
                for attempt in range(3):
                    response = await client.get(url, headers=headers, timeout=15.0)
                    if response.status_code == 429:
                        # Adaptive Rate Limiting: Respect GitHub's Retry-After header
                        retry_after = response.headers.get("Retry-After")
                        wait = int(retry_after) if retry_after and retry_after.isdigit() else (attempt + 1) * 2
                        logger.warning(f"Rate limited by GitHub. Waiting {wait}s (Retry-After)...")
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    return response.text
        except httpx.HTTPError as e:
            logger.error(f"GitHub API error while fetching diff: {str(e)}")
            return None

    async def post_comment(self, owner: str, repo: str, pr_number: int, comment: str) -> bool:
        """Posts a comment to a specific pull request with adaptive rate limiting."""
        logger.info(f"Posting comment to {owner}/{repo} PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"

        try:
            async with httpx.AsyncClient() as client:
                for attempt in range(3):
                    response = await client.post(
                        url,
                        headers=self.headers,
                        json={"body": comment},
                        timeout=10.0
                    )
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", (attempt + 1) * 2)
                        wait = int(retry_after) if str(retry_after).isdigit() else (attempt + 1) * 2
                        logger.warning(f"Rate limited during post_comment. Waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    return True
        except httpx.HTTPError as e:
            logger.error(f"GitHub API Error in post_comment: {str(e)}")
            return False

    async def post_inline_comment(self, owner: str, repo: str, pr_number: int, issue: Dict[str, Any], commit_sha: str) -> bool:
        """Posts an inline comment with adaptive rate limiting and fallback."""
        logger.info(f"Posting inline comment to {owner}/{repo} PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        body = issue.get("formatted_body", issue.get("description", ""))
        try:
            line = int(issue.get("line", 1))
        except (ValueError, TypeError):
            line = 1

        payload = {
            "body": body,
            "commit_id": commit_sha,
            "path": issue.get("file", ""),
            "line": line,
            "side": "RIGHT"
        }

        try:
            async with httpx.AsyncClient() as client:
                for attempt in range(3):
                    response = await client.post(
                        url,
                        headers=self.headers,
                        json=payload,
                        timeout=10.0
                    )

                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", (attempt + 1) * 2)
                        wait = int(retry_after) if str(retry_after).isdigit() else (attempt + 1) * 2
                        logger.warning(f"Rate limited during post_inline_comment. Waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue

                    if response.status_code == 422:
                        logger.warning(f"Line mapping error for {issue.get('file')}:{line}. Falling back.")
                        fallback_body = f"🔍 **AI Review Fallback** for `{issue.get('file')}` line `{line}`:\n\n{body}"
                        return await self.post_comment(owner, repo, pr_number, fallback_body)

                    response.raise_for_status()
                    return True
        except httpx.HTTPError as e:
            logger.error(f"GitHub API Error in post_inline_comment: {str(e)}")
            return False

def get_github_service() -> GitHubService:
    return GitHubService()

_github_service_instance = GitHubService()

def extract_pr_data(payload: Dict[str, Any]) -> Tuple[str, str, int]:
    return _github_service_instance.extract_pr_data(payload)

async def fetch_diff(owner: str, repo: str, pr_number: int) -> Optional[str]:
    return await _github_service_instance.fetch_diff(owner, repo, pr_number)

async def post_comment(owner: str, repo: str, pr_number: int, comment: str) -> bool:
    return await _github_service_instance.post_comment(owner, repo, pr_number, comment)

async def post_inline_comment(owner: str, repo: str, pr_number: int, issue: Dict[str, Any], commit_sha: str) -> bool:
    return await _github_service_instance.post_inline_comment(owner, repo, pr_number, issue, commit_sha)
