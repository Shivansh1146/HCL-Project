"""
db_engine.py — Production Database Engine & Connection Abstraction.

Supports:
  - SQLite via aiosqlite (default / development / test)

Design decisions
----------------
* SQLite path yields the **raw aiosqlite.Connection** unchanged so that every
  existing `async with db.execute(...) as cursor:` call in auth/store.py and
  stats_store.py keeps working without modification.

* Connection is configured via environment variables:
    DATABASE_URL     sqlite://path/to/database.db  (or file path)
    TEST_DB_PATH     (for test databases)
"""

import os
import logging
from contextlib import asynccontextmanager

import aiosqlite

logger = logging.getLogger("backend")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL: str = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("TEST_DB_PATH")
    or ""
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _sqlite_path() -> str:
    raw = os.environ.get("TEST_DB_PATH") or ""
    if raw:
        return raw
    return os.path.join(_BASE_DIR, "reviews.db")

# ---------------------------------------------------------------------------
# SQLite connection lifecycle
# ---------------------------------------------------------------------------

_db = None


async def init_db_engine() -> None:
    """Initialise the SQLite database connection."""
    global _db
    if _db is not None:
        return
    try:
        _db = await aiosqlite.connect(DATABASE_URL or os.path.join(_BASE_DIR, "reviews.db"))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA synchronous=NORMAL")
        logger.info("SQLite database connected: %s", DATABASE_URL or os.path.join(_BASE_DIR, "reviews.db"))
    except Exception as exc:
        logger.error("Failed to connect to SQLite database: %s", exc)
        raise


async def close_db_engine() -> None:
    """Gracefully close the SQLite database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("SQLite database connection closed.")


@asynccontextmanager
async def get_db():
    """Async context manager for database connections (SQLite only)."""
    await init_db_engine()
    yield _db
