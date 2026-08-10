"""
db_engine.py — Production Database Engine & Connection Abstraction.

Supports:
  - PostgreSQL via asyncpg (primary)

Design decisions
----------------
* PostgreSQL connection pool for production performance
* Environment variable configuration via DATABASE_URL
* Async context manager for database operations
"""

import os
import logging
from contextlib import asynccontextmanager

import asyncpg

# ---------------------------------------------------------------------------
# Monkeypatch asyncpg Connection for SQLite backward compatibility
# ---------------------------------------------------------------------------

class CursorWrapper:
    def __init__(self, result, status_str):
        self._result = result
        self.status_str = status_str
        self._idx = 0

    @property
    def rowcount(self) -> int:
        if not self.status_str:
            return 0
        parts = self.status_str.split()
        if not parts:
            return 0
        try:
            return int(parts[-1])
        except ValueError:
            return 0

    async def fetchall(self):
        return self._result

    async def fetchone(self):
        if self._idx < len(self._result):
            row = self._result[self._idx]
            self._idx += 1
            return row
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


_original_execute = asyncpg.Connection.execute
_original_fetch = asyncpg.Connection.fetch
_original_fetchrow = asyncpg.Connection.fetchrow
_original_fetchval = asyncpg.Connection.fetchval

def _normalize_query_and_args(query: str, args: tuple):
    # Convert '?' placeholders to '$1', '$2', ... for PostgreSQL compatibility
    if '?' in query:
        count = 1
        while '?' in query:
            query = query.replace('?', f'${count}', 1)
            count += 1
    
    # Unpack tuple/list argument if it is the only argument passed
    if len(args) == 1 and isinstance(args[0], (tuple, list)):
        args = tuple(args[0])
        
    return query, args

async def _wrapped_execute(self, query, *args, **kwargs):
    # Check for multi-command queries (semicolons in the middle of the query)
    # connection.reset() uses multi-commands like "RESET ALL; UNLISTEN *;"
    cleaned_query = query.strip()
    if ';' in cleaned_query[:-1]:
        status_str = await _original_execute(self, query, *args, **kwargs)
        return CursorWrapper([], status_str)

    query, args = _normalize_query_and_args(query, args)
    
    # Check if this is a SELECT-like query or PRAGMA
    q_upper = query.strip().upper()
    if q_upper.startswith(('SELECT', 'PRAGMA', 'SHOW', 'WITH')):
        rows = await _original_fetch(self, query, *args, **kwargs)
        status_str = f"SELECT {len(rows)}"
        return CursorWrapper(rows, status_str)
    else:
        status_str = await _original_execute(self, query, *args, **kwargs)
        return CursorWrapper([], status_str)

async def _wrapped_fetch(self, query, *args, **kwargs):
    query, args = _normalize_query_and_args(query, args)
    return await _original_fetch(self, query, *args, **kwargs)

async def _wrapped_fetchrow(self, query, *args, **kwargs):
    query, args = _normalize_query_and_args(query, args)
    return await _original_fetchrow(self, query, *args, **kwargs)

async def _wrapped_fetchval(self, query, *args, **kwargs):
    query, args = _normalize_query_and_args(query, args)
    return await _original_fetchval(self, query, *args, **kwargs)

async def _noop_commit(self, *args, **kwargs):
    pass

asyncpg.Connection.execute = _wrapped_execute
asyncpg.Connection.fetch = _wrapped_fetch
asyncpg.Connection.fetchrow = _wrapped_fetchrow
asyncpg.Connection.fetchval = _wrapped_fetchval
asyncpg.Connection.commit = _noop_commit
asyncpg.Connection.rollback = _noop_commit

logger = logging.getLogger("backend")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# Log DATABASE_URL presence for debugging
if DATABASE_URL:
    logger.info("DATABASE_URL environment variable is present (length: %d characters)", len(DATABASE_URL))
else:
    logger.error("DATABASE_URL environment variable is NOT SET")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required. "
        "Please set DATABASE_URL to your PostgreSQL connection string."
    )

_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
_POOL_TIMEOUT = float(os.environ.get("DB_POOL_TIMEOUT", "30.0"))

# ---------------------------------------------------------------------------
# PostgreSQL connection pool lifecycle
# ---------------------------------------------------------------------------

_pg_pool = None


async def init_db_engine() -> None:
    """Initialise the PostgreSQL async connection pool."""
    global _pg_pool
    if _pg_pool is not None:
        return
    try:
        _pg_pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=_POOL_SIZE,
            command_timeout=_POOL_TIMEOUT,
        )
        logger.info("PostgreSQL asyncpg connection pool initialised (size=%d).", _POOL_SIZE)
    except Exception as exc:
        logger.error("Failed to initialise PostgreSQL pool: %s", exc)
        raise


async def close_db_engine() -> None:
    """Gracefully close the PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
        logger.info("PostgreSQL asyncpg connection pool closed.")


# ---------------------------------------------------------------------------
# Public get_db() context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_db():
    """
    Async context manager that yields a PostgreSQL connection.
    
    PostgreSQL via asyncpg with connection pooling.
    """
    global _pg_pool
    if _pg_pool is None:
        await init_db_engine()
    
    async with _pg_pool.acquire() as conn:
        async with conn.transaction():
            yield conn
