"""Dialect-aware database backup and restoration architecture for SQLite and PostgreSQL.

Provides:
- SQLite point-in-time snapshots via SQLite Online Backup API (sqlite3.backup) safe under active WAL mode.
- PostgreSQL backups via pg_dump with safe credential handling (PGPASSWORD environment isolation),
  format selection (custom/plain), and non-destructive restore validation via pg_restore.
- Structured, secret-free BackupManifest tracking backup metadata, checksums, revisions, and status.
- Backward-compatible backup_sqlite_database and restore_sqlite_database functional entrypoints.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from typing import Any, Callable, Dict, Optional, Tuple, Union
import uuid

from sqlalchemy.engine import Engine, make_url
from backend.core.config import normalize_database_url, mask_database_url


class BackupError(Exception):
    """Base exception raised when database backup or restoration fails validation or execution."""
    pass


class BackupToolNotFoundError(BackupError):
    """Raised when an external tool required for backup/restore (e.g., pg_dump, pg_restore) is missing."""
    pass


def sanitize_text(text: str, secret: str = "") -> str:
    """Mask credentials and secrets from exception messages, logs, or command strings."""
    if not text:
        return ""
    sanitized = text
    if secret:
        sanitized = sanitized.replace(secret, "******")
    # Mask connection URI passwords: scheme://user:pass@host
    sanitized = re.sub(r"://([^:@]+):([^@]+)@", r"://\1:******@", sanitized)
    # Mask password=... patterns in connection strings
    sanitized = re.sub(r"(password=)[^\s;'\"]+", r"\1******", sanitized, flags=re.IGNORECASE)
    return sanitized


@dataclass
class BackupManifest:
    """Structured, secret-free metadata tracking database backups across dialects."""
    backup_id: str
    dialect: str  # "sqlite" or "postgresql"
    database_identifier: str  # Sanitized database file name or masked URL, NEVER passwords
    timestamp: str  # ISO 8601 UTC string
    format: str  # "sqlite_file", "pg_dump_custom", "pg_dump_plain"
    backup_file_path: str
    file_size_bytes: int
    sha256_checksum: str
    alembic_revision: Optional[str] = None
    verification_status: str = "unverified"  # "verified", "unverified", "failed"
    tool_version: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to a JSON-serializable dictionary with masked identifiers."""
        return {
            "backup_id": self.backup_id,
            "dialect": self.dialect,
            "database_identifier": mask_database_url(self.database_identifier) if "://" in self.database_identifier else self.database_identifier,
            "timestamp": self.timestamp,
            "format": self.format,
            "backup_file_path": self.backup_file_path,
            "file_size_bytes": self.file_size_bytes,
            "sha256_checksum": self.sha256_checksum,
            "alembic_revision": self.alembic_revision,
            "verification_status": self.verification_status,
            "tool_version": self.tool_version,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize manifest to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Union[str, Path]) -> Path:
        """Write manifest JSON to disk."""
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return p

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupManifest":
        """Reconstruct a BackupManifest from a dictionary."""
        return cls(
            backup_id=data.get("backup_id", ""),
            dialect=data.get("dialect", "unknown"),
            database_identifier=data.get("database_identifier", ""),
            timestamp=data.get("timestamp", ""),
            format=data.get("format", "unknown"),
            backup_file_path=data.get("backup_file_path", ""),
            file_size_bytes=int(data.get("file_size_bytes", 0)),
            sha256_checksum=data.get("sha256_checksum", ""),
            alembic_revision=data.get("alembic_revision"),
            verification_status=data.get("verification_status", "unverified"),
            tool_version=data.get("tool_version", "unknown"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "BackupManifest":
        """Reconstruct a BackupManifest from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def load(cls, path: Union[str, Path]) -> "BackupManifest":
        """Load and parse manifest from a file path."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())


class BaseBackupAdapter(ABC):
    """Abstract base class for dialect-specific backup and restore adapters."""

    @abstractmethod
    def create_backup(
        self,
        backup_dir: Path,
        prefix: str = "backup",
        overwrite: bool = False,
        **kwargs: Any,
    ) -> Tuple[Path, BackupManifest]:
        """Create a point-in-time backup and return (Path, BackupManifest)."""
        pass

    @abstractmethod
    def verify_backup(self, backup_path: Path) -> bool:
        """Verify the structural integrity of a backup artifact."""
        pass

    @abstractmethod
    def validate_restore(
        self,
        backup_path: Path,
        target_destination: Any,
        overwrite: bool = False,
    ) -> bool:
        """Validate non-destructive restoration safety before applying."""
        pass

    @abstractmethod
    def restore(
        self,
        backup_path: Path,
        target_destination: Any,
        overwrite: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Restore a database from a verified backup artifact."""
        pass


class SQLiteBackupAdapter(BaseBackupAdapter):
    """Adapter for SQLite point-in-time online backups using the sqlite3.backup API."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path).resolve()
        self.dialect = "sqlite"

    def create_backup(
        self,
        backup_dir: Path,
        prefix: str = "backup",
        overwrite: bool = False,
        save_manifest: bool = True,
        **kwargs: Any,
    ) -> Tuple[Path, BackupManifest]:
        """Create a point-in-time snapshot backup using the SQLite Online Backup API."""
        if not self.db_path.exists():
            raise BackupError(f"Source database file does not exist: {self.db_path}")

        backup_dir = Path(backup_dir).resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        timestamp_str = now_utc.strftime("%Y%m%d_%H%M%S")
        iso_timestamp = now_utc.isoformat()
        backup_id = f"sqlite_{timestamp_str}_{uuid.uuid4().hex[:8]}"

        backup_filename = f"{prefix}_{timestamp_str}_{self.db_path.name}"
        target_path = backup_dir / backup_filename

        if target_path.exists() and not overwrite:
            raise BackupError(f"Destination backup file already exists and overwrite=False: {target_path}")

        # Connect source in read-only URI mode to avoid locking active writers
        source_uri = f"file:{self.db_path.as_posix()}?mode=ro"
        try:
            source_conn = sqlite3.connect(source_uri, uri=True)
        except Exception:
            source_conn = sqlite3.connect(str(self.db_path))

        target_conn = sqlite3.connect(str(target_path))

        try:
            source_conn.backup(target_conn)
        except Exception as e:
            if target_path.exists():
                target_path.unlink()
            raise BackupError(f"SQLite backup operation failed: {e}") from e
        finally:
            source_conn.close()
            target_conn.close()

        # Perform post-backup PRAGMA integrity_check
        if not self.verify_backup(target_path):
            if target_path.exists():
                target_path.unlink()
            raise BackupError(f"Backup verification failed: PRAGMA integrity_check returned non-ok result")

        # Query alembic revision from the created backup
        alembic_rev = None
        try:
            chk_conn = sqlite3.connect(str(target_path))
            cur = chk_conn.cursor()
            rows = cur.execute("SELECT version_num FROM alembic_version;").fetchall()
            if rows and rows[0][0]:
                alembic_rev = str(rows[0][0])
            chk_conn.close()
        except Exception:
            alembic_rev = None

        # Calculate SHA-256 and file size
        hasher = hashlib.sha256()
        with open(target_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        checksum = hasher.hexdigest()
        file_size = target_path.stat().st_size

        manifest = BackupManifest(
            backup_id=backup_id,
            dialect="sqlite",
            database_identifier=self.db_path.name,
            timestamp=iso_timestamp,
            format="sqlite_file",
            backup_file_path=str(target_path),
            file_size_bytes=file_size,
            sha256_checksum=checksum,
            alembic_revision=alembic_rev,
            verification_status="verified",
            tool_version=f"sqlite3 {sqlite3.sqlite_version}",
        )

        if save_manifest:
            manifest_path = target_path.with_suffix(target_path.suffix + ".manifest.json")
            manifest.save(manifest_path)

        return target_path, manifest

    def verify_backup(self, backup_path: Path) -> bool:
        """Verify the SQLite database backup via PRAGMA integrity_check."""
        backup_path = Path(backup_path).resolve()
        if not backup_path.exists():
            return False
        test_conn = sqlite3.connect(str(backup_path))
        try:
            res = test_conn.cursor().execute("PRAGMA integrity_check;").fetchall()
            return bool(res and res[0][0] == "ok")
        except Exception:
            return False
        finally:
            test_conn.close()

    def restore(
        self,
        backup_path: Path,
        target_db_path: Path,
        overwrite: bool = False,
    ) -> None:
        """Restore a SQLite database from a verified backup file using the SQLite Backup API."""
        backup_path = Path(backup_path).resolve()
        target_db_path = Path(target_db_path).resolve()

        if not backup_path.exists():
            raise BackupError(f"Backup file does not exist: {backup_path}")

        if target_db_path.exists() and not overwrite:
            raise BackupError(f"Target database already exists and overwrite=False: {target_db_path}")

        # Verify integrity before restore
        if not self.verify_backup(backup_path):
            raise BackupError(f"Cannot restore: backup file failed integrity check: {backup_path}")

        source_conn = sqlite3.connect(str(backup_path))
        dest_conn = sqlite3.connect(str(target_db_path))
        try:
            source_conn.backup(dest_conn)
        except Exception as e:
            raise BackupError(f"Restore operation failed: {e}") from e
        finally:
            source_conn.close()
            dest_conn.close()

    def validate_restore(
        self,
        backup_path: Path,
        target_destination: Any,
        overwrite: bool = False,
    ) -> bool:
        """Validate restoration prerequisites safely without modifying target."""
        backup_path = Path(backup_path).resolve()
        target_db_path = Path(target_destination).resolve()

        if not backup_path.exists():
            raise BackupError(f"Backup file does not exist: {backup_path}")
        if not self.verify_backup(backup_path):
            raise BackupError(f"Backup file failed integrity verification: {backup_path}")
        if target_db_path.exists() and not overwrite:
            raise BackupError(f"Target database file already exists and overwrite=False: {target_db_path}")
        return True


def normalize_db_identity(
    url_or_name: str,
    default_host: str = "localhost",
    default_port: int = 5432,
) -> Dict[str, Any]:
    """Parse and normalize database connection identity for robust alias and identity comparison.

    Normalizes:
    - localhost / 127.0.0.1 / ::1 / 0.0.0.0 to 'localhost'
    - Default port 5432
    - Database name (case-insensitive and stripped)
    - URL schemes (postgres, postgresql, postgresql+psycopg)
    """
    clean_target = str(url_or_name).strip()
    if not clean_target:
        return {"host": "", "port": default_port, "database": "", "username": ""}

    if "://" in clean_target:
        norm_url = normalize_database_url(clean_target)
        parsed = make_url(norm_url)
        host = (parsed.host or default_host).lower().strip()
        port = parsed.port or default_port
        database = (parsed.database or "").lower().strip()
        username = (parsed.username or "").lower().strip()
    elif "/" in clean_target:
        parts = clean_target.split("/", 1)
        host_port = parts[0].strip()
        database = parts[1].strip().lower()
        if ":" in host_port:
            hp = host_port.split(":")
            host = hp[0].lower().strip()
            try:
                port = int(hp[1])
            except ValueError:
                port = default_port
        else:
            host = host_port.lower().strip()
            port = default_port
        username = ""
    else:
        host = default_host.lower().strip()
        port = default_port
        database = clean_target.lower().strip()
        username = ""

    # Normalize local host aliases
    if host in ("127.0.0.1", "::1", "0.0.0.0", "localhost"):
        host = "localhost"

    return {
        "host": host,
        "port": port,
        "database": database,
        "username": username,
    }


def is_same_database_identity(source_ident: Dict[str, Any], dest_ident: Dict[str, Any]) -> bool:
    """Determine whether source and destination point to the same physical database instance."""
    if not source_ident.get("database") or not dest_ident.get("database"):
        return False
    if source_ident["database"] != dest_ident["database"]:
        return False
    return (
        source_ident.get("host") == dest_ident.get("host")
        and source_ident.get("port") == dest_ident.get("port")
    )


def is_production_database_target(ident: Dict[str, Any], raw_url_or_name: str) -> bool:
    """Detect whether a database destination targets a production environment."""
    db_name = ident.get("database", "").lower()
    host_name = ident.get("host", "").lower()
    raw_lower = str(raw_url_or_name).lower()

    # Reject if database name contains production markers
    prod_markers = ["prod", "production", "live"]
    db_tokens = re.split(r"[_\-\.]", db_name)
    if any(m in db_tokens for m in prod_markers):
        return True
    if any(p in db_name for p in ["production", "_prod", "prod_"]):
        return True

    # Reject if host indicates production cloud deployment
    cloud_prod_hosts = ["supabase.co", "supabase.com", "rds.amazonaws.com", "cloudsql", "render.com", "railway.app", "elephantsql.com"]
    if any(c in host_name for c in cloud_prod_hosts):
        return True

    # Reject explicit production query parameters or tags
    if "env=production" in raw_lower or "mode=production" in raw_lower or "target=prod" in raw_lower:
        return True

    return False


class PostgreSQLBackupAdapter(BaseBackupAdapter):
    """Adapter for PostgreSQL backups and restores using pg_dump and pg_restore."""

    def __init__(
        self,
        database_url: str,
        pg_dump_cmd: Optional[str] = None,
        pg_restore_cmd: Optional[str] = None,
    ):
        self.dialect = "postgresql"
        normalized = normalize_database_url(database_url)
        self.raw_url = normalized
        self.masked_url = mask_database_url(normalized)

        parsed = make_url(normalized)
        if parsed.get_backend_name() != "postgresql":
            raise ValueError(
                f"PostgreSQLBackupAdapter requires postgresql dialect, got '{parsed.get_backend_name()}'"
            )

        self.host = parsed.host or "localhost"
        self.port = parsed.port or 5432
        self.database = parsed.database or ""
        self.user = parsed.username or ""
        self.password = parsed.password or ""

        self.source_identity = normalize_db_identity(self.raw_url, default_host=self.host, default_port=self.port)

        self.pg_dump_cmd = pg_dump_cmd or "pg_dump"
        self.pg_restore_cmd = pg_restore_cmd or "pg_restore"

    def _resolve_tool(self, cmd_name: str) -> Optional[str]:
        """Resolve full tool executable path if available."""
        if Path(cmd_name).is_file():
            return cmd_name
        return shutil.which(cmd_name)

    def _get_tool_version(
        self,
        tool_cmd: str,
        executor: Optional[Callable[..., Any]] = None,
    ) -> str:
        """Fetch version string of the backup tool without exposing errors."""
        resolved = self._resolve_tool(tool_cmd)
        if not resolved and not executor:
            return "unknown"
        try:
            if executor:
                res = executor([tool_cmd, "--version"])
                return str(res.stdout or res).strip()
            proc = subprocess.run(
                [tool_cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def create_backup(
        self,
        backup_dir: Path,
        prefix: str = "pg_backup",
        overwrite: bool = False,
        format_type: str = "custom",  # "custom" (-Fc) or "plain" (-Fp)
        save_manifest: bool = True,
        executor: Optional[Callable[..., Any]] = None,
        alembic_revision: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[Path, BackupManifest]:
        """Create a PostgreSQL backup artifact using pg_dump with safe credential handling."""
        resolved_dump = self._resolve_tool(self.pg_dump_cmd)
        if not resolved_dump and not executor:
            raise BackupToolNotFoundError(
                f"PostgreSQL backup tool '{self.pg_dump_cmd}' was not found on system PATH. "
                "Please install PostgreSQL client utilities (postgresql-client or postgresql) "
                "to enable automated PostgreSQL backups."
            )

        backup_dir = Path(backup_dir).resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        timestamp_str = now_utc.strftime("%Y%m%d_%H%M%S")
        iso_timestamp = now_utc.isoformat()
        backup_id = f"pg_{timestamp_str}_{uuid.uuid4().hex[:8]}"

        ext = ".dump" if format_type == "custom" else ".sql"
        clean_db_name = self.database or "db"
        backup_filename = f"{prefix}_{timestamp_str}_{clean_db_name}{ext}"
        target_path = backup_dir / backup_filename

        if target_path.exists() and not overwrite:
            raise BackupError(f"Destination backup file already exists and overwrite=False: {target_path}")

        # Construct pg_dump argument vector
        # CRITICAL SECURITY RULE: NEVER pass password as a CLI argument!
        fmt_flag = "c" if format_type == "custom" else "p"
        cmd = [self.pg_dump_cmd]
        if self.host:
            cmd.extend(["-h", self.host])
        if self.port:
            cmd.extend(["-p", str(self.port)])
        if self.user:
            cmd.extend(["-U", self.user])
        cmd.extend(["-F", fmt_flag, "-f", str(target_path)])
        if self.database:
            cmd.append(self.database)

        # Pass PGPASSWORD exclusively via isolated subprocess environment
        sub_env = os.environ.copy()
        if self.password:
            sub_env["PGPASSWORD"] = self.password

        # Execute dump
        try:
            if executor:
                executor(cmd, env=sub_env, target_path=target_path)
            else:
                proc = subprocess.run(
                    cmd,
                    env=sub_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                if proc.returncode != 0:
                    clean_err = sanitize_text(proc.stderr, self.password)
                    if target_path.exists():
                        target_path.unlink()
                    raise BackupError(f"pg_dump failed with exit code {proc.returncode}: {clean_err}")
        except FileNotFoundError:
            raise BackupToolNotFoundError(
                f"PostgreSQL backup executable '{self.pg_dump_cmd}' could not be executed."
            )
        except Exception as e:
            if not isinstance(e, (BackupError, BackupToolNotFoundError)):
                if target_path.exists():
                    target_path.unlink()
                raise BackupError(f"pg_dump execution failed: {sanitize_text(str(e), self.password)}") from e
            raise

        tool_version = self._get_tool_version(self.pg_dump_cmd, executor)

        # Calculate SHA-256 and size
        file_size = target_path.stat().st_size if target_path.exists() else 0
        hasher = hashlib.sha256()
        if target_path.exists():
            with open(target_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            checksum = hasher.hexdigest()
        else:
            checksum = ""

        # Verify integrity
        is_verified = self.verify_backup(target_path, executor=executor)
        verification_status = "verified" if is_verified else "failed"

        manifest = BackupManifest(
            backup_id=backup_id,
            dialect="postgresql",
            database_identifier=self.masked_url,
            timestamp=iso_timestamp,
            format=f"pg_dump_{format_type}",
            backup_file_path=str(target_path),
            file_size_bytes=file_size,
            sha256_checksum=checksum,
            alembic_revision=alembic_revision,
            verification_status=verification_status,
            tool_version=tool_version,
        )

        if save_manifest:
            manifest_path = target_path.with_suffix(target_path.suffix + ".manifest.json")
            manifest.save(manifest_path)

        return target_path, manifest

    def verify_backup(
        self,
        backup_path: Path,
        executor: Optional[Callable[..., Any]] = None,
    ) -> bool:
        """Verify the structural integrity of a PostgreSQL backup artifact."""
        backup_path = Path(backup_path).resolve()
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            return False

        # Custom format archive verification
        # 1. Check custom archive magic bytes (b"PGDMP")
        is_custom_dump = False
        try:
            with open(backup_path, "rb") as f:
                magic = f.read(5)
                if magic == b"PGDMP":
                    is_custom_dump = True
        except Exception:
            pass

        # 2. If custom dump, test TOC integrity via pg_restore --list without database connection
        resolved_restore = self._resolve_tool(self.pg_restore_cmd)
        if is_custom_dump and (resolved_restore or executor):
            cmd = [self.pg_restore_cmd, "--list", str(backup_path)]
            try:
                if executor:
                    res = executor(cmd)
                    return True
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                return proc.returncode == 0
            except Exception:
                return False

        # If plain SQL or pg_restore is not installed, verify file exists and is non-empty
        return backup_path.stat().st_size > 0

    def validate_restore(
        self,
        backup_path: Path,
        target_destination: Any,
        overwrite: bool = False,
        target_is_empty: Optional[bool] = None,
        allow_destructive_clean: bool = False,
        confirm_destructive_clean_database_name: str = "",
    ) -> bool:
        """Validate restoration safety before invoking restore tools.

        SAFETY CONTROLS ENFORCED:
        1. Backup artifact exists, is non-empty, and passes integrity checks.
        2. Explicit target destination required: destination cannot be empty, None, or inferred.
        3. Active database protection: Compares normalized host/port/database identity to detect
           matching active database, including alternate URL aliases (127.0.0.1 vs localhost, default port, casing).
        4. Production database rejection: Rejects any restoration targeting a production database.
        5. Non-empty destination check: Rejects restore into existing non-empty database unless
           allow_destructive_clean=True with confirm_destructive_clean_database_name matching the target.
        """
        backup_path = Path(backup_path).resolve()
        if not backup_path.exists():
            raise BackupError(f"Backup file does not exist: {backup_path}")
        if not self.verify_backup(backup_path):
            raise BackupError(f"Backup artifact failed integrity verification: {backup_path}")

        dest_str = str(target_destination).strip() if target_destination is not None else ""
        if not dest_str:
            raise BackupError(
                "Target restore destination cannot be empty. "
                "An explicit target destination database name or connection URL is required."
            )

        # Parse and normalize destination database identity
        dest_ident = normalize_db_identity(dest_str, default_host=self.host, default_port=self.port)
        target_db = dest_ident["database"]
        if not target_db:
            raise BackupError("Cannot restore: target database name could not be determined from destination.")

        # 1. Active Source Database Overwrite Protection (with alias detection)
        if is_same_database_identity(self.source_identity, dest_ident):
            raise BackupError(
                f"Restoration into the active source database ('{target_db}' at {dest_ident['host']}:{dest_ident['port']}) "
                "is strictly prohibited to protect live application data from accidental corruption."
            )

        # 2. Production Database Protection
        if is_production_database_target(dest_ident, dest_str):
            raise BackupError(
                f"Restoration targeting production database ('{target_db}' at {dest_ident['host']}) is prohibited. "
                "Automated application restores must never target production environments."
            )

        # 3. Non-Empty Destination Protection
        if target_is_empty is False:
            if not allow_destructive_clean:
                raise BackupError(
                    f"Destination database '{target_db}' is not empty. Restoring into an existing non-empty database "
                    "without explicit destructive authorization is prohibited to prevent overwriting existing data. "
                    "Please restore into a freshly provisioned, empty database, or explicitly set "
                    "allow_destructive_clean=True with confirm_destructive_clean_database_name."
                )

        # 4. Destructive Clean Authorization Validation
        if allow_destructive_clean:
            if confirm_destructive_clean_database_name.lower().strip() != target_db:
                raise BackupError(
                    f"Destructive clean authorization failed: confirm_destructive_clean_database_name "
                    f"('{confirm_destructive_clean_database_name}') does not match target database ('{target_db}')."
                )

        return True

    def restore(
        self,
        backup_path: Path,
        target_destination: Union[str, Path],
        overwrite: bool = False,
        allow_destructive_clean: bool = False,
        confirm_destructive_clean_database_name: str = "",
        clean: bool = False,
        target_is_empty: Optional[bool] = None,
        executor: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Restore a PostgreSQL database from a custom-format backup artifact using pg_restore.

        SAFETY CONTROLS:
        1. Explicit Target Validation: Requires explicit, non-empty destination database.
        2. Active Source Database Protection: Rejects restoring over the active source database,
           even if addressed via alternate host/URL aliases (127.0.0.1, localhost, casing).
        3. Production Rejection: Rejects any restoration targeting production databases.
        4. Non-Destructive by Default: Does NOT pass --clean (-c) by default. Dropping existing
           objects requires explicit allow_destructive_clean=True with exact database name confirmation.
        5. Credential Isolation: PGPASSWORD passed strictly via isolated subprocess environment;
           passwords NEVER appear in command line arguments or logs.
        6. Output Sanitization: Stderr and exceptions are filtered through sanitize_text().
        7. Failure Cleanup Safety: Failed restores do not touch or destroy unrelated resources.

        Args:
            backup_path: Path to the .dump backup file.
            target_destination: Target database name or connection URL.
            overwrite: Whether to permit overwriting an active/existing database.
            allow_destructive_clean: Explicit opt-in to pass -c/--clean to pg_restore.
            confirm_destructive_clean_database_name: Must match target database name if clean requested.
            clean: Legacy parameter. If True, requires allow_destructive_clean authorization.
            target_is_empty: Optional pre-flight check indicating whether target database has tables.
            executor: Optional subprocess execution callable for unit testing.

        Returns:
            Dict containing restoration metadata (status, target_database, backup_file_path, tool).

        Raises:
            BackupError: If safety checks fail or pg_restore encounters an unrecoverable error.
            BackupToolNotFoundError: If pg_restore executable is missing from system PATH.
        """
        effective_clean = allow_destructive_clean or clean
        if clean and not allow_destructive_clean:
            dest_ident_pre = normalize_db_identity(str(target_destination), default_host=self.host, default_port=self.port)
            if confirm_destructive_clean_database_name.lower().strip() != dest_ident_pre["database"]:
                raise BackupError(
                    "Destructive clean (-c) requested but not explicitly authorized. "
                    "Passing --clean is dangerous and requires allow_destructive_clean=True "
                    "along with confirm_destructive_clean_database_name matching the target database."
                )

        self.validate_restore(
            backup_path=backup_path,
            target_destination=target_destination,
            overwrite=overwrite,
            target_is_empty=target_is_empty,
            allow_destructive_clean=effective_clean,
            confirm_destructive_clean_database_name=confirm_destructive_clean_database_name,
        )

        backup_path = Path(backup_path).resolve()
        dest_str = str(target_destination).strip()
        dest_ident = normalize_db_identity(dest_str, default_host=self.host, default_port=self.port)

        target_host = dest_ident["host"]
        target_port = dest_ident["port"]
        target_db = dest_ident["database"]
        target_user = self.user
        target_password = self.password

        if "://" in dest_str:
            norm_dest = normalize_database_url(dest_str)
            parsed_dest = make_url(norm_dest)
            target_user = parsed_dest.username or target_user
            target_password = parsed_dest.password or target_password

        resolved_restore = self._resolve_tool(self.pg_restore_cmd)
        if not resolved_restore and not executor:
            raise BackupToolNotFoundError(
                f"PostgreSQL restore tool '{self.pg_restore_cmd}' was not found on system PATH. "
                "Please install PostgreSQL client utilities (pg_restore) to enable automated restoration."
            )

        cmd = [self.pg_restore_cmd]
        if target_host:
            cmd.extend(["-h", target_host])
        if target_port:
            cmd.extend(["-p", str(target_port)])
        if target_user:
            cmd.extend(["-U", target_user])
        cmd.extend(["-d", target_db, "--no-owner", "--no-privileges"])

        # Destructive clean is ONLY added if explicitly authorized and confirmed
        if effective_clean:
            cmd.append("-c")

        cmd.append(str(backup_path))

        sub_env = os.environ.copy()
        if target_password:
            sub_env["PGPASSWORD"] = target_password

        try:
            if executor:
                res = executor(cmd, env=sub_env, backup_path=backup_path, target_db=target_db)
                if hasattr(res, "returncode") and res.returncode > 1:
                    clean_err = sanitize_text(str(getattr(res, "stderr", "")), target_password)
                    raise BackupError(f"pg_restore failed with exit code {res.returncode}: {clean_err}")
            else:
                proc = subprocess.run(
                    cmd,
                    env=sub_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                if proc.returncode > 1:
                    clean_err = sanitize_text(proc.stderr, target_password)
                    raise BackupError(f"pg_restore failed with exit code {proc.returncode}: {clean_err}")
        except FileNotFoundError:
            raise BackupToolNotFoundError(
                f"PostgreSQL restore executable '{self.pg_restore_cmd}' could not be executed."
            )
        except Exception as e:
            if not isinstance(e, (BackupError, BackupToolNotFoundError)):
                raise BackupError(f"pg_restore execution failed: {sanitize_text(str(e), target_password)}") from e
            raise

        return {
            "status": "restored",
            "target_database": target_db,
            "backup_file_path": str(backup_path),
            "clean_enabled": effective_clean,
            "tool": self.pg_restore_cmd,
        }


def get_backup_adapter(
    target: Union[str, Path, Engine],
    **kwargs: Any,
) -> BaseBackupAdapter:
    """Factory creating a dialect-appropriate backup adapter.

    Args:
        target: SQLite file Path, SQLite/PostgreSQL connection URL, or SQLAlchemy Engine.
        **kwargs: Additional configuration parameters passed to adapter constructors.

    Returns:
        SQLiteBackupAdapter or PostgreSQLBackupAdapter.
    """
    if isinstance(target, Engine):
        dialect = target.dialect.name
        if dialect == "sqlite":
            db_path = target.url.database or "campus_automation.db"
            return SQLiteBackupAdapter(db_path)
        elif dialect == "postgresql":
            return PostgreSQLBackupAdapter(str(target.url), **kwargs)
        else:
            raise ValueError(
                f"Unsupported database dialect '{dialect}' for backup adapter. "
                "Supported dialects: 'sqlite', 'postgresql'."
            )

    target_str = str(target)
    if target_str.startswith("sqlite://"):
        parsed = make_url(target_str)
        return SQLiteBackupAdapter(parsed.database or "campus_automation.db")
    elif target_str.startswith("postgres://") or target_str.startswith("postgresql"):
        return PostgreSQLBackupAdapter(target_str, **kwargs)
    elif Path(target_str).suffix in (".db", ".sqlite", ".sqlite3") or not ("://" in target_str):
        return SQLiteBackupAdapter(Path(target_str))
    else:
        raise ValueError(
            f"Cannot determine database backup adapter for target '{sanitize_text(target_str)}'."
        )


# Backward-compatible functional entrypoints preserved for existing callers and tests
def backup_sqlite_database(
    source_db_path: Path,
    backup_dir: Path,
    prefix: str = "backup",
    overwrite: bool = False,
) -> Tuple[Path, str]:
    """Create a consistent snapshot backup of a SQLite database using the SQLite Backup API.

    Backward-compatible functional wrapper returning (Path, sha256_checksum).
    """
    adapter = SQLiteBackupAdapter(source_db_path)
    target_path, manifest = adapter.create_backup(backup_dir, prefix=prefix, overwrite=overwrite)
    return target_path, manifest.sha256_checksum


def restore_sqlite_database(
    backup_path: Path,
    target_db_path: Path,
    overwrite: bool = False,
) -> None:
    """Restore a SQLite database from a verified backup file using the SQLite Backup API.

    Backward-compatible functional wrapper.
    """
    adapter = SQLiteBackupAdapter(target_db_path)
    adapter.restore(backup_path, target_db_path, overwrite=overwrite)
