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
