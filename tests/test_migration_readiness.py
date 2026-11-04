"""Automated Test Suite for Task 18E: Migration Readiness, Schema Drift Protection, and Startup Verification.

Verifies the 14 core database migration readiness requirements:
1. Fresh empty database detected as unmigrated; startup refuses to proceed.
2. Correct baseline-migrated database passes readiness; startup proceeds.
3. Compatible but unstamped legacy database detected; warning emitted; startup proceeds.
4. Database missing required table fails readiness; startup refuses to proceed.
5. Database missing required column fails readiness; startup refuses to proceed.
6. Database with incompatible column type fails readiness; startup refuses to proceed.
7. Database missing foreign key fails readiness; startup refuses to proceed.
8. Database missing unique constraint fails readiness; startup refuses to proceed.
9. Database missing important index fails readiness; startup refuses to proceed.
10. Database with unknown Alembic revision fails readiness; startup refuses to proceed.
11. Verifier execution causes zero DDL operations.
12. Verifier execution does not stamp or migrate the database.
13. Existing application startup behavior preserved for valid databases.
14. Existing authentication and authorization regression verification.
"""

import asyncio
import hashlib
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch
import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic.config import Config
from alembic import command
from backend.database import Base
import backend.models
from backend.core.database_verifier import (
    DatabaseVerifier,
    DatabaseReadinessStatus,
    KNOWN_REVISIONS,
)
from backend.main import startup_event
from backend.core.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.models.user import User


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide an isolated temporary SQLite database path."""
    return tmp_path / "readiness_test.db"


@pytest.fixture
def alembic_cfg(repo_root, temp_db_path):
    """Provide an Alembic Config pointing to the temporary SQLite database."""
    ini_path = str(repo_root / "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{temp_db_path.as_posix()}")
    return cfg


def test_1_fresh_empty_database_detected_as_unmigrated_startup_refuses(temp_db_path):
    """Test 1: Fresh empty database detected as unmigrated; startup refuses to proceed."""
    # Create empty database
    conn = sqlite3.connect(temp_db_path)
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.FRESH
    assert readiness.can_start is False
    assert "alembic upgrade head" in readiness.action_required
    assert len(readiness.missing_tables) == 22

    # Verify startup_event refuses to proceed
    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "fresh database detected" in str(exc_info.value) or "alembic upgrade head" in str(exc_info.value)

    engine.dispose()


def test_2_correct_baseline_migrated_database_passes_readiness_startup_proceeds(alembic_cfg, temp_db_path):
    """Test 2: Correct baseline-migrated database passes readiness; startup proceeds."""
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.MIGRATED
    assert readiness.can_start is True
    assert readiness.revision == "0001_initial_baseline"
    assert len(readiness.missing_tables) == 0
    assert len(readiness.missing_columns) == 0
    assert len(readiness.type_mismatches) == 0
    assert len(readiness.missing_pks) == 0
    assert len(readiness.missing_fks) == 0
    assert len(readiness.missing_unique_constraints) == 0
    assert len(readiness.missing_indexes) == 0

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        # Startup must proceed cleanly without raising
        asyncio.run(startup_event())

    engine.dispose()


def test_3_compatible_unstamped_legacy_database_warning_emitted_startup_proceeds(temp_db_path):
    """Test 3: Compatible but unstamped legacy database detected; warning emitted; startup proceeds."""
    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    Base.metadata.create_all(bind=engine)

    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.COMPATIBLE_UNSTAMPED
    assert readiness.can_start is True
    assert readiness.revision is None
    assert "alembic stamp 0001_initial_baseline" in readiness.action_required

    import backend.main
    TestingSession = sessionmaker(bind=engine)
    with patch.object(backend.main.logger, "log_event") as mock_log:
        with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
            asyncio.run(startup_event())

        notice_calls = [c for c in mock_log.call_args_list if c.args and c.args[0] == "database_readiness_notice"]
        assert len(notice_calls) == 1, "Expected database_readiness_notice event to be logged"
        assert notice_calls[0].kwargs.get("level") == "WARNING"
        assert "alembic stamp 0001_initial_baseline" in notice_calls[0].kwargs.get("action_required", "")

    engine.dispose()


def test_4_database_missing_required_table_fails_readiness_startup_refuses(alembic_cfg, temp_db_path):
    """Test 4: Database missing required table fails readiness; startup refuses to proceed."""
    command.upgrade(alembic_cfg, "head")

    # Drop required domain table
    conn = sqlite3.connect(temp_db_path)
    conn.execute("DROP TABLE events;")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.INCOMPATIBLE
    assert readiness.can_start is False
    assert "events" in readiness.missing_tables

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "events" in str(exc_info.value)

    engine.dispose()


def test_5_database_missing_required_column_fails_readiness_startup_refuses(alembic_cfg, temp_db_path):
    """Test 5: Database missing required column fails readiness; startup refuses to proceed."""
    command.upgrade(alembic_cfg, "head")

    # Recreate users table without 'role' column
    conn = sqlite3.connect(temp_db_path)
    conn.execute("CREATE TABLE users_temp AS SELECT id, username, email, hashed_password, full_name, avatar, is_active, linked_student_id, created_at, updated_at, last_login FROM users;")
    conn.execute("DROP TABLE users;")
    conn.execute("ALTER TABLE users_temp RENAME TO users;")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.INCOMPATIBLE
    assert readiness.can_start is False
    assert "users" in readiness.missing_columns
    assert "role" in readiness.missing_columns["users"]

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "missing columns" in str(exc_info.value)

    engine.dispose()


def test_6_database_with_incompatible_column_type_fails_readiness_startup_refuses(alembic_cfg, temp_db_path):
    """Test 6: Database with incompatible column type fails readiness; startup refuses to proceed."""
    command.upgrade(alembic_cfg, "head")

    # Recreate users table with incompatible column type (INTEGER for role)
    conn = sqlite3.connect(temp_db_path)
    conn.execute("""
        CREATE TABLE users_temp (
            id INTEGER PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            username VARCHAR(100) NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            role INTEGER NOT NULL,
            is_active BOOLEAN,
            is_verified BOOLEAN,
            created_at DATETIME,
            updated_at DATETIME
        );
    """)
    conn.execute("DROP TABLE users;")
    conn.execute("ALTER TABLE users_temp RENAME TO users;")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.INCOMPATIBLE
    assert readiness.can_start is False
    assert any(m["table"] == "users" and m["column"] == "role" for m in readiness.type_mismatches)

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "type mismatches" in str(exc_info.value)

    engine.dispose()


def test_7_database_missing_foreign_key_fails_readiness_startup_refuses(alembic_cfg, temp_db_path):
    """Test 7: Database missing foreign key fails readiness; startup refuses to proceed."""
    command.upgrade(alembic_cfg, "head")

    # Recreate complaints table without Foreign Key constraint on student_id
    conn = sqlite3.connect(temp_db_path)
    conn.execute("""
        CREATE TABLE complaints_temp (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            title VARCHAR NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            priority VARCHAR NOT NULL,
            resolution_notes TEXT,
            assigned_to INTEGER,
            created_at DATETIME,
            updated_at DATETIME
        );
    """)
    conn.execute("DROP TABLE complaints;")
    conn.execute("ALTER TABLE complaints_temp RENAME TO complaints;")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.INCOMPATIBLE
    assert readiness.can_start is False
    assert "complaints" in readiness.missing_fks

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "missing FKs" in str(exc_info.value)

    engine.dispose()


def test_8_database_missing_unique_constraint_fails_readiness_startup_refuses(alembic_cfg, temp_db_path):
    """Test 8: Database missing unique constraint fails readiness; startup refuses to proceed."""
    command.upgrade(alembic_cfg, "head")

    # Recreate students table without UNIQUE(roll_no)
    conn = sqlite3.connect(temp_db_path)
    conn.execute("""
        CREATE TABLE students_temp (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            roll_no VARCHAR NOT NULL,
            department VARCHAR NOT NULL,
            semester INTEGER,
            section VARCHAR
        );
    """)
    conn.execute("DROP TABLE students;")
    conn.execute("ALTER TABLE students_temp RENAME TO students;")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.INCOMPATIBLE
    assert readiness.can_start is False
    assert "students" in readiness.missing_unique_constraints

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "unique" in str(exc_info.value).lower()

    engine.dispose()


def test_9_database_missing_important_index_fails_readiness_startup_refuses(alembic_cfg, temp_db_path):
    """Test 9: Database missing important index fails readiness; startup refuses to proceed."""
    command.upgrade(alembic_cfg, "head")

    # Drop important model index on events (ix_events_name)
    conn = sqlite3.connect(temp_db_path)
    conn.execute("DROP INDEX ix_events_name;")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.INCOMPATIBLE
    assert readiness.can_start is False
    assert "events" in readiness.missing_indexes

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "indexes" in str(exc_info.value) or "events" in str(exc_info.value)

    engine.dispose()


def test_10_database_with_unknown_alembic_revision_fails_readiness_startup_refuses(alembic_cfg, temp_db_path):
    """Test 10: Database with unknown Alembic revision fails readiness; startup refuses to proceed."""
    command.upgrade(alembic_cfg, "head")

    # Overwrite alembic revision with unknown identifier
    conn = sqlite3.connect(temp_db_path)
    conn.execute("UPDATE alembic_version SET version_num = '9999_unknown_future_rev';")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)
    readiness = verifier.check_readiness()

    assert readiness.status == DatabaseReadinessStatus.UNKNOWN_REVISION
    assert readiness.can_start is False
    assert readiness.revision == "9999_unknown_future_rev"
    assert "Expected recognized revisions" in readiness.action_required

    TestingSession = sessionmaker(bind=engine)
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())
        assert "unknown or inconsistent Alembic revision" in str(exc_info.value)

    engine.dispose()


def test_11_verifier_execution_causes_zero_ddl_operations(alembic_cfg, temp_db_path):
    """Test 11: Verifier execution causes zero DDL operations."""
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    schema_before = cursor.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name;").fetchall()
    conn.close()

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    verifier = DatabaseVerifier(engine)

    # Execute check_readiness and verify_schema repeatedly
    for _ in range(5):
        _ = verifier.check_readiness()
        _ = verifier.verify_schema()

    engine.dispose()

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    schema_after = cursor.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name;").fetchall()
    conn.close()

    assert schema_before == schema_after


def test_12_verifier_execution_does_not_stamp_or_migrate_database(temp_db_path):
    """Test 12: Verifier execution does not stamp or migrate the database."""
    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    Base.metadata.create_all(bind=engine)

    conn = sqlite3.connect(temp_db_path)
    tables_before = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    conn.close()
    assert "alembic_version" not in tables_before

    verifier = DatabaseVerifier(engine)
    for _ in range(3):
        readiness = verifier.check_readiness()
        assert readiness.status == DatabaseReadinessStatus.COMPATIBLE_UNSTAMPED

    conn = sqlite3.connect(temp_db_path)
    tables_after = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    conn.close()

    assert "alembic_version" not in tables_after
    assert tables_before == tables_after
    engine.dispose()


def test_13_existing_application_startup_behavior_preserved_for_valid_databases(alembic_cfg, temp_db_path):
    """Test 13: Existing application startup behavior preserved for valid databases."""
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    TestingSession = sessionmaker(bind=engine)

    # First startup provisions default accounts
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        asyncio.run(startup_event())

    session = TestingSession()
    users = session.query(User).all()
    assert len(users) >= 3
    emails = {u.email for u in users}
    assert "admin@campus.edu" in emails
    session.close()

    # Second startup is idempotent and succeeds without error
    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        asyncio.run(startup_event())

    session = TestingSession()
    assert session.query(User).count() == len(users)
    session.close()
    engine.dispose()


def test_14_existing_auth_and_authorization_regression_verification(alembic_cfg, temp_db_path):
    """Test 14: Existing authentication and authorization regression verification."""
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    TestingSession = sessionmaker(bind=engine)

    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        asyncio.run(startup_event())

    session = TestingSession()
    admin = session.query(User).filter_by(email="admin@campus.edu").first()
    assert admin is not None
    assert verify_password("admin123", admin.hashed_password)

    token = create_access_token(
        user_id=admin.id,
        username=admin.username,
        role=admin.role,
        email=admin.email,
    )
    payload = decode_token(token)
    assert payload is not None
    assert payload.sub == admin.username
    assert payload.role == "admin"
    assert payload.email == "admin@campus.edu"

    session.close()
    engine.dispose()
