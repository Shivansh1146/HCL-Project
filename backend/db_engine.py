"""
db_engine.py — Production Database Engine & Connection Abstraction.

Supports:
  - SQLite  via aiosqlite  (default / development / test)
  - PostgreSQL via asyncpg (production, when DATABASE_URL starts with postgres)

Design decisions
----------------
* SQLite path yields the **raw aiosqlite.Connection** unchanged so that every
  existing `async with db.execute(...) as cursor:` call in auth/store.py and
  stats_store.py keeps working without modification.

* PostgreSQL path yields a PGConnectionWrapper that shims the same interface:
    - `async with db.execute(sql, params) as cursor:`  (via __aenter__/__aexit__)
    - `await db.execute(sql, params)`                   (plain await)
    - `cursor.fetchone()` / `cursor.fetchall()`         (async, returns dicts)

* Connection pool is configured via environment variables:
    DATABASE_URL     postgresql+asyncpg://user:pass@host/db  (or postgres://)
    DB_POOL_SIZE     (default 10)
    DB_MAX_OVERFLOW  (default 20, unused by asyncpg – kept for compat)
    DB_POOL_TIMEOUT  (default 30.0 seconds)
"""

import os
import re
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
POOL_SIZE    = int(float(os.environ.get("DB_POOL_SIZE", "10")))
POOL_TIMEOUT = float(os.environ.get("DB_POOL_TIMEOUT", "30.0"))

IS_POSTGRES: bool = DATABASE_URL.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://"))

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _sqlite_path() -> str:
    raw = os.environ.get("TEST_DB_PATH") or ""
    if raw:
        return raw
    # Use DATABASE_PATH if set (for Render persistent disk)
    db_path = os.environ.get("DATABASE_PATH")
    if db_path:
        return db_path
    return os.path.join(_BASE_DIR, "reviews.db")

# ---------------------------------------------------------------------------
# PostgreSQL pool lifecycle
# ---------------------------------------------------------------------------

_pg_pool = None


def _pg_dsn(url: str) -> str:
    """Normalise any Postgres URL variant to the `postgres://` form asyncpg expects."""
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


async def init_db_engine() -> None:
    """Initialise the PostgreSQL async connection pool (no-op for SQLite)."""
    global _pg_pool
    if not IS_POSTGRES or _pg_pool is not None:
        return
    try:
        import asyncpg
        _pg_pool = await asyncpg.create_pool(
            dsn=_pg_dsn(DATABASE_URL),
            min_size=2,
            max_size=POOL_SIZE,
            command_timeout=POOL_TIMEOUT,
        )
        logger.info("PostgreSQL asyncpg connection pool initialised (size=%d).", POOL_SIZE)
    except Exception as exc:
        logger.error("Failed to initialise PostgreSQL pool: %s", exc)
        raise


async def close_db_engine() -> None:
    """Gracefully close the PostgreSQL connection pool (no-op for SQLite)."""
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
        logger.info("PostgreSQL asyncpg connection pool closed.")


# ---------------------------------------------------------------------------
# PostgreSQL compatibility shim
# ---------------------------------------------------------------------------

def _pg_translate(sql: str) -> str:
    """Convert SQLite-style SQL to PostgreSQL syntax."""
    # ? → $1, $2, …
    idx = 0
    def _replace(_m):
        nonlocal idx
        idx += 1
        return f"${idx}"
    sql = re.sub(r"\?", _replace, sql)
    # SQLite DDL quirks
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    sql = sql.replace("date('now')", "CURRENT_DATE")
    sql = sql.replace("datetime('now')", "NOW()")
    return sql


class PGCursor:
    """Async cursor-compatible wrapper around an asyncpg result set."""

    def __init__(self, rows):
        self._rows = rows or []

    async def fetchone(self):
        return dict(self._rows[0]) if self._rows else None

    async def fetchall(self):
        return [dict(r) for r in self._rows]

    def __iter__(self):
        return iter(dict(r) for r in self._rows)


class _PGExecuteContext:
    """Supports both `await db.execute(...)` and `async with db.execute(...) as cur:`."""

    def __init__(self, conn, sql, params):
        self._conn   = conn
        self._sql    = _pg_translate(sql)
        self._params = params
        self._cursor = None

    def __await__(self):
        return self._run().__await__()

    async def _run(self):
        rows = await self._conn.fetch(self._sql, *self._params)
        return PGCursor(rows)

    async def __aenter__(self):
        rows = await self._conn.fetch(self._sql, *self._params)
        self._cursor = PGCursor(rows)
        return self._cursor

    async def __aexit__(self, *_):
        pass


class PGConnectionWrapper:
    """Wraps an asyncpg Connection to look like an aiosqlite Connection."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, parameters=()):
        return _PGExecuteContext(self._conn, sql, parameters)

    async def commit(self):
        pass  # asyncpg transactions are managed by the pool context

    async def rollback(self):
        pass

    # Forward any other attribute access to the underlying connection
    def __getattr__(self, name):
        return getattr(self._conn, name)


# ---------------------------------------------------------------------------
# Public get_db() context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_db():
    """
    Async context manager that yields a database connection.

    SQLite  → raw aiosqlite.Connection  (supports `async with db.execute() as cur:`)
    Postgres → PGConnectionWrapper shim  (same interface)
    """
    if IS_POSTGRES:
        global _pg_pool
        if _pg_pool is None:
            await init_db_engine()
        async with _pg_pool.acquire() as conn:
            async with conn.transaction():
                yield PGConnectionWrapper(conn)
    else:
        path = _sqlite_path()
        db: aiosqlite.Connection = await aiosqlite.connect(path, timeout=30.0)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        try:
            yield db          # ← raw aiosqlite.Connection, fully protocol-compatible
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
