"""
Dual-Engine Database Engine & Session Management for Campus Automation System (MARVEL).

Supports:
  1. SQLite: Local development and testing (zero-configuration, in-memory StaticPool, PRAGMA foreign_keys).
  2. PostgreSQL 16+: High-concurrency staging and production (MVCC, QueuePool, connection budget, pool_pre_ping).

Multi-Worker Connection Budget Formula:
  Total Max PostgreSQL Connections = Worker Count * (DB_POOL_SIZE + DB_MAX_OVERFLOW)
  Example with 4 Uvicorn workers and defaults (5 + 10):
    Steady-state: 4 * 5 = 20 connections
    Max burst:    4 * (5 + 10) = 60 connections
    (Well within PostgreSQL default max_connections of 100)
"""

import logging
import sqlite3
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

from backend.core.config import settings, normalize_database_url, mask_database_url

logger = logging.getLogger(__name__)

# Register SQLite PRAGMA listener globally on Engine class.
# The type check `isinstance(dbapi_connection, sqlite3.Connection)` guarantees this listener
# only executes for SQLite connections and is completely inert for PostgreSQL connections.
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app_engine(
    url: Optional[str] = None,
    echo: Optional[bool] = None,
    pool_size: Optional[int] = None,
    max_overflow: Optional[int] = None,
    pool_timeout: Optional[int] = None,
    pool_recycle: Optional[int] = None,
    pool_pre_ping: Optional[bool] = None,
) -> Engine:
    """Create a configured SQLAlchemy Engine instance supporting both SQLite and PostgreSQL.

    Args:
        url: Database URL. If None, resolves from centralized application settings.
        echo: Whether to echo SQL statements. Defaults to settings.DB_ECHO in development.
        pool_size: Base connection pool size (PostgreSQL QueuePool).
        max_overflow: Maximum overflow connections above pool_size (PostgreSQL QueuePool).
        pool_timeout: Seconds to wait before connection checkout timeout (PostgreSQL QueuePool).
        pool_recycle: Seconds after which idle connections are recycled (PostgreSQL QueuePool).
        pool_pre_ping: Whether to emit lightweight SELECT 1 heartbeat before checkout.

    Returns:
        Configured SQLAlchemy Engine.
    """
    raw_url = url or settings.get_database_url()
    db_url = normalize_database_url(raw_url)

    is_sqlite = "sqlite" in db_url
    should_echo = echo if echo is not None else (settings.DB_ECHO and settings.is_development)

    if is_sqlite:
        connect_args = {"check_same_thread": False}
        kwargs: Dict[str, Any] = {
            "connect_args": connect_args,
            "echo": should_echo,
        }
        # In-memory SQLite requires StaticPool to preserve tables across connections
        if ":memory:" in db_url:
            kwargs["poolclass"] = pool.StaticPool

        return create_engine(db_url, **kwargs)

    # PostgreSQL configuration
    # Verify driver availability
    if "psycopg" in db_url:
        try:
            import psycopg  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "PostgreSQL driver 'psycopg' (v3) is not installed. "
                "Please install dependencies with: pip install 'psycopg[binary]>=3.2.0'"
            )

    ps = pool_size if pool_size is not None else settings.DB_POOL_SIZE
    mo = max_overflow if max_overflow is not None else settings.DB_MAX_OVERFLOW
    pt = pool_timeout if pool_timeout is not None else settings.DB_POOL_TIMEOUT
    pr = pool_recycle if pool_recycle is not None else settings.DB_POOL_RECYCLE
    ping = pool_pre_ping if pool_pre_ping is not None else settings.DB_POOL_PRE_PING

    masked_url = mask_database_url(db_url)
    logger.info(
        f"Configuring PostgreSQL QueuePool for {masked_url} "
        f"(pool_size={ps}, max_overflow={mo}, timeout={pt}s, recycle={pr}s, pre_ping={ping})"
    )

    return create_engine(
        db_url,
        pool_size=ps,
        max_overflow=mo,
        pool_timeout=pt,
        pool_recycle=pr,
        pool_pre_ping=ping,
        echo=should_echo,
    )


def get_connection_budget(worker_count: int = 1) -> Dict[str, int]:
    """Calculate the connection budget across multiple worker processes.

    Formula:
        steady_state = worker_count * DB_POOL_SIZE
        max_burst = worker_count * (DB_POOL_SIZE + DB_MAX_OVERFLOW)
    """
    if worker_count < 1:
        raise ValueError("worker_count must be at least 1")
    pool_size = settings.DB_POOL_SIZE
    max_overflow = settings.DB_MAX_OVERFLOW
    return {
        "worker_count": worker_count,
        "pool_size_per_worker": pool_size,
        "max_overflow_per_worker": max_overflow,
        "steady_state_connections": worker_count * pool_size,
        "max_burst_connections": worker_count * (pool_size + max_overflow),
    }


def dispose_engine():
    """Dispose the active connection pool.

    Multi-process / worker safety:
    Ensures inherited socket descriptors are not shared across process forks.
    Call on application shutdown or worker initialization.
    """
    engine.dispose(close=False)


# Initialize global database URL, engine, session factory, and declarative base
DATABASE_URL = settings.get_database_url()
engine = create_app_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a database session with automatic transaction cleanup."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
