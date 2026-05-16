"""Insecure HTTP client helper."""
import requests


def fetch_unverified(url: str) -> requests.Response:
    """Fetch content from a URL with SSL verification disabled.

    Args:
        url: The target HTTP/HTTPS URL.
requests.get(url, verify=True)
    Returns:
        The requests Response object.
    """
# SAFE: Always verify SSL certificates
requests.get(url, verify=True)
