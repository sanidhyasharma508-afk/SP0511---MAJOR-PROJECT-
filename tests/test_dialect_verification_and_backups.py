"""Automated Test Suite for Phase 19E: Dialect-Aware Database Verification & Backup Architecture.

Verifies:
1. Dialect detection and validation (SQLite, PostgreSQL, and rejection of unsupported dialects).
2. SQLite schema verification, PRAGMA checks, and 5-state migration readiness classification.
3. PostgreSQL verification: connectivity heartbeat (SELECT 1), schema qualification, native enum inspection, sequences.
4. SQLite backup adapter: online backup API, integrity check, SHA-256, overwrite protection, manifest, and restore.
5. PostgreSQL backup adapter: argument construction, password environment isolation (never in CLI), tool-missing diagnostics, output sanitization.
6. BackupManifest serialization, deserialization, and secret masking.
7. get_backup_adapter factory dispatch.
8. Backward compatibility of functional backup/restore wrappers.
"""

from dataclasses import asdict
import datetime
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from alembic.config import Config
from alembic import command
from backend.database import Base
import backend.models
from backend.core.database_verifier import (
    DatabaseVerifier,
    DatabaseReadinessStatus,
    VerificationReport,
    ReadinessReport,
    EXPECTED_REVISION,
    KNOWN_REVISIONS,
    SUPPORTED_DIALECTS,
    POSTGRESQL_EXPECTED_ENUMS,
    get_type_family,
)
from backend.core.backup_utils import (
    BackupError,
    BackupToolNotFoundError,
    BackupManifest,
    BaseBackupAdapter,
    SQLiteBackupAdapter,
    PostgreSQLBackupAdapter,
    get_backup_adapter,
    backup_sqlite_database,
    restore_sqlite_database,
    sanitize_text,
)


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def temp_sqlite_db(tmp_path):
    """Provide an isolated temporary SQLite database path."""
    return tmp_path / "test_dialect_verifier.db"


@pytest.fixture
def alembic_cfg(repo_root, temp_sqlite_db):
    """Provide an Alembic Config pointing to the temporary SQLite database."""
    ini_path = str(repo_root / "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{temp_sqlite_db.as_posix()}")
    return cfg


# ============================================================================
# 1. Dialect Detection & Validation Tests
# ============================================================================

class TestDialectDetectionAndValidation:
    """Tests for dialect detection and enforcement of supported dialects."""

    def test_verifier_accepts_sqlite(self, temp_sqlite_db):
        engine = create_engine(f"sqlite:///{temp_sqlite_db.as_posix()}")
        verifier = DatabaseVerifier(engine)
        assert verifier.dialect_name == "sqlite"
        assert verifier.dialect_name in SUPPORTED_DIALECTS
        engine.dispose()

    def test_verifier_accepts_postgresql(self):
        mock_engine = MagicMock()
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        mock_engine.dialect = mock_dialect
        verifier = DatabaseVerifier(mock_engine)
        assert verifier.dialect_name == "postgresql"
        assert verifier.dialect_name in SUPPORTED_DIALECTS

    def test_verifier_rejects_unsupported_dialects(self):
        for unsupported in ["mysql", "oracle", "mssql", "mariadb"]:
            mock_engine = MagicMock()
            mock_dialect = MagicMock()
            mock_dialect.name = unsupported
            mock_engine.dialect = mock_dialect
            with pytest.raises(ValueError) as exc_info:
                DatabaseVerifier(mock_engine)
            assert f"Unsupported database dialect '{unsupported}'" in str(exc_info.value)


# ============================================================================
# 2. SQLite Verification & Readiness Tests
# ============================================================================

class TestSQLiteDialectVerification:
    """Tests for SQLite-specific verification, PRAGMA checks, and readiness."""

    def test_sqlite_fresh_database(self, temp_sqlite_db):
        conn = sqlite3.connect(temp_sqlite_db)
        conn.close()

        engine = create_engine(f"sqlite:///{temp_sqlite_db.as_posix()}")
        verifier = DatabaseVerifier(engine)
        readiness = verifier.check_readiness()

        assert readiness.status == DatabaseReadinessStatus.FRESH
        assert readiness.can_start is False
        assert readiness.dialect == "sqlite"
        assert len(readiness.missing_tables) == 22
        engine.dispose()

    def test_sqlite_migrated_database(self, alembic_cfg, temp_sqlite_db):
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(f"sqlite:///{temp_sqlite_db.as_posix()}")
        verifier = DatabaseVerifier(engine)
        v_report = verifier.verify_schema()
        r_report = verifier.check_readiness()

        assert v_report.is_valid is True
        assert v_report.dialect == "sqlite"
        assert v_report.integrity_status == "ok"
        assert len(v_report.foreign_key_violations) == 0

        assert r_report.status == DatabaseReadinessStatus.MIGRATED
        assert r_report.can_start is True
        assert r_report.dialect == "sqlite"
        assert r_report.revision == EXPECTED_REVISION
        engine.dispose()

    def test_sqlite_compatible_unstamped_database(self, temp_sqlite_db):
        engine = create_engine(f"sqlite:///{temp_sqlite_db.as_posix()}")
        Base.metadata.create_all(bind=engine)

        verifier = DatabaseVerifier(engine)
        v_report = verifier.verify_schema()
        r_report = verifier.check_readiness()

        assert v_report.is_valid is True
        assert v_report.can_stamp is True
        assert r_report.status == DatabaseReadinessStatus.COMPATIBLE_UNSTAMPED
        assert r_report.can_start is True
        assert r_report.revision is None
        engine.dispose()

    def test_sqlite_executes_integrity_and_foreign_key_pragmas(self, alembic_cfg, temp_sqlite_db):
        command.upgrade(alembic_cfg, "head")
        engine = create_engine(f"sqlite:///{temp_sqlite_db.as_posix()}")

        verifier = DatabaseVerifier(engine)
        with patch.object(engine, "connect", wraps=engine.connect) as mock_connect:
            report = verifier.verify_schema()
            assert report.integrity_status == "ok"
            assert mock_connect.called
        engine.dispose()


# ============================================================================
# 3. PostgreSQL Verification & Readiness Tests
# ============================================================================

class TestPostgreSQLDialectVerification:
    """Tests for PostgreSQL-specific verification, schema qualification, and enums."""

    @pytest.fixture
    def mock_pg_engine(self):
        engine = MagicMock()
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        engine.dialect = mock_dialect
        return engine

    def test_postgresql_heartbeat_execution(self, mock_pg_engine):
        mock_conn = MagicMock()
        mock_conn.exec_driver_sql.return_value.fetchone.return_value = (1,)
        mock_pg_engine.connect.return_value.__enter__.return_value = mock_conn

        with patch("backend.core.database_verifier.inspect") as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspect.return_value = mock_inspector
            mock_inspector.get_table_names.return_value = []

            verifier = DatabaseVerifier(mock_pg_engine)
            readiness = verifier.check_readiness()

            assert readiness.dialect == "postgresql"
            assert readiness.status == DatabaseReadinessStatus.FRESH

    def test_postgresql_schema_qualification(self, mock_pg_engine):
        with patch("backend.core.database_verifier.inspect") as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspect.return_value = mock_inspector
            mock_inspector.get_table_names.return_value = ["users"]

            verifier = DatabaseVerifier(mock_pg_engine, schema="custom_schema")
            assert verifier.schema == "custom_schema"

            verifier.verify_schema()
            mock_inspector.get_table_names.assert_called_with(schema="custom_schema")

    def test_postgresql_native_enum_verification_pass(self, mock_pg_engine):
        mock_inspector = MagicMock()
        mock_inspector.get_enums.return_value = [
            {"name": "eventcategory", "labels": list(POSTGRESQL_EXPECTED_ENUMS["eventcategory"])},
            {"name": "eventstatus", "labels": list(POSTGRESQL_EXPECTED_ENUMS["eventstatus"])},
            {"name": "registrationstatus", "labels": list(POSTGRESQL_EXPECTED_ENUMS["registrationstatus"])},
        ]

        verifier = DatabaseVerifier(mock_pg_engine)
        mismatches = verifier._inspect_postgresql_enums(mock_inspector)
        assert len(mismatches) == 0

    def test_postgresql_native_enum_verification_missing_enum(self, mock_pg_engine):
        mock_inspector = MagicMock()
        # Missing 'registrationstatus'
        mock_inspector.get_enums.return_value = [
            {"name": "eventcategory", "labels": list(POSTGRESQL_EXPECTED_ENUMS["eventcategory"])},
            {"name": "eventstatus", "labels": list(POSTGRESQL_EXPECTED_ENUMS["eventstatus"])},
        ]

        verifier = DatabaseVerifier(mock_pg_engine)
        mismatches = verifier._inspect_postgresql_enums(mock_inspector)
        assert len(mismatches) == 1
        assert "Missing PostgreSQL enum type: 'registrationstatus'" in mismatches[0]

    def test_postgresql_native_enum_verification_missing_label(self, mock_pg_engine):
        mock_inspector = MagicMock()
        # 'eventstatus' missing 'CANCELLED'
        mock_inspector.get_enums.return_value = [
            {"name": "eventcategory", "labels": list(POSTGRESQL_EXPECTED_ENUMS["eventcategory"])},
            {"name": "eventstatus", "labels": ["DRAFT", "PUBLISHED", "COMPLETED"]},
            {"name": "registrationstatus", "labels": list(POSTGRESQL_EXPECTED_ENUMS["registrationstatus"])},
        ]

        verifier = DatabaseVerifier(mock_pg_engine)
        mismatches = verifier._inspect_postgresql_enums(mock_inspector)
        assert len(mismatches) == 1
        assert "Enum 'eventstatus' missing labels" in mismatches[0]
        assert "CANCELLED" in mismatches[0]


# ============================================================================
# 4. SQLite Backup Adapter Tests
# ============================================================================

class TestSQLiteBackupAdapter:
    """Tests for SQLite point-in-time online backups, manifests, and restoration."""

    def test_sqlite_backup_creation_and_manifest(self, alembic_cfg, temp_sqlite_db, tmp_path):
        command.upgrade(alembic_cfg, "head")

        adapter = SQLiteBackupAdapter(temp_sqlite_db)
        backup_dir = tmp_path / "backups"
        backup_file, manifest = adapter.create_backup(backup_dir, prefix="unit_test")

        assert backup_file.exists()
        assert manifest.dialect == "sqlite"
        assert manifest.database_identifier == temp_sqlite_db.name
        assert manifest.format == "sqlite_file"
        assert manifest.verification_status == "verified"
        assert manifest.alembic_revision == EXPECTED_REVISION
        assert len(manifest.sha256_checksum) == 64
        assert manifest.file_size_bytes == backup_file.stat().st_size

        # Verify manifest file on disk
        manifest_file = backup_file.with_suffix(backup_file.suffix + ".manifest.json")
        assert manifest_file.exists()
        loaded = BackupManifest.load(manifest_file)
        assert loaded.sha256_checksum == manifest.sha256_checksum
        assert loaded.alembic_revision == EXPECTED_REVISION

    def test_sqlite_backup_overwrite_protection(self, temp_sqlite_db, tmp_path):
        conn = sqlite3.connect(temp_sqlite_db)
        conn.close()

        adapter = SQLiteBackupAdapter(temp_sqlite_db)
        backup_dir = tmp_path / "backups"

        fixed_time = datetime.datetime(2026, 11, 9, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.timezone = datetime.timezone
            # First create
            p1, _ = adapter.create_backup(backup_dir, prefix="locked")
            # Attempt overwrite
            with pytest.raises(BackupError) as exc_info:
                adapter.create_backup(backup_dir, prefix="locked", overwrite=False)
            assert "already exists and overwrite=False" in str(exc_info.value)

    def test_sqlite_restore_and_validate_restore(self, alembic_cfg, temp_sqlite_db, tmp_path):
        command.upgrade(alembic_cfg, "head")

        adapter = SQLiteBackupAdapter(temp_sqlite_db)
        backup_dir = tmp_path / "backups"
        backup_file, _ = adapter.create_backup(backup_dir)

        # Validate restore
        restore_target = tmp_path / "restored.db"
        assert adapter.validate_restore(backup_file, restore_target) is True

        # Perform restore
        adapter.restore(backup_file, restore_target)
        assert restore_target.exists()

        # Check restored database integrity and tables
        chk_conn = sqlite3.connect(restore_target)
        cur = chk_conn.cursor()
        res = cur.execute("PRAGMA integrity_check;").fetchall()
        assert res[0][0] == "ok"
        rev = cur.execute("SELECT version_num FROM alembic_version;").fetchall()
        assert rev[0][0] == EXPECTED_REVISION
        chk_conn.close()


# ============================================================================
# 5. PostgreSQL Backup Adapter Tests
# ============================================================================

class TestPostgreSQLBackupAdapter:
    """Tests for PostgreSQL backup command generation, password isolation, and safety."""

    def test_postgresql_command_construction_and_no_password_in_cli(self, tmp_path):
        db_url = "postgresql+psycopg://campus_user:SuperSecretPassword123@10.0.0.5:5432/campus_production"
        adapter = PostgreSQLBackupAdapter(db_url, pg_dump_cmd="pg_dump")

        executed_cmds = []
        captured_envs = []

        def mock_executor(cmd, env=None, target_path=None, **kwargs):
            executed_cmds.append(cmd)
            if env:
                captured_envs.append(env)
            if target_path:
                target_path.write_bytes(b"PGDMP\x01\x02mock_dump_data")
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = "pg_dump 16.1"
            return mock_res

        backup_dir = tmp_path / "pg_backups"
        target_path, manifest = adapter.create_backup(
            backup_dir,
            prefix="test_pg",
            format_type="custom",
            executor=mock_executor,
            alembic_revision=EXPECTED_REVISION,
        )

        assert len(executed_cmds) >= 1
        cli_cmd = executed_cmds[0]
        cmd_str = " ".join(cli_cmd)

        # CRITICAL SECURITY ASSERTION: Password NEVER appears in command arguments
        assert "SuperSecretPassword123" not in cmd_str
        assert "-W" not in cli_cmd

        # Verify command flags
        assert "-h" in cli_cmd and "10.0.0.5" in cli_cmd
        assert "-p" in cli_cmd and "5432" in cli_cmd
        assert "-U" in cli_cmd and "campus_user" in cli_cmd
        assert "-F" in cli_cmd and "c" in cli_cmd
        assert "campus_production" in cli_cmd

        # CRITICAL SECURITY ASSERTION: Password is passed exclusively in subprocess env
        assert captured_envs[0].get("PGPASSWORD") == "SuperSecretPassword123"

        # Verify manifest is completely secret-free
        assert manifest.dialect == "postgresql"
        assert "SuperSecretPassword123" not in manifest.database_identifier
        assert "SuperSecretPassword123" not in manifest.to_json()
        assert manifest.verification_status == "verified"
        assert manifest.alembic_revision == EXPECTED_REVISION

    def test_postgresql_missing_tool_raises_tool_not_found(self, tmp_path):
        db_url = "postgresql+psycopg://user:pass@localhost:5432/testdb"
        adapter = PostgreSQLBackupAdapter(db_url, pg_dump_cmd="/nonexistent/path/pg_dump_xyz")
        backup_dir = tmp_path / "backups"

        with pytest.raises(BackupToolNotFoundError) as exc_info:
            adapter.create_backup(backup_dir)
        assert "pg_dump_xyz' was not found on system PATH" in str(exc_info.value)

    def test_postgresql_backup_sanitizes_errors(self, tmp_path):
        db_url = "postgresql+psycopg://user:SecretKey99@localhost:5432/proddb"
        adapter = PostgreSQLBackupAdapter(db_url)

        def failing_executor(cmd, env=None, target_path=None, **kwargs):
            raise RuntimeError("Fatal: password=SecretKey99 rejected by server")

        backup_dir = tmp_path / "backups"
        with pytest.raises(BackupError) as exc_info:
            adapter.create_backup(backup_dir, executor=failing_executor)

        error_message = str(exc_info.value)
        assert "SecretKey99" not in error_message
        assert "******" in error_message

    def test_default_restore_does_not_include_clean_mocked(self, tmp_path):
        """[MOCKED TEST] Verify default restore command never includes --clean (-c)."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/source_db"
        adapter = PostgreSQLBackupAdapter(db_url, pg_restore_cmd="pg_restore")

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        executed_cmds = []

        def mock_executor(cmd, env=None, backup_path=None, target_db=None, **kwargs):
            executed_cmds.append(cmd)
            mock_res = MagicMock()
            mock_res.returncode = 0
            return mock_res

        res = adapter.restore(
            mock_backup,
            target_destination="isolated_empty_db",
            executor=mock_executor,
        )

        assert res["status"] == "restored"
        assert res["clean_enabled"] is False
        assert len(executed_cmds) == 1
        cli_cmd = executed_cmds[0]
        # CRITICAL SAFETY ASSERTION: Default restore NEVER passes -c / --clean
        assert "-c" not in cli_cmd
        assert "--clean" not in cli_cmd

    def test_existing_non_empty_destination_is_rejected_mocked(self, tmp_path):
        """[MOCKED TEST] Verify restore into non-empty database without destructive authorization is rejected."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/source_db"
        adapter = PostgreSQLBackupAdapter(db_url)

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        with pytest.raises(BackupError) as exc_info:
            adapter.restore(
                mock_backup,
                target_destination="existing_populated_db",
                target_is_empty=False,
                allow_destructive_clean=False,
            )
        assert "is not empty" in str(exc_info.value)
        assert "destructive authorization is prohibited" in str(exc_info.value)

    def test_active_source_database_destination_is_rejected_mocked(self, tmp_path):
        """[MOCKED TEST] Verify restore refuses to target the active source database."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/active_campus_db"
        adapter = PostgreSQLBackupAdapter(db_url)

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        with pytest.raises(BackupError) as exc_info:
            adapter.restore(mock_backup, target_destination="active_campus_db", overwrite=False)
        assert "active source database" in str(exc_info.value)
        assert "strictly prohibited" in str(exc_info.value)

    def test_same_database_with_alternate_url_formatting_is_detected_mocked(self, tmp_path):
        """[MOCKED TEST] Verify alias normalization detects identical database under alternate URL formats."""
        db_url = "postgresql+psycopg://app_user:pass@127.0.0.1:5432/campus_system_db"
        adapter = PostgreSQLBackupAdapter(db_url)

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        # Alternate representations of the same database
        aliases = [
            "campus_system_db",
            "localhost/campus_system_db",
            "127.0.0.1:5432/campus_system_db",
            "postgresql://other_user:diffpass@localhost:5432/campus_system_db",
            "postgresql://other_user:diffpass@127.0.0.1/CAMPUS_SYSTEM_DB",
        ]

        for alias in aliases:
            with pytest.raises(BackupError) as exc_info:
                adapter.restore(mock_backup, target_destination=alias)
            assert "active source database" in str(exc_info.value)

    def test_production_targeted_restore_is_rejected_mocked(self, tmp_path):
        """[MOCKED TEST] Verify restore operations targeting production databases are rejected."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/staging_db"
        adapter = PostgreSQLBackupAdapter(db_url)

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        prod_targets = [
            "campus_production",
            "college_prod_db",
            "live_replica",
            "postgresql://admin:pass@db.supabase.co:5432/campus",
            "postgresql://admin:pass@cluster.rds.amazonaws.com:5432/campus",
        ]

        for prod_target in prod_targets:
            with pytest.raises(BackupError) as exc_info:
                adapter.restore(mock_backup, target_destination=prod_target)
            assert "targeting production database" in str(exc_info.value)

    def test_missing_destination_information_is_rejected_mocked(self, tmp_path):
        """[MOCKED TEST] Verify missing, blank, or whitespace destination is rejected."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/source_db"
        adapter = PostgreSQLBackupAdapter(db_url)

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        for invalid_dest in ["", "   ", None]:
            with pytest.raises(BackupError) as exc_info:
                adapter.restore(mock_backup, target_destination=invalid_dest)
            assert "cannot be empty" in str(exc_info.value)

    def test_explicitly_authorized_destructive_behavior_cannot_be_triggered_accidentally_mocked(self, tmp_path):
        """[MOCKED TEST] Verify destructive clean requires explicit confirmation and cannot target production."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/source_db"
        adapter = PostgreSQLBackupAdapter(db_url, pg_restore_cmd="pg_restore")

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        # 1. clean=True without confirmation must fail
        with pytest.raises(BackupError) as exc_info:
            adapter.restore(
                mock_backup,
                target_destination="disposable_scratch_db",
                clean=True,
                confirm_destructive_clean_database_name="",
            )
        assert "Destructive clean (-c) requested but not explicitly authorized" in str(exc_info.value)

        # 2. allow_destructive_clean=True with mismatching confirmation name must fail
        with pytest.raises(BackupError) as exc_info:
            adapter.restore(
                mock_backup,
                target_destination="disposable_scratch_db",
                allow_destructive_clean=True,
                confirm_destructive_clean_database_name="wrong_db_name",
            )
        assert "Destructive clean authorization failed" in str(exc_info.value)

        # 3. Valid authorization against non-production database succeeds and passes -c
        executed_cmds = []

        def mock_clean_executor(cmd, env=None, backup_path=None, target_db=None, **kwargs):
            executed_cmds.append(cmd)
            mock_res = MagicMock()
            mock_res.returncode = 0
            return mock_res

        res = adapter.restore(
            mock_backup,
            target_destination="disposable_scratch_db",
            allow_destructive_clean=True,
            confirm_destructive_clean_database_name="disposable_scratch_db",
            executor=mock_clean_executor,
        )
        assert res["clean_enabled"] is True
        assert "-c" in executed_cmds[0]

    def test_credential_values_never_appear_in_subprocess_arguments_or_sanitized_logs_mocked(self, tmp_path):
        """[MOCKED TEST] Verify password credentials never appear in CLI args and are masked in errors."""
        db_url = "postgresql+psycopg://admin_user:SuperSecretPass999@10.0.0.12:5432/primary_source_db"
        adapter = PostgreSQLBackupAdapter(db_url, pg_restore_cmd="pg_restore")

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        executed_cmds = []
        captured_envs = []

        def mock_executor(cmd, env=None, backup_path=None, target_db=None, **kwargs):
            executed_cmds.append(cmd)
            if env:
                captured_envs.append(env)
            mock_res = MagicMock()
            mock_res.returncode = 0
            return mock_res

        adapter.restore(mock_backup, target_destination="isolated_target_db", executor=mock_executor)

        cmd_str = " ".join(executed_cmds[0])
        # Password NEVER in CLI arguments
        assert "SuperSecretPass999" not in cmd_str
        assert "-W" not in executed_cmds[0]
        # Password strictly in environment
        assert captured_envs[0].get("PGPASSWORD") == "SuperSecretPass999"

        # Check error sanitization on failure
        def failing_executor(cmd, env=None, backup_path=None, target_db=None, **kwargs):
            raise RuntimeError("pg_restore fatal: password=SuperSecretPass999 rejected")

        with pytest.raises(BackupError) as exc_info:
            adapter.restore(mock_backup, target_destination="isolated_target_db", executor=failing_executor)
        err_msg = str(exc_info.value)
        assert "SuperSecretPass999" not in err_msg
        assert "******" in err_msg

    def test_failed_restore_does_not_trigger_destructive_cleanup_of_unrelated_resources_mocked(self, tmp_path):
        """[MOCKED TEST] Verify failed restore preserves backup file and surrounding assets."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/source_db"
        adapter = PostgreSQLBackupAdapter(db_url)

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")
        unrelated_file = tmp_path / "important_data.csv"
        unrelated_file.write_text("id,val\n1,a")

        def failing_executor(cmd, env=None, backup_path=None, target_db=None, **kwargs):
            mock_res = MagicMock()
            mock_res.returncode = 2
            mock_res.stderr = "FATAL: connection terminated"
            return mock_res

        with pytest.raises(BackupError):
            adapter.restore(mock_backup, target_destination="scratch_db", executor=failing_executor)

        # Unrelated assets and backup artifact MUST NOT be deleted
        assert mock_backup.exists()
        assert unrelated_file.exists()
        assert unrelated_file.read_text() == "id,val\n1,a"

    def test_postgresql_restore_missing_tool_raises_tool_not_found_mocked(self, tmp_path):
        """[MOCKED TEST] Verify missing pg_restore executable raises BackupToolNotFoundError."""
        db_url = "postgresql+psycopg://user:pass@localhost:5432/testdb"
        adapter = PostgreSQLBackupAdapter(db_url, pg_restore_cmd="/missing/path/pg_restore_xyz")

        mock_backup = tmp_path / "valid.dump"
        mock_backup.write_bytes(b"PGDMP\x01\x02valid")

        with pytest.raises(BackupToolNotFoundError) as exc_info:
            adapter.restore(mock_backup, target_destination="target_disposable_db")
        assert "pg_restore_xyz' was not found on system PATH" in str(exc_info.value)


# ============================================================================
# 6. Factory & Backward-Compatibility Tests
# ============================================================================

class TestFactoryAndBackwardCompatibility:
    """Tests for get_backup_adapter factory and backward-compatible functional wrappers."""

    def test_get_backup_adapter_sqlite_path(self, temp_sqlite_db):
        adapter = get_backup_adapter(temp_sqlite_db)
        assert isinstance(adapter, SQLiteBackupAdapter)
        assert adapter.dialect == "sqlite"

    def test_get_backup_adapter_sqlite_url(self):
        adapter = get_backup_adapter("sqlite:///./campus_automation.db")
        assert isinstance(adapter, SQLiteBackupAdapter)

    def test_get_backup_adapter_postgresql_url(self):
        adapter = get_backup_adapter("postgresql+psycopg://user:pass@localhost:5432/campus_db")
        assert isinstance(adapter, PostgreSQLBackupAdapter)
        assert adapter.dialect == "postgresql"

    def test_get_backup_adapter_from_engine(self, temp_sqlite_db):
        engine = create_engine(f"sqlite:///{temp_sqlite_db.as_posix()}")
        adapter = get_backup_adapter(engine)
        assert isinstance(adapter, SQLiteBackupAdapter)
        engine.dispose()

    def test_backup_sqlite_database_functional_wrapper(self, alembic_cfg, temp_sqlite_db, tmp_path):
        command.upgrade(alembic_cfg, "head")

        backup_dir = tmp_path / "functional_backups"
        path, checksum = backup_sqlite_database(temp_sqlite_db, backup_dir, prefix="func_test")

        assert path.exists()
        assert len(checksum) == 64

        # Test functional restore
        restore_path = tmp_path / "func_restored.db"
        restore_sqlite_database(path, restore_path)
        assert restore_path.exists()

        chk_conn = sqlite3.connect(restore_path)
        assert chk_conn.execute("PRAGMA integrity_check;").fetchall()[0][0] == "ok"
        chk_conn.close()

    def test_sanitize_text_utility(self):
        raw = "postgres://admin:TopSecretPassword@db.campus.edu:5432/cas_db password=TopSecretPassword"
        sanitized = sanitize_text(raw, secret="TopSecretPassword")
        assert "TopSecretPassword" not in sanitized
        assert "******" in sanitized
