import asyncio
import os
import logging
from typing import Tuple, Dict, Any, Optional
import httpx
from datetime import datetime
from db_engine import get_db

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"

class GitHubService:
    """Service to interact with GitHub APIs."""

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.error("GITHUB_TOKEN is not set in environment variables")
        else:
            logger.info(f"✅ [GITHUB_SERVICE] GITHUB_TOKEN is set (length: {len(self.token)} chars)")

        # Use 'Bearer' prefix which is the modern standard for GitHub PATs and Apps
        self.headers = {
            "Authorization": f"Bearer {self.token}" if self.token else "",
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
        logger.info(f"📥 [GITHUB_SERVICE] Fetching diff for {owner}/{repo} PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        
        logger.info(f"🔍 [GITHUB_SERVICE] URL: {url}")
        logger.info(f"🔍 [GITHUB_SERVICE] HTTP Method: GET")
        
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.diff"
        
        # Log token type
        auth_header = headers.get("Authorization", "")
        if "Bearer" in auth_header:
            logger.info(f"🔍 [GITHUB_SERVICE] Authorization: Bearer token (token present)")
        elif "token" in auth_header:
            logger.info(f"🔍 [GITHUB_SERVICE] Authorization: Token-based")
        else:
            logger.warning(f"⚠️ [GITHUB_SERVICE] Authorization: {auth_header[:50] if auth_header else 'MISSING'}")
        
        logger.info(f"🔍 [GITHUB_SERVICE] Accept header: {headers.get('Accept')}")

        try:
            # Explicitly follow redirects for diff fetching as GitHub may redirect to patch-diff.githubusercontent.com
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                for attempt in range(3):
                    logger.info(f"🔄 [GITHUB_SERVICE] Attempt {attempt + 1}/3 to fetch diff")
                    
                    response = await client.get(url, headers=headers)
                    
                    logger.info(f"📊 [GITHUB_SERVICE] HTTP Status: {response.status_code}")
                    logger.info(f"📊 [GITHUB_SERVICE] Response Headers: {dict(response.headers)}")
                    logger.info(f"📊 [GITHUB_SERVICE] Response Body (first 500 chars): {response.text[:500] if response.text else 'EMPTY'}")
                    
                    # Store API response in database for debugging
                    try:
                        async with get_db() as db:
                            await db.execute(
                                "INSERT INTO webhook_deliveries (delivery_id, event_type, action, status, processed_at) VALUES (?, ?, ?, ?, ?)",
                                (f"github_api_{owner}_{repo}_{pr_number}", "github_api", "diff_fetch", f"status_{response.status_code}", datetime.now().isoformat())
                            )
                            await db.commit()
                            
                            # Store response body
                            await db.execute(
                                "INSERT INTO webhook_deliveries (delivery_id, event_type, action, status, processed_at) VALUES (?, ?, ?, ?, ?)",
                                (f"github_response_{owner}_{repo}_{pr_number}", "github_api", "response_body", response.text[:500] if response.text else "EMPTY", datetime.now().isoformat())
                            )
                            await db.commit()
                    except Exception as db_error:
                        logger.error(f"Failed to store GitHub API response in database: {db_error}")
                    
                    if response.status_code == 429:
                        # Adaptive Rate Limiting: Respect GitHub's Retry-After header
                        retry_after = response.headers.get("Retry-After")
                        wait = int(retry_after) if retry_after and retry_after.isdigit() else (attempt + 1) * 2
                        logger.warning(f"Rate limited by GitHub. Waiting {wait}s (Retry-After)...")
                        await asyncio.sleep(wait)
                        continue

                    if response.status_code == 401:
                        logger.error(f"Unauthorized access to {url}. Token status: {'Present' if self.token else 'Missing'}")

                    if response.status_code != 200:
                        logger.error(f"❌ [GITHUB_SERVICE] HTTP Error {response.status_code}: {response.text}")
                        return None
                    
                    logger.info(f"✅ [GITHUB_SERVICE] Diff fetched successfully, length: {len(response.text)}")
                    return response.text
                    
        except httpx.HTTPError as e:
            import traceback
            logger.error(f"❌ [GITHUB_SERVICE] HTTP Error while fetching diff: {str(e)}")
            logger.error(f"❌ [GITHUB_SERVICE] Exception type: {type(e).__name__}")
            logger.error(f"❌ [GITHUB_SERVICE] Traceback: {traceback.format_exc()}")
            
            # Store error in database
            try:
                async with get_db() as db:
                    await db.execute(
                        "INSERT INTO webhook_deliveries (delivery_id, event_type, action, status, processed_at) VALUES (?, ?, ?, ?, ?)",
                        (f"github_error_{owner}_{repo}_{pr_number}", "github_api", "http_error", f"{type(e).__name__}: {str(e)}", datetime.now().isoformat())
                    )
                    await db.commit()
            except Exception as db_error:
                logger.error(f"Failed to store GitHub error in database: {db_error}")
            
            return None
        except Exception as e:
            import traceback
            logger.error(f"❌ [GITHUB_SERVICE] Unexpected error while fetching diff: {str(e)}")
            logger.error(f"❌ [GITHUB_SERVICE] Exception type: {type(e).__name__}")
            logger.error(f"❌ [GITHUB_SERVICE] Traceback: {traceback.format_exc()}")
            
            # Store error in database
            try:
                async with get_db() as db:
                    await db.execute(
                        "INSERT INTO webhook_deliveries (delivery_id, event_type, action, status, processed_at) VALUES (?, ?, ?, ?, ?)",
                        (f"github_error_{owner}_{repo}_{pr_number}", "github_api", "unexpected_error", f"{type(e).__name__}: {str(e)}", datetime.now().isoformat())
                    )
                    await db.commit()
            except Exception as db_error:
                logger.error(f"Failed to store GitHub error in database: {db_error}")
            
            return None

    async def post_comment(self, owner: str, repo: str, pr_number: int, comment: str) -> bool:
        """Posts a comment to a specific pull request with adaptive rate limiting."""
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        logger.info(f"DEBUG URL: {url}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for attempt in range(3):
                    response = await client.post(
                        url,
                        headers=self.headers,
                        json={"body": comment}
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

    async def post_inline_comment(self, owner: str, repo: str, pr_number: int, issue: Dict[str, Any], commit_sha: str, suggestion: Optional[str] = None) -> bool:
        """Posts an inline review comment. If a suggestion block exists, posts it as a
        committable GitHub suggestion. Context (severity/description) goes in the body
        ABOVE the suggestion so GitHub still renders the one-click 'Commit suggestion' button."""
        logger.info(f"Posting inline comment to {owner}/{repo} PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
            issue.get("severity", "").upper(), "🔍"
        )
        severity = issue.get("severity", "medium").upper()
        title = issue.get("title", "Code Issue")
        description = issue.get("description", "")
        file_path = issue.get("file", "")

        try:
            line = int(issue.get("line", 1))
        except (ValueError, TypeError):
            line = 1

        # Build comment body:
        # GitHub renders the ```suggestion block as a committable suggestion
        # ONLY when the block is present in the body. Any text before it is fine.
        if suggestion:
            comment_body = (
                f"{severity_emoji} **[{severity}] {title}**\n\n"
                f"{description}\n\n"
                f"{suggestion}"
            )
        else:
            comment_body = (
                f"{severity_emoji} **[{severity}] {title}**\n\n"
                f"{description}\n\n"
                f"*No automated fix available — manual review required.*"
            )

        payload = {
            "body": comment_body,
            "commit_id": commit_sha,
            "path": file_path,
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
                        logger.warning(f"Line mapping error for {file_path}:{line} — {response.text[:200]}")
                        fallback_body = (
                            f"{severity_emoji} **[{severity}] {title}** "
                            f"(in `{file_path}` near line {line})\n\n"
                            f"{description}\n\n"
                            + (suggestion if suggestion else "*No automated fix available.*")
                        )
                        return await self.post_comment(owner, repo, pr_number, fallback_body)

                    response.raise_for_status()
                    logger.info(f"✅ Inline comment posted: {file_path}:{line}")
                    return True
        except httpx.HTTPError as e:
            logger.error(f"GitHub API Error in post_inline_comment: {str(e)}")
            return False

    async def post_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        event: str,
        body: str,
        comments: Optional[list] = None,
        commit_sha: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publishes a pull request review using GitHub's Pull Request Review API.
        Event: APPROVE, COMMENT, REQUEST_CHANGES.
        Handles transient retries (429 rate limit, 5xx errors) and self-review fallback (422).
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        headers = self.headers.copy()
        tok = token or self.token
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        headers["Accept"] = "application/vnd.github.v3+json"

        payload: Dict[str, Any] = {
            "body": body,
            "event": event,
            "comments": comments or []
        }
        if commit_sha:
            payload["commit_id"] = commit_sha

        logger.info(f"Posting PR review to {owner}/{repo}#{pr_number} (event={event}, comments={len(comments or [])})")

        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(1, 4):
                try:
                    resp = await client.post(url, headers=headers, json=payload)

                    if resp.status_code == 429 or resp.status_code >= 500:
                        retry_after = resp.headers.get("Retry-After")
                        wait = int(retry_after) if retry_after and retry_after.isdigit() else attempt * 2
                        logger.warning(f"GitHub review API returned {resp.status_code}. Retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        continue

                    # GitHub returns 422 if user tries to APPROVE or REQUEST_CHANGES on their own PR
                    if resp.status_code == 422 and payload.get("event") in ("APPROVE", "REQUEST_CHANGES"):
                        logger.warning(f"GitHub returned 422 for event={payload['event']} (likely self-review). Retrying with event='COMMENT'.")
                        payload["event"] = "COMMENT"
                        resp = await client.post(url, headers=headers, json=payload)

                    resp.raise_for_status()
                    data = resp.json()
                    review_id = data.get("id", 123456)
                    logger.info(f"✅ GitHub Review published successfully: review_id={review_id}")
                    return {
                        "status": "success",
                        "review_id": review_id,
                        "data": data
                    }
                except httpx.HTTPError as exc:
                    logger.error(f"Attempt {attempt} failed posting PR review to {owner}/{repo}#{pr_number}: {str(exc)}")
                    if attempt == 3:
                        raise RuntimeError(f"GitHub API Error posting review: {str(exc)}") from exc

        raise RuntimeError(f"Failed to post PR review to {owner}/{repo}#{pr_number} after retries")

def get_github_service() -> GitHubService:
    return GitHubService()

_github_service_instance = GitHubService()

def extract_pr_data(payload: Dict[str, Any]) -> Tuple[str, str, int]:
    return _github_service_instance.extract_pr_data(payload)

async def fetch_diff(owner: str, repo: str, pr_number: int) -> Optional[str]:
    return await _github_service_instance.fetch_diff(owner, repo, pr_number)

async def post_comment(owner: str, repo: str, pr_number: int, comment: str) -> bool:
    return await _github_service_instance.post_comment(owner, repo, pr_number, comment)

async def post_inline_comment(owner: str, repo: str, pr_number: int, issue: Dict[str, Any], commit_sha: str, suggestion: Optional[str] = None) -> bool:
    return await _github_service_instance.post_inline_comment(owner, repo, pr_number, issue, commit_sha, suggestion)

async def post_pull_request_review(owner: str, repo: str, pr_number: int, event: str, body: str, comments: Optional[list] = None, commit_sha: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
    return await _github_service_instance.post_pull_request_review(owner, repo, pr_number, event, body, comments, commit_sha, token)
async def post_status(owner: str, repo: str, sha: str, state: str, description: str, target_url: str = None):
    """
    Updates the GitHub Commit Status.
    state: 'pending', 'success', 'error', 'failure'
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/statuses/{sha}"
    payload = {
        "state": state,
        "description": description[:140],
        "context": "AI Code Reviewer"
    }
    if target_url:
        payload["target_url"] = target_url

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=_github_service_instance.headers, json=payload, timeout=10.0)
            if resp.status_code not in (201, 200):
                logger.error(f"Failed to post status: {resp.status_code} - {resp.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error posting status: {str(e)}")
            return False
