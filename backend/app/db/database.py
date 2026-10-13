"""PostgreSQL connection pool for Supabase via psycopg2.

Replaces SQLAlchemy ORM — all queries are raw SQL written directly
in the route/service files that need them.

Usage (FastAPI dependency):
    from app.db.database import get_conn

    @router.get("/example")
    def example(conn=Depends(get_conn)):
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (name,))
            row = cur.fetchone()
"""

import logging
from typing import Generator, Any

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool (created once at module import, shared across requests)
# ---------------------------------------------------------------------------
_pool: "pg_pool.ThreadedConnectionPool | None" = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            dbname=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            sslmode=settings.DB_SSLMODE,
            cursor_factory=RealDictCursor,
        )
        logger.info(
            f"[DB] Supabase connection pool created → "
            f"{settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        )
    return _pool


def get_conn() -> Generator[Any, None, None]:
    """FastAPI dependency — yields a psycopg2 connection, returns it to pool after request.

    Typed as Generator[Any, ...] so FastAPI does NOT try to validate the
    yielded value as a request body field. Use as: conn=Depends(get_conn).
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db() -> None:
    """Create tables from schema.sql if they don't already exist."""
    from pathlib import Path

    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        logger.warning("[DB] schema.sql not found — skipping table creation.")
        return

    sql = schema_path.read_text(encoding="utf-8")
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        logger.info("[DB] Tables verified / created from schema.sql.")
    except Exception as e:
        conn.rollback()
        logger.error(f"[DB] init_db failed: {e}", exc_info=True)
        raise
    finally:
        pool.putconn(conn)
