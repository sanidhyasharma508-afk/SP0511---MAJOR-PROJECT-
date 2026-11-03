"""Database verification and baseline validation utility.

Validates that an existing database strictly matches the expected SQLAlchemy
metadata schema before any baseline stamping or migration operation is permitted.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import sqlite3
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from backend.database import Base
import backend.models  # Ensure all models are registered


@dataclass
class VerificationReport:
    is_valid: bool
    can_stamp: bool
    missing_tables: List[str] = field(default_factory=list)
    unexpected_tables: List[str] = field(default_factory=list)
    missing_columns: Dict[str, List[str]] = field(default_factory=dict)
    integrity_status: str = "unknown"
    foreign_key_violations: List[str] = field(default_factory=list)
    summary: str = ""


class DatabaseVerifier:
    """Verifies schema conformance against Base.metadata."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.target_metadata = Base.metadata

    def verify_schema(self) -> VerificationReport:
        """Perform a rigorous schema comparison against Base.metadata.

        Returns:
            VerificationReport with detailed diagnostics.
        """
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())
        expected_tables = set(self.target_metadata.tables.keys())

        missing_tables = list(expected_tables - existing_tables)
        unexpected_tables = list(existing_tables - expected_tables - {"alembic_version", "sqlite_sequence"})

        missing_columns: Dict[str, List[str]] = {}
        for table_name in expected_tables.intersection(existing_tables):
            expected_cols = {c.name for c in self.target_metadata.tables[table_name].columns}
            actual_cols = {col["name"] for col in inspector.get_columns(table_name)}
            diff = expected_cols - actual_cols
            if diff:
                missing_columns[table_name] = sorted(list(diff))

        # Check SQLite-specific integrity and foreign keys if applicable
        integrity_status = "ok"
        foreign_key_violations: List[str] = []

        if self.engine.dialect.name == "sqlite":
            with self.engine.connect() as conn:
                try:
                    res = conn.exec_driver_sql("PRAGMA integrity_check;").fetchall()
                    if res and res[0][0] != "ok":
                        integrity_status = str(res)
                except Exception as e:
                    integrity_status = f"error: {e}"

                try:
                    fk_res = conn.exec_driver_sql("PRAGMA foreign_key_check;").fetchall()
                    if fk_res:
                        foreign_key_violations = [str(r) for r in fk_res]
                except Exception as e:
                    foreign_key_violations.append(f"error: {e}")

        # Stamping criteria: All 22 tables present, no missing columns, integrity check passed, no FK violations
        is_valid = (
            len(missing_tables) == 0
            and len(missing_columns) == 0
            and integrity_status == "ok"
            and len(foreign_key_violations) == 0
        )

        can_stamp = is_valid and ("alembic_version" not in existing_tables)

        if not is_valid:
            summary = (
                f"Schema mismatch: missing {len(missing_tables)} tables, "
                f"{len(missing_columns)} tables with missing columns. "
                f"Integrity: {integrity_status}. FK violations: {len(foreign_key_violations)}."
            )
        elif not can_stamp:
            summary = "Schema matches baseline, but database is already versioned (alembic_version present)."
        else:
            summary = "Schema fully matches 22-model baseline and is eligible for safe baseline stamping."

        return VerificationReport(
            is_valid=is_valid,
            can_stamp=can_stamp,
            missing_tables=sorted(missing_tables),
            unexpected_tables=sorted(unexpected_tables),
            missing_columns=missing_columns,
            integrity_status=integrity_status,
            foreign_key_violations=foreign_key_violations,
            summary=summary,
        )
