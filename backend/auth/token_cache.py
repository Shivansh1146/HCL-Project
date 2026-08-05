"""
auth/token_cache.py — Installation Access Token Cache.

Responsibilities
────────────────
1.  Cache tokens in memory keyed by installation_id.
2.  Return cached token if it expires > REFRESH_BUFFER_SECONDS from now.
3.  Proactively refresh when within the buffer window (default 5 min).
4.  Serialize concurrent requests for the same installation via an asyncio.Lock
    so we never make duplicate token API calls ("thundering herd" prevention).
5.  Retry transient GitHub API failures with exponential backoff (3 attempts).
6.  Handle expired / invalid JWT gracefully — regenerate JWT and retry.
7.  Log every cache hit, miss, refresh, and failure.
8.  Provide a `token_status()` method for diagnostics / tests.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Coroutine, Dict, Optional, Tuple

logger = logging.getLogger("backend.token_cache")

# Refresh token this many seconds before actual expiry to avoid clock-skew races
REFRESH_BUFFER_SECONDS = 300  # 5 minutes

# Retry configuration
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0  # seconds, doubled each attempt


# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------

@dataclass
class _CachedToken:
    token: str
    expires_at: float          # Unix timestamp (UTC)
    installation_id: int
    fetched_at: float = field(default_factory=time.time)

    def is_valid(self) -> bool:
        """True if token is non-empty and does not expire within the buffer."""
        return bool(self.token) and time.time() < (
            self.expires_at - REFRESH_BUFFER_SECONDS
        )

    def seconds_until_expiry(self) -> float:
        return max(0.0, self.expires_at - time.time())

    def expires_at_iso(self) -> str:
        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public status dict (returned by token_status / diagnostic endpoint)
# ---------------------------------------------------------------------------

@dataclass
class TokenStatus:
    installation_id: int
    cached: bool
    valid: bool
    expires_at: Optional[str]        # ISO-8601 or None
    seconds_until_expiry: Optional[float]
    fetched_at: Optional[str]        # ISO-8601 or None
    refresh_buffer_seconds: int = REFRESH_BUFFER_SECONDS

    def as_dict(self) -> dict:
        return {
            "installation_id": self.installation_id,
            "cached": self.cached,
            "valid": self.valid,
            "expires_at": self.expires_at,
            "seconds_until_expiry": round(self.seconds_until_expiry, 1)
            if self.seconds_until_expiry is not None
            else None,
            "fetched_at": self.fetched_at,
            "refresh_buffer_seconds": self.refresh_buffer_seconds,
        }


# ---------------------------------------------------------------------------
# Token fetcher type alias
# ---------------------------------------------------------------------------

# The cache accepts any async callable (installation_id) -> (token, expires_at_iso)
# This decouples the cache from the GitHub HTTP logic.
TokenFetcherFn = Callable[[int], Coroutine[None, None, Tuple[str, str]]]


# ---------------------------------------------------------------------------
# InstallationTokenCache
# ---------------------------------------------------------------------------

class InstallationTokenCache:
    """
    Thread-safe, coroutine-safe in-memory cache for GitHub installation tokens.

    Usage
    ─────
        cache = InstallationTokenCache(fetch_fn=my_github_fetcher)
        token = await cache.get_token(installation_id)
    """

    def __init__(self, fetch_fn: TokenFetcherFn) -> None:
        """
        Args:
            fetch_fn: Async callable that contacts GitHub and returns
                      (token_string, expires_at_iso) tuple.
        """
        self._fetch_fn = fetch_fn
        self._cache: Dict[int, _CachedToken] = {}
        # One lock per installation prevents duplicate simultaneous refreshes
        self._locks: Dict[int, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_token(self, installation_id: int) -> str:
        """
        Return a valid installation access token.

        - Returns cached token if it won't expire within REFRESH_BUFFER_SECONDS.
        - Otherwise fetches a new token (serialized per installation_id).
        - Raises RuntimeError if all retries are exhausted.
        """
        # Fast path — check cache without locking
        cached = self._cache.get(installation_id)
        if cached and cached.is_valid():
            logger.debug(
                "[TokenCache] HIT  installation=%d  expires_in=%.0fs",
                installation_id,
                cached.seconds_until_expiry(),
            )
            return cached.token

        # Slow path — serialize refresh per installation
        lock = self._get_lock(installation_id)
        async with lock:
            # Re-check inside the lock (another coroutine may have refreshed)
            cached = self._cache.get(installation_id)
            if cached and cached.is_valid():
                logger.debug(
                    "[TokenCache] HIT (post-lock) installation=%d  expires_in=%.0fs",
                    installation_id,
                    cached.seconds_until_expiry(),
                )
                return cached.token

            # Need to fetch / refresh
            return await self._refresh(installation_id)

    def invalidate(self, installation_id: int) -> None:
        """Remove a cached token, forcing the next call to fetch a fresh one."""
        removed = self._cache.pop(installation_id, None)
        if removed:
            logger.info(
                "[TokenCache] INVALIDATED  installation=%d", installation_id
            )

    def token_status(self, installation_id: int) -> TokenStatus:
        """Return diagnostic information about the cached token (never fetches)."""
        cached = self._cache.get(installation_id)
        if not cached:
            return TokenStatus(
                installation_id=installation_id,
                cached=False,
                valid=False,
                expires_at=None,
                seconds_until_expiry=None,
                fetched_at=None,
            )
        return TokenStatus(
            installation_id=installation_id,
            cached=True,
            valid=cached.is_valid(),
            expires_at=cached.expires_at_iso(),
            seconds_until_expiry=cached.seconds_until_expiry(),
            fetched_at=datetime.fromtimestamp(
                cached.fetched_at, tz=timezone.utc
            ).isoformat(),
        )

    def clear_all(self) -> None:
        """Clear every cached token (useful in tests)."""
        self._cache.clear()
        logger.debug("[TokenCache] All tokens cleared.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_lock(self, installation_id: int) -> asyncio.Lock:
        if installation_id not in self._locks:
            self._locks[installation_id] = asyncio.Lock()
        return self._locks[installation_id]

    async def _refresh(self, installation_id: int) -> str:
        """
        Fetch a fresh token from GitHub with exponential-backoff retry.

        Retry strategy:
          attempt 1 → immediate
          attempt 2 → wait BASE_RETRY_DELAY seconds
          attempt 3 → wait BASE_RETRY_DELAY * 2 seconds
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[TokenCache] FETCH  installation=%d  attempt=%d/%d",
                    installation_id,
                    attempt,
                    MAX_RETRIES,
                )
                token_str, expires_at_iso = await self._fetch_fn(installation_id)

                if not token_str:
                    raise ValueError("Empty token returned by fetcher.")

                expires_at = _parse_iso_to_timestamp(expires_at_iso)
                cached = _CachedToken(
                    token=token_str,
                    expires_at=expires_at,
                    installation_id=installation_id,
                )
                self._cache[installation_id] = cached

                logger.info(
                    "[TokenCache] STORED  installation=%d  expires_at=%s  "
                    "valid_for=%.0fs",
                    installation_id,
                    expires_at_iso,
                    cached.seconds_until_expiry(),
                )
                return token_str

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[TokenCache] FAIL  installation=%d  attempt=%d  error=%s",
                    installation_id,
                    attempt,
                    str(exc),
                )
                if attempt < MAX_RETRIES:
                    delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.debug(
                        "[TokenCache] Retrying in %.1fs …", delay
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Failed to obtain installation token for installation "
            f"{installation_id} after {MAX_RETRIES} attempts: {last_error}"
        ) from last_error


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _parse_iso_to_timestamp(iso_str: str) -> float:
    """
    Parse a GitHub-style ISO-8601 expiry string to a UTC Unix timestamp.

    GitHub returns:  "2024-01-01T01:00:00Z"
    """
    # Replace trailing Z with +00:00 for Python 3.10 compatibility
    normalized = iso_str.rstrip("Z") + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        # Fallback: assume token lasts 1 hour from now
        logger.warning(
            "[TokenCache] Could not parse expiry %r; assuming 1h from now.", iso_str
        )
        return time.time() + 3600.0
    return dt.timestamp()
