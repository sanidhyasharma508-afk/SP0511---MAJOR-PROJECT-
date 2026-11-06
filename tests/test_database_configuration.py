"""
Automated tests for Dual-Engine Database Configuration & Cross-Platform Driver Setup (Task 19B).

Tests:
1. SQLite default configuration.
2. SQLite file-based configuration.
3. SQLite in-memory test configuration (StaticPool).
4. PostgreSQL URL parsing, normalization, and credential masking.
5. PostgreSQL engine configuration (QueuePool).
6. Connection pool settings and pool sizing.
7. Environment variable overrides for pool settings.
8. Invalid database URL handling and error reporting without credential leaks.
9. Missing PostgreSQL driver handling.
10. Session creation and transaction rollback on error.
11. Multi-worker connection budget formula and engine disposal.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import StaticPool, QueuePool

from backend.core.config import (
    Settings,
    Environment,
    normalize_database_url,
    mask_database_url,
)
from backend.database import (
    create_app_engine,
    get_connection_budget,
    dispose_engine,
    get_db,
    SessionLocal,
)


def test_sqlite_default_configuration():
    """Verify default SQLite configuration resolves to the application database path."""
    assert Settings.model_fields["DATABASE_URL"].default == "sqlite:///./campus_automation.db"
    cfg = Settings(ENV="development", DATABASE_URL="sqlite:///./campus_automation.db")
    assert cfg.DATABASE_URL == "sqlite:///./campus_automation.db"
    resolved = cfg.get_database_url()
    assert resolved.startswith("sqlite:///")
    assert resolved.endswith("campus_automation.db")

    engine = create_app_engine(resolved)
    assert engine.dialect.name == "sqlite"
    assert engine.dialect.driver == "pysqlite"
    engine.dispose()


def test_sqlite_file_based_configuration(tmp_path):
    """Verify arbitrary file-based SQLite database paths configure properly."""
    custom_db = tmp_path / "custom_test.db"
    url = f"sqlite:///{custom_db.as_posix()}"
    engine = create_app_engine(url)
    assert engine.dialect.name == "sqlite"

    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE test_tab (id INTEGER PRIMARY KEY, val TEXT);"))
        conn.execute(text("INSERT INTO test_tab (val) VALUES ('marvel');"))
        res = conn.execute(text("SELECT val FROM test_tab;")).scalar()
        assert res == "marvel"
    engine.dispose()


def test_sqlite_in_memory_configuration():
    """Verify in-memory SQLite uses StaticPool to share state across connections."""
    url = "sqlite:///:memory:"
    engine = create_app_engine(url)
    assert engine.dialect.name == "sqlite"
    assert isinstance(engine.pool, StaticPool)

    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE memory_tab (id INTEGER PRIMARY KEY, name TEXT);"))
        conn.execute(text("INSERT INTO memory_tab (name) VALUES ('shared_state');"))
        conn.commit()

    # Second connection must see data created in the first connection due to StaticPool
    with engine.connect() as conn2:
        val = conn2.execute(text("SELECT name FROM memory_tab;")).scalar()
        assert val == "shared_state"
    engine.dispose()


def test_postgresql_url_parsing():
    """Verify PostgreSQL URL parsing, scheme normalization, and password masking."""
    # Bare postgresql:// should normalize to modern psycopg v3
    norm1 = normalize_database_url("postgresql://user:secret123@localhost:5432/campus_db")
    assert norm1.startswith("postgresql+psycopg://")
    assert "user:secret123@localhost:5432/campus_db" in norm1

    # Legacy postgres:// should normalize to postgresql+psycopg://
    norm2 = normalize_database_url("postgres://admin:topsecret@db.internal:5432/marvel_db")
    assert norm2.startswith("postgresql+psycopg://")
    assert "admin:topsecret@db.internal:5432/marvel_db" in norm2

    # Explicit drivers should be preserved
    norm3 = normalize_database_url("postgresql+psycopg://alice:pass@host/db")
    assert norm3 == "postgresql+psycopg://alice:pass@host/db"

    # Password masking verification
    masked = mask_database_url("postgresql://alice:super_secret_pw@localhost:5432/campus")
    assert "super_secret_pw" not in masked
    assert "***" in masked
    assert "alice" in masked
    assert "campus" in masked


def test_postgresql_engine_configuration():
    """Verify PostgreSQL engine is configured with QueuePool and Psycopg 3 dialect."""
    url = "postgresql+psycopg://user:pass@localhost:5432/campus_db"
    engine = create_app_engine(url)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    assert isinstance(engine.pool, QueuePool)
    engine.dispose()


def test_connection_pool_settings():
    """Verify connection pool sizing, overflow, timeouts, recycle, and pre_ping."""
    url = "postgresql+psycopg://user:pass@localhost:5432/campus_db"
    engine = create_app_engine(
        url,
        pool_size=12,
        max_overflow=24,
        pool_timeout=45,
        pool_recycle=900,
        pool_pre_ping=True,
    )
    assert engine.pool.size() == 12
    assert engine.pool._max_overflow == 24
    assert engine.pool._timeout == 45
    assert engine.pool._recycle == 900
    assert engine.pool._pre_ping is True
    engine.dispose()


def test_connection_budget_calculation():
    """Verify multi-worker connection budget formula."""
    budget = get_connection_budget(worker_count=4)
    assert budget["worker_count"] == 4
    assert budget["steady_state_connections"] == 4 * budget["pool_size_per_worker"]
    assert budget["max_burst_connections"] == 4 * (
        budget["pool_size_per_worker"] + budget["max_overflow_per_worker"]
    )

    with pytest.raises(ValueError, match="worker_count must be at least 1"):
        get_connection_budget(worker_count=0)


def test_environment_variable_overrides(monkeypatch):
    """Verify database configuration environment variable overrides."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://app_user:db_pass@10.0.0.5:5432/marvel_prod")
    monkeypatch.setenv("DB_POOL_SIZE", "8")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "16")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "40")
    monkeypatch.setenv("DB_POOL_RECYCLE", "2400")
    monkeypatch.setenv("DB_POOL_PRE_PING", "false")

    cfg = Settings()
    assert cfg.DB_POOL_SIZE == 8
    assert cfg.DB_MAX_OVERFLOW == 16
    assert cfg.DB_POOL_TIMEOUT == 40
    assert cfg.DB_POOL_RECYCLE == 2400
    assert cfg.DB_POOL_PRE_PING is False

    # Check normalized output
    norm = cfg.get_normalized_database_url()
    assert norm.startswith("postgresql+psycopg://app_user:db_pass@10.0.0.5:5432/marvel_prod")

    # Check masked output
    masked = cfg.get_masked_database_url()
    assert "db_pass" not in masked
    assert "***" in masked


def test_pool_validators():
    """Verify validation on invalid pool configuration values."""
    with pytest.raises(ValueError, match="DB_POOL_SIZE must be greater than or equal to 1"):
        Settings(DB_POOL_SIZE=0)

    with pytest.raises(ValueError, match="DB_MAX_OVERFLOW must be greater than or equal to 0"):
        Settings(DB_MAX_OVERFLOW=-1)

    with pytest.raises(ValueError, match="DB_POOL_TIMEOUT must be greater than or equal to 1"):
        Settings(DB_POOL_TIMEOUT=0)

    with pytest.raises(ValueError, match="DB_POOL_RECYCLE must be greater than or equal to 1"):
        Settings(DB_POOL_RECYCLE=0)


def test_invalid_database_url_handling():
    """Verify invalid database URLs are rejected without leaking passwords."""
    with pytest.raises(ValueError, match="DATABASE_URL must be a non-empty string"):
        normalize_database_url("")

    with pytest.raises(ValueError, match="Invalid database URL format"):
        normalize_database_url("not_a_valid_url")

    with pytest.raises(ValueError, match="Unsupported database dialect 'mysql'"):
        normalize_database_url("mysql://root:secret_sql_password@localhost:3306/db")

    # Verify secret is NOT leaked in dialect error
    try:
        normalize_database_url("oracle://admin:confidential_pw@localhost/xe")
    except ValueError as e:
        assert "confidential_pw" not in str(e)

    with pytest.raises(ValueError, match="Invalid PostgreSQL connection URL"):
        normalize_database_url("postgresql://")


def test_missing_postgresql_driver_handling():
    """Verify informative RuntimeError when driver is missing."""
    url = "postgresql+psycopg://user:pass@localhost:5432/db"
    with patch.dict(sys.modules, {"psycopg": None}):
        with pytest.raises(RuntimeError, match="PostgreSQL driver 'psycopg'.*is not installed"):
            create_app_engine(url)


def test_session_lifecycle_and_rollback():
    """Verify get_db session dependency lifecycle and automatic rollback on error."""
    # Test normal lifecycle
    gen = get_db()
    session = next(gen)
    assert session is not None
    assert session.is_active
    try:
        next(gen)
    except StopIteration:
        pass  # Clean shutdown

    # Test rollback on exception
    mock_session = MagicMock()
    with patch("backend.database.SessionLocal", return_value=mock_session):
        gen = get_db()
        sess = next(gen)
        with pytest.raises(ZeroDivisionError):
            try:
                raise ZeroDivisionError("Simulated application route crash")
            except Exception as exc:
                gen.throw(exc)
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


def test_dispose_engine():
    """Verify dispose_engine executes without error for multi-process safety."""
    dispose_engine()
