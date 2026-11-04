"""Automated Test Suite for Task 18D: Alembic Schema Ownership.

Verifies that:
1. Importing the application does not create domain tables.
2. Application startup does not call Base.metadata.create_all().
3. Application startup does not invoke procedural schema creation (ensure_schema).
4. Seed routines do not create tables on unmigrated databases.
5. Seed routines remain idempotent across repeated executions.
6. Application startup against a correctly migrated database succeeds cleanly.
7. Application startup against a database missing required tables fails clearly with RuntimeError.
8. Existing SQLAlchemy ORM queries continue working.
9. Existing authentication and authorization routines remain functional.
10. DatabaseVerifier and baseline migration contracts remain enforced.
"""

import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.main import startup_event
from backend.models.user import User
from backend.models.student import Student
from backend.models.club import Club
from backend.core.auth import create_access_token, decode_token, hash_password, verify_password
from backend.seed_data import seed_default_users, seed_database, ensure_schema
from backend.core.database_verifier import DatabaseVerifier


def test_1_importing_application_does_not_create_domain_tables(tmp_path):
    """Test 1: Verify that importing backend.main in a fresh process does not create domain tables."""
    test_db = tmp_path / "fresh_import_test.db"
    test_db_url = f"sqlite:///{test_db.as_posix()}"

    # Run in a clean subprocess to test module-level side effects on import
    code = (
        "import os\n"
        "import sys\n"
        "import sqlite3\n"
        "os.environ['DATABASE_URL'] = sys.argv[1]\n"
        "import backend.main\n"
        "conn = sqlite3.connect(sys.argv[2])\n"
        "tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';\").fetchall()]\n"
        "conn.close()\n"
        "print(f'TABLE_COUNT:{len(tables)}')\n"
    )

    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    result = subprocess.run(
        [sys.executable, "-c", code, test_db_url, str(test_db)],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, f"Subprocess failed: {result.stderr}"
    assert "TABLE_COUNT:0" in result.stdout, f"Expected 0 tables on import, stdout: {result.stdout}"


def test_2_startup_does_not_call_create_all(tmp_path):
    """Test 2: Verify that application startup event does not call Base.metadata.create_all."""
    test_db = tmp_path / "migrated_test_2.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    with patch.object(Base.metadata, "create_all") as mock_create_all:
        with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
            asyncio.run(startup_event())
            mock_create_all.assert_not_called()

    engine.dispose()


def test_3_startup_does_not_invoke_procedural_schema_creation(tmp_path):
    """Test 3: Verify that application startup does not call ensure_schema or procedural migrations."""
    test_db = tmp_path / "migrated_test_3.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    with patch("backend.seed_data.ensure_schema") as mock_ensure:
        with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
            asyncio.run(startup_event())
            mock_ensure.assert_not_called()

    # Also verify that calling ensure_schema() directly does not execute DDL
    with patch.object(Base.metadata, "create_all") as mock_create_all:
        ensure_schema()
        mock_create_all.assert_not_called()

    engine.dispose()


def test_4_seed_routines_do_not_create_tables(tmp_path):
    """Test 4: Verify that seed routines refuse to create tables on an unmigrated database."""
    test_db = tmp_path / "empty_for_seed.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}")
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    # 1. seed_default_users must raise RuntimeError and NOT create tables
    with pytest.raises(RuntimeError) as exc_info_users:
        seed_default_users(db)
    assert "users" in str(exc_info_users.value)
    assert "alembic upgrade head" in str(exc_info_users.value)

    # 2. seed_database must raise RuntimeError and NOT create tables
    with patch("backend.seed_data.engine", engine), patch("backend.seed_data.SessionLocal", TestingSession):
        with pytest.raises(RuntimeError) as exc_info_db:
            seed_database()
        assert "required tables are missing" in str(exc_info_db.value)
        assert "alembic upgrade head" in str(exc_info_db.value)

    db.close()
    engine.dispose()

    # Confirm 0 tables exist in the database
    conn = sqlite3.connect(test_db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()
    conn.close()
    assert len(tables) == 0, f"Expected 0 tables created by seed routines, found: {tables}"


def test_5_seed_routines_remain_idempotent(tmp_path):
    """Test 5: Verify that seed routines remain idempotent on a migrated database."""
    test_db = tmp_path / "idempotent_seed.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    # First seeding run for users
    seed_default_users(db)
    initial_user_count = db.query(User).count()
    assert initial_user_count == 4  # admin, staff1, student1, staff2

    # Second seeding run (must not duplicate users)
    seed_default_users(db)
    assert db.query(User).count() == initial_user_count

    # Third seeding run with seed_database
    with patch("backend.seed_data.engine", engine), patch("backend.seed_data.SessionLocal", TestingSession):
        seed_database()
        initial_student_count = db.query(Student).count()
        assert initial_student_count > 0

        # Re-running seed_database must not duplicate students or users
        seed_database()
        assert db.query(Student).count() == initial_student_count
        assert db.query(User).count() == initial_user_count

    db.close()
    engine.dispose()


def test_6_startup_against_correctly_migrated_database_works(tmp_path):
    """Test 6: Verify that application startup succeeds cleanly against a fully migrated database."""
    test_db = tmp_path / "valid_migrated.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    with patch("backend.main.engine", engine), patch("backend.database.SessionLocal", TestingSession):
        # Startup event should complete with zero errors
        asyncio.run(startup_event())

    # Verify that default users were populated
    db = TestingSession()
    assert db.query(User).count() == 4
    db.close()
    engine.dispose()


def test_7_startup_against_missing_tables_fails_clearly(tmp_path):
    """Test 7: Verify that application startup fails clearly when required tables are missing."""
    test_db = tmp_path / "missing_tables.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}")

    with patch("backend.main.engine", engine):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(startup_event())

        err_str = str(exc_info.value)
        assert "Database schema is incomplete: missing required tables" in err_str
        assert "alembic upgrade head" in err_str

    engine.dispose()


def test_8_existing_orm_queries_continue_working(tmp_path):
    """Test 8: Verify that SQLAlchemy ORM model queries, relations, and operations work normally."""
    test_db = tmp_path / "orm_work.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    # Seed default entities
    seed_default_users(db)

    # Test User query
    admin = db.query(User).filter(User.username == "admin").first()
    assert admin is not None
    assert admin.role == "admin"
    assert admin.is_active is True

    # Test Student creation and query
    s = Student(name="Jane Doe", roll_no="2026TEST01", department="CS", semester=1, section="A")
    db.add(s)
    db.commit()

    queried_s = db.query(Student).filter(Student.roll_no == "2026TEST01").first()
    assert queried_s is not None
    assert queried_s.name == "Jane Doe"

    # Test Club creation
    club = Club(
        name="Robotics Club",
        description="Tech Club",
        category="Technical",
        advisor="Dr. Tech Advisor",
    )
    db.add(club)
    db.commit()

    queried_club = db.query(Club).filter(Club.name == "Robotics Club").first()
    assert queried_club is not None
    assert queried_club.name == "Robotics Club"
    assert queried_club.advisor == "Dr. Tech Advisor"

    db.close()
    engine.dispose()


def test_9_existing_auth_and_security_behavior_unchanged():
    """Test 9: Verify that authentication and token creation/verification logic remains functional."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

    token = create_access_token(user_id=42, username="testadmin", role="admin")
    payload = decode_token(token)
    assert payload is not None
    assert payload.sub == "testadmin"
    assert payload.role == "admin"
    assert payload.user_id == 42


def test_10_database_verifier_rejects_unmigrated_and_approves_baseline(tmp_path):
    """Test 10: Verify DatabaseVerifier contract on unmigrated and migrated schemas."""
    # Unmigrated (empty) database
    empty_db = tmp_path / "verifier_empty.db"
    empty_engine = create_engine(f"sqlite:///{empty_db.as_posix()}")
    verifier_empty = DatabaseVerifier(empty_engine)
    report_empty = verifier_empty.verify_schema()
    empty_engine.dispose()

    assert report_empty.is_valid is False
    assert report_empty.can_stamp is False
    assert len(report_empty.missing_tables) == 22
    assert "Schema mismatch" in report_empty.summary

    # Fully migrated baseline database
    migrated_db = tmp_path / "verifier_migrated.db"
    migrated_engine = create_engine(f"sqlite:///{migrated_db.as_posix()}")
    Base.metadata.create_all(bind=migrated_engine)
    verifier_migrated = DatabaseVerifier(migrated_engine)
    report_migrated = verifier_migrated.verify_schema()
    migrated_engine.dispose()

    assert report_migrated.is_valid is True
    assert report_migrated.can_stamp is True
    assert len(report_migrated.missing_tables) == 0
    assert report_migrated.integrity_status == "ok"
