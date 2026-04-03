import os
import requests
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GitHubService:
    """Service to interact with GitHub APIs."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        } if self.github_token else {}

        if not self.github_token or self.github_token == "your_github_token_here":
            logger.warning("GitHub token is not properly set. API limits will apply and private endpoints will fail.")

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

    def fetch_diff(self, owner: str, repo: str, pr_number: int) -> Optional[str]:
        """Fetches the code diff of a specific pull request securely."""
        logger.info(f"Fetching diff for {owner}/{repo} PR #{pr_number}")

        diff_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}.diff"

        headers = self.headers.copy()
        # Strictly accept native diff
        headers["Accept"] = "application/vnd.github.v3.diff"

        try:
            response = requests.get(diff_url, headers=headers)
            print("DIFF STATUS:", response.status_code)
            response.raise_for_status()

            diff_text = response.text
            if not diff_text:
                logger.warning(f"No diff text found in PR #{pr_number}")
                return ""

            logger.info(f"Successfully fetched diff for PR #{pr_number}")
            return diff_text

        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API error while fetching diff: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching diff: {str(e)}")
            return None

    def post_comment(self, owner: str, repo: str, pr_number: int, comment: str) -> bool:
        """Posts a comment to a specific pull request."""
        logger.info(f"Posting comment to {owner}/{repo} PR #{pr_number}")

        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json={"body": comment}
            )
            print("GITHUB POST STATUS:", response.status_code)
            print("GITHUB POST RESPONSE:", response.text)
            response.raise_for_status()
            logger.info(f"Successfully posted comment to PR #{pr_number}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API error while posting comment: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while posting comment: {str(e)}")
            return False

    def post_inline_comment(self, owner: str, repo: str, pr_number: int, issue: Dict[str, Any], commit_sha: str) -> bool:
        """Posts an inline comment to a specific file and line in a PR, with a fallback to general comment."""
        logger.info(f"Posting inline comment to {owner}/{repo} PR #{pr_number}")

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        body = issue.get("formatted_body", issue.get("description", ""))

        payload = {
            "body": body,
            "commit_id": commit_sha,
            "path": issue.get("file", ""),
            "line": int(issue.get("line", 1))
        }

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )
            print("GITHUB POST STATUS:", response.status_code)
            print("GITHUB POST RESPONSE:", response.text)
            response.raise_for_status()
            logger.info(f"Successfully posted inline comment to PR #{pr_number}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API error while posting inline comment: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")

            # Fallback to general PR comment
            logger.warning(f"Falling back to general PR comment for issue in {issue.get('file')} line {issue.get('line')}")
            fallback_body = f"**(Fallback from inline comment for `{issue.get('file')}` line `{issue.get('line')}`)**\n\n{body}"
            return self.post_comment(owner, repo, pr_number, fallback_body)
        except Exception as e:
            logger.error(f"Unexpected error while posting inline comment: {str(e)}")
            return False

def get_github_service() -> GitHubService:
    return GitHubService()

# Global singleton
_service_instance = GitHubService()

def extract_pr_data(payload: Dict[str, Any]) -> Tuple[str, str, int]:
    return _service_instance.extract_pr_data(payload)

def fetch_diff(owner: str, repo: str, pr_number: int) -> Optional[str]:
    return _service_instance.fetch_diff(owner, repo, pr_number)

def post_comment(owner: str, repo: str, pr_number: int, comment: str) -> bool:
    return _service_instance.post_comment(owner, repo, pr_number, comment)

def post_inline_comment(owner: str, repo: str, pr_number: int, issue: Dict[str, Any], commit_sha: str) -> bool:
    return _service_instance.post_inline_comment(owner, repo, pr_number, issue, commit_sha)
