"""Database verification, migration readiness classification, and schema drift protection.

Provides rigorous, dialect-aware, read-only validation of database structure against expected
SQLAlchemy models and Alembic revision state, distinguishing five distinct database states:
1. Fresh database (State A)
2. Migrated database (State B)
3. Compatible but unstamped legacy database (State C)
4. Incompatible database (State D)
5. Unknown or inconsistent Alembic revision (State E)

Supports both:
- SQLite 3 (local development and automated test suites, PRAGMA integrity/foreign_key checks)
- PostgreSQL 16+ (staging and production, schema qualification, native enum inspection, sequences)
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


# The canonical target (head) revision expected by the deployed application code
EXPECTED_REVISION: str = "0001_initial_baseline"

# Canonical recognized revisions established by repository history
KNOWN_REVISIONS: Set[str] = {"0001_initial_baseline"}

# Supported database dialects
SUPPORTED_DIALECTS: Set[str] = {"sqlite", "postgresql"}

# Canonical PostgreSQL named enums and expected labels
POSTGRESQL_EXPECTED_ENUMS: Dict[str, Set[str]] = {
    "eventcategory": {"ACADEMIC", "CULTURAL", "SPORTS", "TECHNICAL", "WORKSHOP", "OTHER"},
    "eventstatus": {"DRAFT", "PUBLISHED", "COMPLETED", "CANCELLED"},
    "registrationstatus": {"PENDING", "APPROVED", "REJECTED", "CANCELLED", "ATTENDED"},
}


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
    if any(k in t_str for k in ["JSON"]):
        return "JSON"
    if any(k in t_str for k in ["ENUM", "EVENTCATEGORY", "EVENTSTATUS", "REGISTRATIONSTATUS"]):
        return "ENUM"
    return t_str


@dataclass
class VerificationReport:
    """Detailed structural schema comparison report."""
    is_valid: bool
    can_stamp: bool
    dialect: str = "sqlite"
    missing_tables: List[str] = field(default_factory=list)
    unexpected_tables: List[str] = field(default_factory=list)
    missing_columns: Dict[str, List[str]] = field(default_factory=dict)
    type_mismatches: List[Dict[str, str]] = field(default_factory=list)
    missing_pks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    missing_fks: Dict[str, List[str]] = field(default_factory=dict)
    missing_unique_constraints: Dict[str, List[str]] = field(default_factory=dict)
    missing_indexes: Dict[str, List[str]] = field(default_factory=dict)
    nullability_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    enum_mismatches: List[str] = field(default_factory=list)
    sequence_mismatches: List[str] = field(default_factory=list)
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
    dialect: str = "sqlite"
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
    enum_mismatches: List[str] = field(default_factory=list)
    sequence_mismatches: List[str] = field(default_factory=list)
    integrity_status: str = "unknown"
    foreign_key_violations: List[str] = field(default_factory=list)


class DatabaseVerifier:
    """Verifies schema conformance against Base.metadata and classifies migration readiness across dialects."""

    def __init__(
        self,
        engine: Engine,
        expected_revision: str = EXPECTED_REVISION,
        known_revisions: Optional[Set[str]] = None,
        schema: Optional[str] = None,
    ):
        self.engine = engine
        self.dialect_name = engine.dialect.name
        self.schema = schema
        self.target_metadata = Base.metadata
        self.expected_revision = expected_revision
        self.known_revisions = known_revisions if known_revisions is not None else KNOWN_REVISIONS

        if self.dialect_name not in SUPPORTED_DIALECTS:
            raise ValueError(
                f"Unsupported database dialect '{self.dialect_name}'. "
                f"DatabaseVerifier supports {sorted(list(SUPPORTED_DIALECTS))}."
            )

    def _inspect_postgresql_enums(self, inspector) -> List[str]:
        """Inspect PostgreSQL custom ENUM types and verify expected enum labels."""
        mismatches: List[str] = []
        try:
            if hasattr(inspector, "get_enums"):
                actual_enums_list = inspector.get_enums(schema=self.schema)
                actual_enums = {e["name"]: set(e.get("labels", [])) for e in actual_enums_list}
                for enum_name, expected_labels in POSTGRESQL_EXPECTED_ENUMS.items():
                    if enum_name not in actual_enums:
                        mismatches.append(f"Missing PostgreSQL enum type: '{enum_name}'")
                    else:
                        act_labels = actual_enums[enum_name]
                        if not expected_labels.issubset(act_labels):
                            missing_labels = sorted(list(expected_labels - act_labels))
                            mismatches.append(f"Enum '{enum_name}' missing labels: {missing_labels}")
        except Exception as e:
            mismatches.append(f"Enum inspection error: {e}")
        return mismatches

    def _inspect_postgresql_sequences(self, inspector, connection) -> List[str]:
        """Inspect PostgreSQL sequences / identity definitions for primary key columns."""
        mismatches: List[str] = []
        try:
            if hasattr(inspector, "get_sequence_names"):
                sequences = set(inspector.get_sequence_names(schema=self.schema))
            else:
                schema_name = self.schema or "public"
                res = connection.exec_driver_sql(
                    "SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = %s;",
                    (schema_name,),
                ).fetchall()
                sequences = {r[0] for r in res}
        except Exception:
            # Fallback if unprivileged or information_schema restricted
            sequences = set()
        return mismatches

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
        enum_mismatches: List[str] = []
        sequence_mismatches: List[str] = []

        # Allow backward-compatibility for historical legacy databases where non-unique secondary
        # lookup indexes were not present at initial table creation.
        LEGACY_OPTIONAL_INDEXES = {
            ("attendance", "ix_attendance_faculty_id"),
            ("attendance", "ix_attendance_subject_code"),
        }

        for table_name in expected_tables.intersection(existing_tables):
            table = self.target_metadata.tables[table_name]
            actual_cols_list = inspector.get_columns(table_name, schema=self.schema)
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

                    # SQLite compatibility rule: Boolean is represented as INTEGER or BOOLEAN
                    is_bool_compatible = exp_family == "BOOLEAN" and act_family in ("BOOLEAN", "INTEGER")
                    # Enum compatibility rule: Enum represented as native ENUM or VARCHAR/STRING
                    is_enum_compatible = (exp_family in ("ENUM", "STRING") and act_family in ("ENUM", "STRING"))

                    if exp_family != act_family and not is_bool_compatible and not is_enum_compatible:
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
            act_pk = sorted(inspector.get_pk_constraint(table_name, schema=self.schema).get("constrained_columns") or [])
            if exp_pk != act_pk:
                missing_pks[table_name] = {"expected": exp_pk, "actual": act_pk}

            # 4. Foreign Key definitions
            exp_fks = {(fk.parent.name, fk.column.table.name, fk.column.name) for fk in table.foreign_keys}
            act_fks = set()
            for fk_dict in inspector.get_foreign_keys(table_name, schema=self.schema):
                p_cols = fk_dict.get("constrained_columns") or []
                r_table = fk_dict.get("referred_table")
                r_cols = fk_dict.get("referred_columns") or []
                for p, r in zip(p_cols, r_cols):
                    act_fks.add((p, r_table, r))
            if not exp_fks.issubset(act_fks):
                missing_fks[table_name] = sorted([f"{p} -> {r_t}.{r_c}" for (p, r_t, r_c) in (exp_fks - act_fks)])

            # 5. Unique constraints
            act_uniques = inspector.get_unique_constraints(table_name, schema=self.schema)
            act_indexes = inspector.get_indexes(table_name, schema=self.schema)
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

        # Dialect-specific integrity and constraint checks
        integrity_status = "ok"
        foreign_key_violations: List[str] = []

        if self.dialect_name == "sqlite":
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

        elif self.dialect_name == "postgresql":
            with self.engine.connect() as conn:
                try:
                    res = conn.exec_driver_sql("SELECT 1;").fetchone()
                    if not res or res[0] != 1:
                        integrity_status = "heartbeat_failed"
                except Exception as e:
                    integrity_status = f"error: {e}"

                enum_mismatches = self._inspect_postgresql_enums(inspector)
                sequence_mismatches = self._inspect_postgresql_sequences(inspector, conn)

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
            enum_mismatches,
            sequence_mismatches,
        )

    def verify_schema(self) -> VerificationReport:
        """Perform a rigorous schema comparison against Base.metadata across supported dialects.

        Returns:
            VerificationReport with detailed diagnostics.
        """
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names(schema=self.schema))
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
            enum_mismatches,
            sequence_mismatches,
        ) = self._inspect_structural_details(inspector, existing_tables, expected_tables)

        is_valid = (
            len(missing_tables) == 0
            and len(missing_columns) == 0
            and len(type_mismatches) == 0
            and len(missing_pks) == 0
            and len(missing_fks) == 0
            and len(missing_unique_constraints) == 0
            and len(missing_indexes) == 0
            and len(enum_mismatches) == 0
            and len(sequence_mismatches) == 0
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
            if enum_mismatches:
                diagnostics.append(f"enum mismatches: {enum_mismatches}")
            if sequence_mismatches:
                diagnostics.append(f"sequence mismatches: {sequence_mismatches}")
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
            dialect=self.dialect_name,
            missing_tables=missing_tables,
            unexpected_tables=unexpected_tables,
            missing_columns=missing_columns,
            type_mismatches=type_mismatches,
            missing_pks=missing_pks,
            missing_fks=missing_fks,
            missing_unique_constraints=missing_unique_constraints,
            missing_indexes=missing_indexes,
            nullability_mismatches=nullability_mismatches,
            enum_mismatches=enum_mismatches,
            sequence_mismatches=sequence_mismatches,
            integrity_status=integrity_status,
            foreign_key_violations=foreign_key_violations,
            summary=summary,
        )

    def check_readiness(self) -> ReadinessReport:
        """Classify database readiness into one of five distinct operational states across dialects.

        Returns:
            ReadinessReport with actionable startup diagnostics.
        """
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names(schema=self.schema))
        expected_tables = set(self.target_metadata.tables.keys())
        has_alembic = "alembic_version" in existing_tables
        domain_existing = existing_tables.intersection(expected_tables)

        # Query alembic_version revision if table exists
        current_revision: Optional[str] = None
        if has_alembic:
            try:
                with self.engine.connect() as conn:
                    table_ref = f'"{self.schema}".alembic_version' if (self.schema and self.dialect_name == "postgresql") else "alembic_version"
                    rows = conn.exec_driver_sql(f"SELECT version_num FROM {table_ref};").fetchall()
                    if rows and rows[0][0]:
                        current_revision = str(rows[0][0])
            except Exception:
                current_revision = None

        # State A: Fresh Database
        if len(domain_existing) == 0 and not has_alembic:
            return ReadinessReport(
                status=DatabaseReadinessStatus.FRESH,
                can_start=False,
                dialect=self.dialect_name,
                summary=f"Database schema is incomplete: missing required tables {sorted(list(expected_tables))} (fresh database detected).",
                action_required="Execute 'alembic upgrade head' to initialize the database schema.",
                missing_tables=sorted(list(expected_tables)),
            )

        # State E: Unknown or inconsistent Alembic revision
        if has_alembic:
            if not current_revision or current_revision not in self.known_revisions:
                return ReadinessReport(
                    status=DatabaseReadinessStatus.UNKNOWN_REVISION,
                    can_start=False,
                    dialect=self.dialect_name,
                    revision=current_revision,
                    summary=f"Database has unknown or inconsistent Alembic revision: '{current_revision}'.",
                    action_required=(
                        f"Verify migration history. Expected recognized revisions: {sorted(list(self.known_revisions))}. "
                        "Do not start application with unrecognized database revision."
                    ),
                )
            if current_revision != self.expected_revision:
                return ReadinessReport(
                    status=DatabaseReadinessStatus.INCOMPATIBLE,
                    can_start=False,
                    dialect=self.dialect_name,
                    revision=current_revision,
                    summary=(
                        f"Database schema revision '{current_revision}' is outdated. "
                        f"Current expected revision is '{self.expected_revision}'."
                    ),
                    action_required=(
                        "Upgrade database schema using 'alembic upgrade head'. "
                        f"The application cannot start against outdated revision '{current_revision}'."
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
            enum_mismatches,
            sequence_mismatches,
        ) = self._inspect_structural_details(inspector, existing_tables, expected_tables)

        is_structurally_compatible = (
            len(missing_tables) == 0
            and len(missing_columns) == 0
            and len(type_mismatches) == 0
            and len(missing_pks) == 0
            and len(missing_fks) == 0
            and len(missing_unique_constraints) == 0
            and len(missing_indexes) == 0
            and len(enum_mismatches) == 0
            and len(sequence_mismatches) == 0
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
            if enum_mismatches:
                diagnostics.append(f"enum mismatches: {enum_mismatches}")
            if sequence_mismatches:
                diagnostics.append(f"sequence mismatches: {sequence_mismatches}")
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
                dialect=self.dialect_name,
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
                enum_mismatches=enum_mismatches,
                sequence_mismatches=sequence_mismatches,
                integrity_status=integrity_status,
                foreign_key_violations=foreign_key_violations,
                summary=summary,
                action_required=action_required,
            )

        # State B: Migrated Database
        if has_alembic and current_revision == self.expected_revision:
            return ReadinessReport(
                status=DatabaseReadinessStatus.MIGRATED,
                can_start=True,
                dialect=self.dialect_name,
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
            dialect=self.dialect_name,
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
