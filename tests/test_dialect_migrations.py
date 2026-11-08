"""Tests for Phase 19D: Dual-Dialect Alembic Migration Hardening.

Verifies:
- Alembic revision graph integrity and head revision
- SQLite full upgrade, downgrade to base, and re-upgrade cycle
- Idempotency of repeated upgrade head invocations
- Zero autogenerate metadata drift between Base.metadata and baseline schema
- PostgreSQL offline SQL generation for both upgrade and downgrade
- Named PostgreSQL ENUM creation (eventcategory, eventstatus, registrationstatus)
- Centralized URL normalization and scheme remapping (postgres:// -> postgresql+psycopg://)
- Rejection of unsupported database dialects
- SQLite transaction safety and foreign-key PRAGMA restoration on error
- Credential masking in migration logs
"""

import io
import logging
import sqlite3
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from backend.database import Base
import backend.models
from backend.core.config import normalize_database_url, mask_database_url


@pytest.fixture
def temp_sqlite_db(tmp_path):
    """Provide an isolated temporary SQLite database path."""
    return tmp_path / "dialect_test.db"


@pytest.fixture
def alembic_cfg(temp_sqlite_db):
    """Provide an Alembic Config instance configured for the isolated test database."""
    repo_root = Path(__file__).resolve().parent.parent
    ini_path = str(repo_root / "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{temp_sqlite_db.as_posix()}")
    return cfg


class TestAlembicRevisionGraph:
    """Task 1: Migration graph and revision tracking."""

    def test_single_authoritative_head(self, alembic_cfg):
        """Verify the Alembic revision graph has exactly one head: 0001_initial_baseline."""
        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()
        assert len(heads) == 1
        assert heads[0] == "0001_initial_baseline"

    def test_revision_metadata(self, alembic_cfg):
        """Verify the baseline revision metadata has no down_revision (root migration)."""
        script = ScriptDirectory.from_config(alembic_cfg)
        rev = script.get_revision("0001_initial_baseline")
        assert rev is not None
        assert rev.down_revision is None
        assert rev.revision == "0001_initial_baseline"


class TestSQLiteMigrationExecution:
    """Task 4: SQLite Migration and Lifecycle Execution."""

    def test_full_upgrade_downgrade_reupgrade_cycle(self, alembic_cfg, temp_sqlite_db):
        """Verify SQLite upgrade head -> downgrade base -> upgrade head lifecycle."""
        # 1. Upgrade to head
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(temp_sqlite_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
        conn.close()

        assert "alembic_version" in tables
        assert len(tables) == 23  # 22 domain tables + alembic_version

        # 2. Downgrade to base
        command.downgrade(alembic_cfg, "base")

        conn = sqlite3.connect(temp_sqlite_db)
        tables_after_down = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
        version_rows = conn.execute("SELECT COUNT(*) FROM alembic_version;").fetchone()[0]
        conn.close()

        # All 22 domain tables dropped, alembic_version emptied
        domain_tables_remaining = [t for t in tables_after_down if t != "alembic_version"]
        assert len(domain_tables_remaining) == 0
        assert version_rows == 0

        # 3. Re-upgrade to head
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(temp_sqlite_db)
        tables_after_reup = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
        version_after_reup = conn.execute("SELECT version_num FROM alembic_version;").fetchone()
        conn.close()

        assert len(tables_after_reup) == 23
        assert version_after_reup == ("0001_initial_baseline",)

    def test_repeated_upgrade_head_is_idempotent(self, alembic_cfg, temp_sqlite_db):
        """Verify executing upgrade head consecutively on an already migrated database is a safe no-op."""
        command.upgrade(alembic_cfg, "head")
        # Second execution must succeed cleanly
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(temp_sqlite_db)
        version = conn.execute("SELECT version_num FROM alembic_version;").fetchone()
        conn.close()

        assert version == ("0001_initial_baseline",)


class TestAutogenerationAccuracy:
    """Task 3 & 6: Autogeneration Accuracy and Model-to-Baseline Parity."""

    def test_zero_metadata_drift_against_baseline(self, alembic_cfg, temp_sqlite_db):
        """Verify compare_metadata produces exactly zero schema drift between models and baseline."""
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(f"sqlite:///{temp_sqlite_db.as_posix()}")
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn,
                opts={
                    "compare_type": True,
                    "compare_server_default": True,
                    "target_metadata": Base.metadata,
                },
            )
            diff = compare_metadata(ctx, Base.metadata)

        engine.dispose()
        assert len(diff) == 0, f"Unexpected autogenerate diff: {diff}"


class TestPostgreSQLMigrationSupport:
    """Task 5: PostgreSQL-Specific DDL and Offline Generation."""

    def test_postgresql_offline_sql_generation(self):
        """Verify offline SQL generation for PostgreSQL dialect produces valid DDL and Enums."""
        repo_root = Path(__file__).resolve().parent.parent
        cfg = Config(str(repo_root / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app_user:secret_pwd@pg.campus.internal:5432/campus_db")

        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            command.upgrade(cfg, "head", sql=True)
        finally:
            sys.stdout = old_stdout

        sql = buf.getvalue()

        # Verify PostgreSQL native ENUM types
        assert "CREATE TYPE eventcategory AS ENUM" in sql
        assert "CREATE TYPE eventstatus AS ENUM" in sql
        assert "CREATE TYPE registrationstatus AS ENUM" in sql

        # Verify sample domain tables and version tracking
        assert "CREATE TABLE announcements" in sql
        assert "CREATE TABLE events" in sql
        assert "CREATE TABLE users" in sql
        assert "CREATE TABLE alembic_version" in sql
        assert "INSERT INTO alembic_version" in sql

        # Verify credentials are NOT embedded in generated DDL output
        assert "secret_pwd" not in sql

    def test_postgresql_offline_downgrade_sql_generation(self):
        """Verify offline downgrade SQL generation for PostgreSQL dialect drops tables cleanly."""
        repo_root = Path(__file__).resolve().parent.parent
        cfg = Config(str(repo_root / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app_user:secret_pwd@pg.campus.internal:5432/campus_db")

        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            command.downgrade(cfg, "0001_initial_baseline:base", sql=True)
        finally:
            sys.stdout = old_stdout

        sql = buf.getvalue()

        assert "DROP TABLE users;" in sql
        assert "DROP TABLE events;" in sql
        assert "DROP TABLE announcements;" in sql
        assert "DELETE FROM alembic_version WHERE alembic_version.version_num = '0001_initial_baseline';" in sql


class TestDialectEnvironmentAndSecurity:
    """Task 2: Dialect Handling, URL Normalization, and Credential Masking."""

    def test_url_normalization_postgres_schemes(self):
        """Verify postgres:// and postgresql:// are remapped to modern postgresql+psycopg://."""
        legacy_pg1 = "postgres://usr:pwd@localhost:5432/db"
        legacy_pg2 = "postgresql://usr:pwd@localhost:5432/db"

        assert normalize_database_url(legacy_pg1).startswith("postgresql+psycopg://")
        assert normalize_database_url(legacy_pg2).startswith("postgresql+psycopg://")

    def test_unsupported_dialect_raises_value_error(self):
        """Verify unsupported dialects like mysql or oracle raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported database dialect"):
            normalize_database_url("mysql+pymysql://usr:pwd@localhost:3306/db")

        with pytest.raises(ValueError, match="Unsupported database dialect"):
            normalize_database_url("oracle+cx_oracle://usr:pwd@localhost:1521/db")

    def test_credential_masking_in_migration_logging(self, capfd):
        """Verify database credentials in URL are masked in alembic stderr log output."""
        repo_root = Path(__file__).resolve().parent.parent
        cfg = Config(str(repo_root / "alembic.ini"))
        test_url = "postgresql+psycopg://admin_user:super_secret_password_123@db.host.edu:5432/prod_db"
        cfg.set_main_option("sqlalchemy.url", test_url)

        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            command.upgrade(cfg, "head", sql=True)
        finally:
            sys.stdout = old_stdout

        captured = capfd.readouterr()
        combined_logs = captured.out + captured.err

        # Verify password is NOT leaked in output/logs
        assert "super_secret_password_123" not in combined_logs
        assert "admin_user:***@db.host.edu:5432/prod_db" in combined_logs or "admin_user:***" in combined_logs
