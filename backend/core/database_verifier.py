"""Database verification, migration readiness classification, and schema drift protection.

Provides rigorous, read-only validation of database structure against expected
SQLAlchemy models and Alembic revision state, distinguishing five distinct database states:
1. Fresh database (State A)
2. Migrated database (State B)
3. Compatible but unstamped legacy database (State C)
4. Incompatible database (State D)
5. Unknown or inconsistent Alembic revision (State E)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import sqlite3
from sqlalchemy import inspect, UniqueConstraint
from sqlalchemy.engine import Engine
from backend.database import Base
import backend.models  # Ensure all models are registered


class DatabaseReadinessStatus(str, Enum):
    """The five operational states of the database schema and migration state."""
    FRESH = "fresh"  # State A: No application tables and no Alembic revision
    MIGRATED = "migrated"  # State B: Required schema is present and Alembic revision is recognized
    COMPATIBLE_UNSTAMPED = "compatible_unstamped"  # State C: Required schema matches baseline, but alembic_version is absent
    INCOMPATIBLE = "incompatible"  # State D: Missing tables, missing columns, incompatible types, or constraint/index mismatches
    UNKNOWN_REVISION = "unknown_revision"  # State E: alembic_version table exists with an unknown or inconsistent revision


# Canonical recognized revisions established by the repository
KNOWN_REVISIONS: Set[str] = {"0001_initial_baseline"}


def get_type_family(type_obj: Any) -> str:
    """Normalize SQLAlchemy or DBAPI column types to canonical type families."""
    t_str = str(type_obj).upper()
    if any(k in t_str for k in ["INT", "SERIAL"]):
        return "INTEGER"
    if any(k in t_str for k in ["CHAR", "VARCHAR", "TEXT", "STRING"]):
        return "STRING"
    if any(k in t_str for k in ["BOOL"]):
        return "BOOLEAN"
    if any(k in t_str for k in ["DATE", "TIME"]):
        return "DATETIME"
    if any(k in t_str for k in ["FLOAT", "NUMERIC", "DECIMAL", "REAL", "DOUBLE"]):
        return "FLOAT"
    return t_str


@dataclass
class VerificationReport:
    """Detailed structural schema comparison report."""
    is_valid: bool
    can_stamp: bool
    missing_tables: List[str] = field(default_factory=list)
    unexpected_tables: List[str] = field(default_factory=list)
    missing_columns: Dict[str, List[str]] = field(default_factory=dict)
    type_mismatches: List[Dict[str, str]] = field(default_factory=list)
    missing_pks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    missing_fks: Dict[str, List[str]] = field(default_factory=dict)
    missing_unique_constraints: Dict[str, List[str]] = field(default_factory=dict)
    missing_indexes: Dict[str, List[str]] = field(default_factory=dict)
    nullability_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    integrity_status: str = "unknown"
    foreign_key_violations: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ReadinessReport:
    """Operational database readiness classification report for application startup."""
    status: DatabaseReadinessStatus
    can_start: bool
    summary: str
    action_required: str
    revision: Optional[str] = None
    missing_tables: List[str] = field(default_factory=list)
    unexpected_tables: List[str] = field(default_factory=list)
    missing_columns: Dict[str, List[str]] = field(default_factory=dict)
    type_mismatches: List[Dict[str, str]] = field(default_factory=list)
    missing_pks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    missing_fks: Dict[str, List[str]] = field(default_factory=dict)
    missing_unique_constraints: Dict[str, List[str]] = field(default_factory=dict)
    missing_indexes: Dict[str, List[str]] = field(default_factory=dict)
    nullability_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    integrity_status: str = "unknown"
    foreign_key_violations: List[str] = field(default_factory=list)


class DatabaseVerifier:
    """Verifies schema conformance against Base.metadata and classifies migration readiness."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.target_metadata = Base.metadata

    def _inspect_structural_details(self, inspector, existing_tables: Set[str], expected_tables: Set[str]):
        """Perform comprehensive inspection of tables, columns, types, nullability, PKs, FKs, and indexes."""
        missing_tables = sorted(list(expected_tables - existing_tables))
        unexpected_tables = sorted(list(existing_tables - expected_tables - {"alembic_version", "sqlite_sequence"}))

        missing_columns: Dict[str, List[str]] = {}
        type_mismatches: List[Dict[str, str]] = []
        nullability_mismatches: List[Dict[str, Any]] = []
        missing_pks: Dict[str, Dict[str, Any]] = {}
        missing_fks: Dict[str, List[str]] = {}
        missing_unique_constraints: Dict[str, List[str]] = {}
        missing_indexes: Dict[str, List[str]] = {}

        # Allow backward-compatibility for historical legacy databases where non-unique secondary
        # lookup indexes were not present at initial table creation.
        LEGACY_OPTIONAL_INDEXES = {
            ("attendance", "ix_attendance_faculty_id"),
            ("attendance", "ix_attendance_subject_code"),
        }

        for table_name in expected_tables.intersection(existing_tables):
            table = self.target_metadata.tables[table_name]
            actual_cols_list = inspector.get_columns(table_name)
            actual_cols = {col["name"]: col for col in actual_cols_list}

            # 1. Missing columns
            expected_col_names = {c.name for c in table.columns}
            actual_col_names = set(actual_cols.keys())
            diff = expected_col_names - actual_col_names
            if diff:
                missing_columns[table_name] = sorted(list(diff))

            # 2. Column types & nullability
            for col in table.columns:
                if col.name in actual_cols:
                    act_col = actual_cols[col.name]
                    exp_family = get_type_family(col.type)
                    act_family = get_type_family(act_col["type"])

                    # SQLite compatibility rule: Boolean is represented as INTEGER
                    is_bool_compatible = exp_family == "BOOLEAN" and act_family in ("BOOLEAN", "INTEGER")
                    if exp_family != act_family and not is_bool_compatible:
                        type_mismatches.append({
                            "table": table_name,
                            "column": col.name,
                            "expected_type": exp_family,
                            "actual_type": act_family,
                        })

                    # Nullability: If model explicitly requires NOT NULL, actual column must not be nullable
                    if col.nullable is False and act_col.get("nullable") is True:
                        nullability_mismatches.append({
                            "table": table_name,
                            "column": col.name,
                            "expected_nullable": False,
                            "actual_nullable": True,
                        })

            # 3. Primary Key constraints
            exp_pk = sorted([c.name for c in table.primary_key.columns])
            act_pk = sorted(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
            if exp_pk != act_pk:
                missing_pks[table_name] = {"expected": exp_pk, "actual": act_pk}

            # 4. Foreign Key definitions
            exp_fks = {(fk.parent.name, fk.column.table.name, fk.column.name) for fk in table.foreign_keys}
            act_fks = set()
            for fk_dict in inspector.get_foreign_keys(table_name):
                p_cols = fk_dict.get("constrained_columns") or []
                r_table = fk_dict.get("referred_table")
                r_cols = fk_dict.get("referred_columns") or []
                for p, r in zip(p_cols, r_cols):
                    act_fks.add((p, r_table, r))
            if not exp_fks.issubset(act_fks):
                missing_fks[table_name] = sorted([f"{p} -> {r_t}.{r_c}" for (p, r_t, r_c) in (exp_fks - act_fks)])

            # 5. Unique constraints
            act_uniques = inspector.get_unique_constraints(table_name)
            act_indexes = inspector.get_indexes(table_name)
            act_unique_cols = {tuple(sorted(u.get("column_names") or [])) for u in act_uniques}
            for idx in act_indexes:
                if idx.get("unique"):
                    act_unique_cols.add(tuple(sorted(idx.get("column_names") or [])))

            # Table-level unique constraints
            for const in table.constraints:
                if isinstance(const, UniqueConstraint):
                    u_cols = tuple(sorted([c.name for c in const.columns]))
                    if u_cols not in act_unique_cols:
                        missing_unique_constraints.setdefault(table_name, []).append(f"unique({', '.join(u_cols)})")

            # Column-level unique constraints
            for col in table.columns:
                if col.unique:
                    col_tuple = (col.name,)
                    if col_tuple not in act_unique_cols:
                        missing_unique_constraints.setdefault(table_name, []).append(f"unique({col.name})")

            # Unique indexes
            for exp_idx in table.indexes:
                if exp_idx.unique:
                    exp_cols = tuple(sorted([c.name for c in exp_idx.columns]))
                    if exp_cols not in act_unique_cols:
                        missing_unique_constraints.setdefault(table_name, []).append(f"unique({', '.join(exp_cols)})")

            # 6. Important indexes (declared non-unique model indexes)
            act_idx_cols = {tuple(sorted(idx.get("column_names") or [])) for idx in act_indexes}
            for exp_idx in table.indexes:
                if not exp_idx.unique:
                    exp_cols = tuple(sorted([c.name for c in exp_idx.columns]))
                    if (table_name, exp_idx.name) not in LEGACY_OPTIONAL_INDEXES:
                        if exp_cols not in act_idx_cols:
                            missing_indexes.setdefault(table_name, []).append(f"index({', '.join(exp_cols)})")

        # SQLite integrity check and foreign key violation check
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

        return (
            missing_tables,
            unexpected_tables,
            missing_columns,
            type_mismatches,
            nullability_mismatches,
            missing_pks,
            missing_fks,
            missing_unique_constraints,
            missing_indexes,
            integrity_status,
            foreign_key_violations,
        )

    def verify_schema(self) -> VerificationReport:
        """Perform a rigorous schema comparison against Base.metadata.

        Returns:
            VerificationReport with detailed diagnostics.
        """
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())
        expected_tables = set(self.target_metadata.tables.keys())

        (
            missing_tables,
            unexpected_tables,
            missing_columns,
            type_mismatches,
            nullability_mismatches,
            missing_pks,
            missing_fks,
            missing_unique_constraints,
            missing_indexes,
            integrity_status,
            foreign_key_violations,
        ) = self._inspect_structural_details(inspector, existing_tables, expected_tables)

        is_valid = (
            len(missing_tables) == 0
            and len(missing_columns) == 0
            and len(type_mismatches) == 0
            and len(missing_pks) == 0
            and len(missing_fks) == 0
            and len(missing_unique_constraints) == 0
            and len(missing_indexes) == 0
            and integrity_status == "ok"
            and len(foreign_key_violations) == 0
        )

        can_stamp = is_valid and ("alembic_version" not in existing_tables)

        if not is_valid:
            diagnostics = []
            if missing_tables:
                diagnostics.append(f"missing {len(missing_tables)} tables")
            if missing_columns:
                diagnostics.append(f"{len(missing_columns)} tables with missing columns")
            if type_mismatches:
                diagnostics.append(f"{len(type_mismatches)} type mismatches")
            if missing_pks:
                diagnostics.append(f"{len(missing_pks)} PK mismatches")
            if missing_fks:
                diagnostics.append(f"{len(missing_fks)} FK mismatches")
            if missing_unique_constraints:
                diagnostics.append(f"{len(missing_unique_constraints)} unique constraint mismatches")
            if missing_indexes:
                diagnostics.append(f"{len(missing_indexes)} index mismatches")
            if integrity_status != "ok":
                diagnostics.append(f"integrity: {integrity_status}")
            if foreign_key_violations:
                diagnostics.append(f"FK violations: {len(foreign_key_violations)}")
            summary = f"Schema mismatch: {', '.join(diagnostics)}."
        elif not can_stamp:
            summary = "Schema matches baseline, but database is already versioned (alembic_version present)."
        else:
            summary = "Schema fully matches 22-model baseline and is eligible for safe baseline stamping."

        return VerificationReport(
            is_valid=is_valid,
            can_stamp=can_stamp,
            missing_tables=missing_tables,
            unexpected_tables=unexpected_tables,
            missing_columns=missing_columns,
            type_mismatches=type_mismatches,
            missing_pks=missing_pks,
            missing_fks=missing_fks,
            missing_unique_constraints=missing_unique_constraints,
            missing_indexes=missing_indexes,
            nullability_mismatches=nullability_mismatches,
            integrity_status=integrity_status,
            foreign_key_violations=foreign_key_violations,
            summary=summary,
        )

    def check_readiness(self) -> ReadinessReport:
        """Classify database readiness into one of five distinct operational states.

        Returns:
            ReadinessReport with actionable startup diagnostics.
        """
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())
        expected_tables = set(self.target_metadata.tables.keys())
        has_alembic = "alembic_version" in existing_tables
        domain_existing = existing_tables.intersection(expected_tables)

        # Query alembic_version revision if table exists
        current_revision: Optional[str] = None
        if has_alembic:
            try:
                with self.engine.connect() as conn:
                    rows = conn.exec_driver_sql("SELECT version_num FROM alembic_version;").fetchall()
                    if rows and rows[0][0]:
                        current_revision = str(rows[0][0])
            except Exception:
                current_revision = None

        # State A: Fresh Database
        if len(domain_existing) == 0 and not has_alembic:
            return ReadinessReport(
                status=DatabaseReadinessStatus.FRESH,
                can_start=False,
                summary=f"Database schema is incomplete: missing required tables {sorted(list(expected_tables))} (fresh database detected).",
                action_required="Execute 'alembic upgrade head' to initialize the database schema.",
                missing_tables=sorted(list(expected_tables)),
            )

        # State E: Unknown or inconsistent Alembic revision
        if has_alembic:
            if not current_revision or current_revision not in KNOWN_REVISIONS:
                return ReadinessReport(
                    status=DatabaseReadinessStatus.UNKNOWN_REVISION,
                    can_start=False,
                    revision=current_revision,
                    summary=f"Database has unknown or inconsistent Alembic revision: '{current_revision}'.",
                    action_required=(
                        f"Verify migration history. Expected recognized revisions: {sorted(list(KNOWN_REVISIONS))}. "
                        "Do not start application with unrecognized database revision."
                    ),
                )

        # Inspect structural schema details
        (
            missing_tables,
            unexpected_tables,
            missing_columns,
            type_mismatches,
            nullability_mismatches,
            missing_pks,
            missing_fks,
            missing_unique_constraints,
            missing_indexes,
            integrity_status,
            foreign_key_violations,
        ) = self._inspect_structural_details(inspector, existing_tables, expected_tables)

        is_structurally_compatible = (
            len(missing_tables) == 0
            and len(missing_columns) == 0
            and len(type_mismatches) == 0
            and len(missing_pks) == 0
            and len(missing_fks) == 0
            and len(missing_unique_constraints) == 0
            and len(missing_indexes) == 0
            and integrity_status == "ok"
            and len(foreign_key_violations) == 0
        )

        # State D: Incompatible Database
        if not is_structurally_compatible:
            diagnostics = []
            if missing_tables:
                diagnostics.append(f"missing required tables: {missing_tables}")
            if missing_columns:
                diagnostics.append(f"missing columns: {missing_columns}")
            if type_mismatches:
                diagnostics.append(f"type mismatches: {type_mismatches}")
            if missing_pks:
                diagnostics.append(f"missing PKs: {missing_pks}")
            if missing_fks:
                diagnostics.append(f"missing FKs: {missing_fks}")
            if missing_unique_constraints:
                diagnostics.append(f"missing unique constraints: {missing_unique_constraints}")
            if missing_indexes:
                diagnostics.append(f"missing indexes: {missing_indexes}")
            if integrity_status != "ok":
                diagnostics.append(f"integrity check: {integrity_status}")
            if foreign_key_violations:
                diagnostics.append(f"FK violations: {len(foreign_key_violations)}")

            if missing_tables:
                summary = f"Database schema is incomplete: {'; '.join(diagnostics)}."
            else:
                summary = f"Database schema is structurally incompatible: {'; '.join(diagnostics)}."

            action_required = (
                "Resolve schema drift or apply missing migrations using 'alembic upgrade head'. "
                "Automatic database repair on startup is prohibited."
            )

            return ReadinessReport(
                status=DatabaseReadinessStatus.INCOMPATIBLE,
                can_start=False,
                revision=current_revision,
                missing_tables=missing_tables,
                unexpected_tables=unexpected_tables,
                missing_columns=missing_columns,
                type_mismatches=type_mismatches,
                nullability_mismatches=nullability_mismatches,
                missing_pks=missing_pks,
                missing_fks=missing_fks,
                missing_unique_constraints=missing_unique_constraints,
                missing_indexes=missing_indexes,
                integrity_status=integrity_status,
                foreign_key_violations=foreign_key_violations,
                summary=summary,
                action_required=action_required,
            )

        # State B: Migrated Database
        if has_alembic and current_revision in KNOWN_REVISIONS:
            return ReadinessReport(
                status=DatabaseReadinessStatus.MIGRATED,
                can_start=True,
                revision=current_revision,
                unexpected_tables=unexpected_tables,
                integrity_status=integrity_status,
                summary=f"Database is correctly migrated to recognized revision '{current_revision}'.",
                action_required="None. Database schema is fully compatible and versioned.",
            )

        # State C: Compatible but Unstamped Legacy Database
        return ReadinessReport(
            status=DatabaseReadinessStatus.COMPATIBLE_UNSTAMPED,
            can_start=True,
            revision=None,
            unexpected_tables=unexpected_tables,
            integrity_status=integrity_status,
            summary=(
                "Database schema is structurally compatible with baseline '0001_initial_baseline', "
                "but alembic_version is absent (legacy unstamped database)."
            ),
            action_required=(
                "Authorized baseline adoption required: verify backup and execute "
                "'alembic stamp 0001_initial_baseline' during a scheduled maintenance window. "
                "Automatic stamping is prohibited."
            ),
        )
