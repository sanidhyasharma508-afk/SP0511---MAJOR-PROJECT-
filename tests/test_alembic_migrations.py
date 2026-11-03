"""Tests for Alembic migration framework, baseline revision, verification, and backups."""

import os
import sys
import tempfile
import sqlite3
import io
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect

from alembic.config import Config
from alembic import command
from backend.database import Base
import backend.models
from backend.core.database_verifier import DatabaseVerifier
from backend.core.backup_utils import backup_sqlite_database, restore_sqlite_database, BackupError


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a path to a temporary SQLite database outside application data paths."""
    db_file = tmp_path / "test_migration.db"
    return db_file


@pytest.fixture
def alembic_cfg(temp_db_path):
    """Provide an Alembic Config pointing to the temporary SQLite database."""
    repo_root = Path(__file__).resolve().parent.parent
    ini_path = str(repo_root / "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{temp_db_path.as_posix()}")
    return cfg


def test_1_alembic_configuration_loading(alembic_cfg):
    """Test 1: Verify alembic.ini loads and resolves script location and settings."""
    assert alembic_cfg.get_main_option("script_location") is not None
    assert "alembic" in alembic_cfg.get_main_option("script_location")
    assert alembic_cfg.get_main_option("sqlalchemy.url").startswith("sqlite:///")


def test_2_model_metadata_registration():
    """Test 2: Verify all 22 domain models are registered in Base.metadata."""
    tables = Base.metadata.tables.keys()
    assert len(tables) == 22
    expected = [
        "announcements", "attendance", "club_activities", "club_attendance",
        "club_members", "clubs", "complaint_history", "complaints",
        "device_fingerprints", "event_announcements", "event_leaderboard",
        "event_registrations", "events", "qr_attendance_logs", "qr_attendance_records",
        "qr_attendance_sessions", "risk_logs", "schedule_feedback", "schedules",
        "students", "study_tasks", "users"
    ]
    for exp in expected:
        assert exp in tables, f"Expected table {exp} missing from Base.metadata"


def test_3_fresh_database_baseline_upgrade(alembic_cfg, temp_db_path):
    """Test 3: Verify alembic upgrade head on a clean database creates all tables."""
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    conn.close()

    assert "alembic_version" in tables
    assert len(tables) == 23  # 22 domain tables + alembic_version


def test_4_correct_alembic_version_revision(alembic_cfg, temp_db_path):
    """Test 4: Verify alembic_version contains '0001_initial_baseline'."""
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    version = cursor.execute("SELECT version_num FROM alembic_version;").fetchone()
    conn.close()

    assert version is not None
    assert version[0] == "0001_initial_baseline"


def test_5_foreign_key_integrity(alembic_cfg, temp_db_path):
    """Test 5: Verify PRAGMA foreign_key_check and PRAGMA integrity_check pass on upgraded DB."""
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    fk_violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    integrity = cursor.execute("PRAGMA integrity_check;").fetchall()
    conn.close()

    assert len(fk_violations) == 0
    assert integrity == [("ok",)]


def test_6_unique_constraint_preservation(alembic_cfg, temp_db_path):
    """Test 6: Verify key unique constraints and composite uniques exist."""
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(f"sqlite:///{temp_db_path.as_posix()}")
    inspector = inspect(engine)

    # QR attendance unique constraint on session_id, roll_number
    qr_uniques = inspector.get_unique_constraints("qr_attendance_records")
    qr_unique_cols = [set(u["column_names"]) for u in qr_uniques]
    assert {"session_id", "roll_number"} in qr_unique_cols

    # Student unique roll_no
    student_uniques = inspector.get_unique_constraints("students")
    student_unique_cols = [set(u["column_names"]) for u in student_uniques]
    assert {"roll_no"} in student_unique_cols

    # Club unique name
    club_uniques = inspector.get_unique_constraints("clubs")
    club_unique_cols = [set(u["column_names"]) for u in club_uniques]
    assert {"name"} in club_unique_cols

    engine.dispose()


def test_7_index_preservation(alembic_cfg, temp_db_path):
    """Test 7: Verify custom indexes are created across tables."""
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    indexes = cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';").fetchall()
    conn.close()

    index_names = {idx[0] for idx in indexes}
    assert "ix_users_username" in index_names
    assert "ix_users_email" in index_names
    assert "ix_students_id" in index_names
    assert "ix_attendance_subject_code" in index_names
    assert "ix_qr_attendance_sessions_session_id" in index_names
    assert len(index_names) >= 35


def test_8_offline_sql_generation(alembic_cfg):
    """Test 8: Verify offline SQL generation emits valid DDL without database connection."""
    buf = io.StringIO()
    # Save current stdout
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        command.upgrade(alembic_cfg, "head", sql=True)
    finally:
        sys.stdout = old_stdout

    sql = buf.getvalue()
    assert "CREATE TABLE announcements" in sql
    assert "CREATE TABLE students" in sql
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE alembic_version" in sql
    assert "INSERT INTO alembic_version" in sql


def test_9_baseline_mismatch_rejection(tmp_path):
    """Test 9: Verify DatabaseVerifier rejects stamping on an incomplete or mismatched database."""
    mismatched_db = tmp_path / "mismatched.db"
    conn = sqlite3.connect(mismatched_db)
    # Create only 1 table with missing columns
    conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT);")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{mismatched_db.as_posix()}")
    verifier = DatabaseVerifier(engine)
    report = verifier.verify_schema()
    engine.dispose()

    assert report.is_valid is False
    assert report.can_stamp is False
    assert len(report.missing_tables) == 21  # 21 missing tables
    assert "students" in report.missing_columns  # missing columns in students
    assert "Schema mismatch" in report.summary


def test_10_sqlite_backup_and_integrity_verification(tmp_path):
    """Test 10: Verify SQLite Online Backup API creates consistent, verified snapshots with overwrite protection."""
    src_db = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"

    # Populate source DB with sample rows
    conn = sqlite3.connect(src_db)
    conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, text_val TEXT);")
    conn.execute("INSERT INTO test_data (text_val) VALUES ('backup_verification_record');")
    conn.commit()
    conn.close()

    # Create backup
    backup_path, checksum = backup_sqlite_database(src_db, backup_dir)
    assert backup_path.exists()
    assert len(checksum) == 64

    # Verify backup contains the record
    b_conn = sqlite3.connect(backup_path)
    rows = b_conn.execute("SELECT text_val FROM test_data;").fetchall()
    b_conn.close()
    assert rows == [("backup_verification_record",)]

    # Overwrite protection test
    with pytest.raises(BackupError):
        # Trying to backup with same filename without overwrite should fail if exists
        backup_sqlite_database(src_db, backup_dir, prefix="custom", overwrite=False)
        # Immediate second call with identical filename
        backup_sqlite_database(src_db, backup_dir, prefix="custom", overwrite=False)

    # Test restoration
    restore_target = tmp_path / "restored.db"
    restore_sqlite_database(backup_path, restore_target)
    r_conn = sqlite3.connect(restore_target)
    r_rows = r_conn.execute("SELECT text_val FROM test_data;").fetchall()
    r_conn.close()
    assert r_rows == [("backup_verification_record",)]
