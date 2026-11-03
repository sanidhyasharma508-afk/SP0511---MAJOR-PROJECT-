"""SQLite database backup and restoration utility.

Uses the official SQLite Online Backup API (sqlite3.backup) to create
consistent point-in-time snapshots of SQLite databases, safe under active WAL mode.
"""

import os
import sqlite3
import datetime
import hashlib
from pathlib import Path
from typing import Tuple


class BackupError(Exception):
    """Raised when backup or restore fails validation."""
    pass


def backup_sqlite_database(
    source_db_path: Path,
    backup_dir: Path,
    prefix: str = "backup",
    overwrite: bool = False,
) -> Tuple[Path, str]:
    """Create a consistent snapshot backup of a SQLite database using the SQLite Backup API.

    Args:
        source_db_path: Path to the active SQLite database file.
        backup_dir: Target directory where backups are stored.
        prefix: Prefix for the generated backup filename.
        overwrite: If False, raises BackupError if the destination file already exists.

    Returns:
        Tuple of (Path to backup file, SHA256 checksum of backup).

    Raises:
        BackupError: If source does not exist, backup fails, or integrity check fails.
    """
    source_db_path = Path(source_db_path).resolve()
    backup_dir = Path(backup_dir).resolve()

    if not source_db_path.exists():
        raise BackupError(f"Source database file does not exist: {source_db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{prefix}_{timestamp}_{source_db_path.name}"
    target_path = backup_dir / backup_filename

    if target_path.exists() and not overwrite:
        raise BackupError(f"Destination backup file already exists and overwrite=False: {target_path}")

    # Use URI read-only connection for source to avoid locking active writers
    source_uri = f"file:{source_db_path.as_posix()}?mode=ro"
    try:
        source_conn = sqlite3.connect(source_uri, uri=True)
    except Exception:
        # Fallback to standard connect if URI mode fails
        source_conn = sqlite3.connect(str(source_db_path))

    target_conn = sqlite3.connect(str(target_path))

    try:
        # Execute official SQLite online backup
        source_conn.backup(target_conn)
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise BackupError(f"SQLite backup operation failed: {e}") from e
    finally:
        source_conn.close()
        target_conn.close()

    # Perform post-backup integrity check on destination file
    verify_conn = sqlite3.connect(str(target_path))
    try:
        cursor = verify_conn.cursor()
        res = cursor.execute("PRAGMA integrity_check;").fetchall()
        if not res or res[0][0] != "ok":
            if target_path.exists():
                target_path.unlink()
            raise BackupError(f"Backup verification failed: integrity_check returned {res}")
    finally:
        verify_conn.close()

    # Compute SHA-256 hash
    hasher = hashlib.sha256()
    with open(target_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    checksum = hasher.hexdigest()

    return target_path, checksum


def restore_sqlite_database(
    backup_path: Path,
    target_db_path: Path,
    overwrite: bool = False,
) -> None:
    """Restore a SQLite database from a verified backup file using the SQLite Backup API.

    Args:
        backup_path: Path to the backup file.
        target_db_path: Path to restore to.
        overwrite: Whether to overwrite existing target file.

    Raises:
        BackupError: If backup file is invalid or restore fails.
    """
    backup_path = Path(backup_path).resolve()
    target_db_path = Path(target_db_path).resolve()

    if not backup_path.exists():
        raise BackupError(f"Backup file does not exist: {backup_path}")

    if target_db_path.exists() and not overwrite:
        raise BackupError(f"Target database already exists and overwrite=False: {target_db_path}")

    # Verify backup integrity before restoring
    test_conn = sqlite3.connect(str(backup_path))
    try:
        res = test_conn.cursor().execute("PRAGMA integrity_check;").fetchall()
        if not res or res[0][0] != "ok":
            raise BackupError(f"Cannot restore: backup file failed integrity check ({res})")
    finally:
        test_conn.close()

    # Perform restoration via Backup API
    source_conn = sqlite3.connect(str(backup_path))
    dest_conn = sqlite3.connect(str(target_db_path))
    try:
        source_conn.backup(dest_conn)
    except Exception as e:
        raise BackupError(f"Restore operation failed: {e}") from e
    finally:
        source_conn.close()
        dest_conn.close()
