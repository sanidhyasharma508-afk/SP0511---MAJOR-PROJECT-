# Phase 19E — Dialect-Aware Database Verification & Backup Architecture

**Project:** Campus Automation System (MARVEL)  
**Workspace:** `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`  
**Target Dialects:** SQLite 3 (Dev/Test) and PostgreSQL 16+ (Staging/Production)  
**Mode:** Strict, Non-Destructive Implementation

---

## 1. Executive Summary

Phase 19E establishes a robust, dialect-aware database verification and backup architecture supporting both SQLite 3 and PostgreSQL 16+. 

Prior to this phase, `DatabaseVerifier` relied on SQLite-specific `PRAGMA integrity_check` and `PRAGMA foreign_key_check` queries that would fail against PostgreSQL engines, while `backup_utils.py` was tightly coupled to SQLite's C-level `sqlite3.backup` API without support for enterprise PostgreSQL backups.

In Phase 19E, both modules were refactored into modular, dialect-aware architectures:
1. **`DatabaseVerifier` (`backend/core/database_verifier.py`)**:
   - Detects the active database dialect (`sqlite` or `postgresql`) and rejects unsupported engines.
   - Preserves portable SQLAlchemy reflection across all 22 domain tables, columns, data types, nullability, primary keys, foreign keys, unique constraints, and indexes.
   - Isolates SQLite PRAGMA checks to SQLite engines only.
   - Introduces PostgreSQL connectivity heartbeat (`SELECT 1;`), schema qualification, custom native ENUM inspection (`eventcategory`, `eventstatus`, `registrationstatus`), and sequence reflection.
   - Retains 100% backward compatibility for the five canonical migration readiness states (`FRESH`, `MIGRATED`, `COMPATIBLE_UNSTAMPED`, `INCOMPATIBLE`, `UNKNOWN_REVISION`).
2. **Modular Backup Architecture (`backend/core/backup_utils.py`)**:
   - Defines a structured, secret-free `BackupManifest` capturing backup identifiers, dialect, masked database identity, UTC timestamps, format, file path, size, SHA-256 checksum, Alembic revision, verification status, and tool version.
   - Implements `SQLiteBackupAdapter` using the SQLite Online Backup API (`sqlite3.backup`) under active WAL mode, post-backup PRAGMA integrity validation, and SHA-256 hashing.
   - Implements `PostgreSQLBackupAdapter` executing `pg_dump` with strict credential isolation via the `PGPASSWORD` process environment variable (never exposed on command line arguments or logs), custom format (`-Fc`) / plain SQL (`-Fp`) output, non-destructive restore validation via `pg_restore --list`, and missing-tool diagnostics (`BackupToolNotFoundError`).
   - Retains backward-compatible functional wrappers (`backup_sqlite_database` and `restore_sqlite_database`).
3. **Automated Testing Suite (`tests/test_dialect_verification_and_backups.py`)**:
   - Added 25 comprehensive automated tests covering dialect detection, SQLite verifier checks, PostgreSQL simulated heartbeat/enums/sequences, SQLite backup/restore/manifests, PostgreSQL command argument safety/password isolation/missing tool handling, and factory dispatch.
   - Full regression suite increased from **263 passed to 288 passed** (backend) and **20 passed** (frontend).
   - Production database `campus_automation.db` remained strictly untouched with identical SHA-256 checksum and size.

---

## 2. Initial Repository Audit

An audit of the codebase prior to Phase 19E identified the following dialect-dependent behaviors:

| Component | Behavior | Dialect Classification | Remediation Strategy |
| :--- | :--- | :--- | :--- |
| **`database_verifier.py`** | `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;` | SQLite-only | Restrict PRAGMA calls strictly to `dialect_name == "sqlite"`. |
| **`database_verifier.py`** | `SELECT 1;` connectivity check | PostgreSQL-specific | Execute heartbeat query when `dialect_name == "postgresql"`. |
| **`database_verifier.py`** | Custom ENUM inspection | PostgreSQL-specific | Use `inspector.get_enums(schema)` to verify `eventcategory`, `eventstatus`, and `registrationstatus` labels. |
| **`database_verifier.py`** | Sequence / Identity reflection | PostgreSQL-specific | Inspect sequences via `inspector.get_sequence_names` or `information_schema.sequences`. |
| **`database_verifier.py`** | Table, column, constraint, index reflection | Portable SQLAlchemy | Maintain shared reflection logic across all 22 domain models. |
| **`database_verifier.py`** | Column type family matching | Shared with Dialect Nuance | Normalize `BOOLEAN` (compatible with `INTEGER` on SQLite) and `ENUM` (compatible with `VARCHAR` on SQLite and native `ENUM` on PG). |
| **`backup_utils.py`** | `source_conn.backup(target_conn)` | SQLite-only | Encapsulate inside `SQLiteBackupAdapter`. |
| **`backup_utils.py`** | CLI `pg_dump` invocation | PostgreSQL-specific | Implement `PostgreSQLBackupAdapter` with secure environment variable isolation for `PGPASSWORD`. |
| **`backup_utils.py`** | Metadata tracking & Checksumming | Shared | Standardize on `BackupManifest` dataclass with JSON serialization and secret masking. |

---

## 3. Files Created and Modified

### Created Files
- `tests/test_dialect_verification_and_backups.py`: Automated test suite containing 25 unit and integration tests.
- `docs/database/PHASE_19E_DIALECT_VERIFICATION_AND_BACKUPS.md`: This comprehensive architectural record.

### Modified Files
- `backend/core/database_verifier.py`: Refactored to support dialect detection, PostgreSQL heartbeat, schema qualification, custom enum inspection, sequence checks, and enriched report dataclasses.
- `backend/core/backup_utils.py`: Refactored into a modular adapter architecture with `BackupManifest`, `BaseBackupAdapter`, `SQLiteBackupAdapter`, `PostgreSQLBackupAdapter`, `get_backup_adapter`, and credential sanitization.

---

## 4. Verifier Architecture

```mermaid
flowchart TD
    Engine[SQLAlchemy Engine / URL] --> DialectDetect{Dialect Detection}
    DialectDetect -->|sqlite| SQLiteVerifier[SQLite Verifier Branch]
    DialectDetect -->|postgresql| PGVerifier[PostgreSQL Verifier Branch]
    DialectDetect -->|other| Reject[Raise ValueError: Unsupported Dialect]

    subgraph Shared Inspection
        SQLiteVerifier --> SharedReflect[SQLAlchemy Reflection]
        PGVerifier --> SharedReflect
        SharedReflect --> Tables[22 Domain Tables]
        SharedReflect --> Columns[Columns & Types & Nullability]
        SharedReflect --> Constraints[PK, FK, Unique Constraints]
        SharedReflect --> Indexes[Secondary & Unique Indexes]
        SharedReflect --> AlembicRev[Alembic Version Table Query]
    end

    subgraph Dialect-Specific Checks
        SQLiteVerifier --> SQLitePragmas[PRAGMA integrity_check<br/>PRAGMA foreign_key_check]
        PGVerifier --> PGHeartbeat[SELECT 1 Heartbeat]
        PGVerifier --> PGEnums[Inspector Enum Check:<br/>eventcategory, eventstatus, registrationstatus]
        PGVerifier --> PGSequences[Sequence / Identity Check]
    end

    SharedReflect & SQLitePragmas & PGHeartbeat & PGEnums & PGSequences --> Classifier{5-State Readiness Classifier}

    Classifier -->|No domain tables, No alembic| StateA[FRESH: can_start=False]
    Classifier -->|Matches baseline, Alembic verified| StateB[MIGRATED: can_start=True]
    Classifier -->|Matches baseline, Alembic absent| StateC[COMPATIBLE_UNSTAMPED: can_start=True, Warn]
    Classifier -->|Missing tables, cols, types, FKs| StateD[INCOMPATIBLE: can_start=False]
    Classifier -->|Alembic revision unknown/mismatched| StateE[UNKNOWN_REVISION: can_start=False]
```

### Readiness Classification Summary
1. **`FRESH` (State A)**: Empty database with no domain tables. Startup halts; instructs operator to run `alembic upgrade head`.
2. **`MIGRATED` (State B)**: Required 22-table schema present, structural constraints match `Base.metadata`, dialect checks pass, and `alembic_version` matches `0001_initial_baseline`. Startup proceeds cleanly.
3. **`COMPATIBLE_UNSTAMPED` (State C)**: Schema fully matches baseline, but `alembic_version` table is absent (legacy database). Warning logged; startup proceeds; manual baseline stamping requested during maintenance window.
4. **`INCOMPATIBLE` (State D)**: Schema has missing tables, missing columns, incompatible type families, missing constraints, or dialect integrity errors. Startup halts with critical diagnostic log.
5. **`UNKNOWN_REVISION` (State E)**: Database contains an `alembic_version` row with an unrecognized revision string. Startup halts to prevent data corruption.

---

## 5. Backup Architecture & Secret-Free Manifest

### `BackupManifest` Specification
Backups generated by both adapters are accompanied by a companion `.manifest.json` file containing structured metadata:

```json
{
  "backup_id": "sqlite_20261109_123736_4f9a12bc",
  "dialect": "sqlite",
  "database_identifier": "campus_automation.db",
  "timestamp": "2026-11-09T12:37:36.123456+00:00",
  "format": "sqlite_file",
  "backup_file_path": "C:\\backups\\backup_20261109_123736_campus_automation.db",
  "file_size_bytes": 290816,
  "sha256_checksum": "baca55ebd284e474ef79c45d01f1b311c7c8e4f9a779bcb99a596a46798ce227",
  "alembic_revision": "0001_initial_baseline",
  "verification_status": "verified",
  "tool_version": "sqlite3 3.49.1"
}
```

For PostgreSQL backups, credentials are never included:
```json
{
  "backup_id": "pg_20261109_123840_9a8b7c6d",
  "dialect": "postgresql",
  "database_identifier": "postgresql+psycopg://campus_user:***@10.0.0.5:5432/campus_production",
  "timestamp": "2026-11-09T12:38:40.654321+00:00",
  "format": "pg_dump_custom",
  "backup_file_path": "C:\\pg_backups\\pg_backup_20261109_123840_campus_production.dump",
  "file_size_bytes": 1048576,
  "sha256_checksum": "c2b3a4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091",
  "alembic_revision": "0001_initial_baseline",
  "verification_status": "verified",
  "tool_version": "pg_dump 16.1"
}
```

### PostgreSQL Credential Isolation Security Rule
Under `PostgreSQLBackupAdapter`:
- The CLI command constructed is:
  `['pg_dump', '-h', host, '-p', port, '-U', user, '-F', 'c', '-f', target_path, database]`
- Passwords are **NEVER** passed via `-W`, query parameters, or command-line arguments. This prevents process table snooping (`ps -ef`, Process Explorer).
- The password is provided exclusively via the subprocess environment dictionary: `env["PGPASSWORD"] = password`.
- Any error output captured from `stderr` passes through `sanitize_text()`, which strips plain text passwords and connection URI secrets before logging or raising `BackupError`.

---

## 6. Test Results and Baseline Comparison

### Test Execution Summary
- **Backend Test Suite:**
  - Previous Phase 19D Baseline: **263 passed**
  - Phase 19E New Tests: **25 passed**
  - Total Passing Tests: **288 passed** in 43.42s
  - Failures: 0, Errors: 0, Skipped: 0
- **Frontend Test Suite:**
  - Status: **20 passed** in 155.66ms
  - Failures: 0, Errors: 0

### Phase 19E Test Breakdown (`tests/test_dialect_verification_and_backups.py`)
1. `test_verifier_accepts_sqlite`: PASSED
2. `test_verifier_accepts_postgresql`: PASSED
3. `test_verifier_rejects_unsupported_dialects`: PASSED
4. `test_sqlite_fresh_database`: PASSED
5. `test_sqlite_migrated_database`: PASSED
6. `test_sqlite_compatible_unstamped_database`: PASSED
7. `test_sqlite_executes_integrity_and_foreign_key_pragmas`: PASSED
8. `test_postgresql_heartbeat_execution`: PASSED
9. `test_postgresql_schema_qualification`: PASSED
10. `test_postgresql_native_enum_verification_pass`: PASSED
11. `test_postgresql_native_enum_verification_missing_enum`: PASSED
12. `test_postgresql_native_enum_verification_missing_label`: PASSED
13. `test_sqlite_backup_creation_and_manifest`: PASSED
14. `test_sqlite_backup_overwrite_protection`: PASSED
15. `test_sqlite_restore_and_validate_restore`: PASSED
16. `test_postgresql_command_construction_and_no_password_in_cli`: PASSED
17. `test_postgresql_missing_tool_raises_tool_not_found`: PASSED
18. `test_postgresql_backup_sanitizes_errors`: PASSED
19. `test_postgresql_validate_restore_guards_active_database`: PASSED
20. `test_get_backup_adapter_sqlite_path`: PASSED
21. `test_get_backup_adapter_sqlite_url`: PASSED
22. `test_get_backup_adapter_postgresql_url`: PASSED
23. `test_get_backup_adapter_from_engine`: PASSED
24. `test_backup_sqlite_database_functional_wrapper`: PASSED
25. `test_sanitize_text_utility`: PASSED

---

## 7. Production Database Safety & Integrity Verification

To adhere strictly to non-destructive constraints, the application database `campus_automation.db` was verified before and after Phase 19E implementation:

- **File Path:** `MARVEL-main/campus_automation.db`
- **File Length:** `290,816` bytes (exact match)
- **SHA-256 Checksum:** `BACA55EBD284E474EF79C45D01F1B311C7C8E4F9A779BCB99A596A46798CE227` (exact match)
- **Verification Status:** Pristine and untouched. No migrations, stamping, or table modifications were executed against this database.

---

## 8. Limitations & Unverified Capabilities

1. **Subprocess Mocking in Automated Tests**:
   - PostgreSQL adapter tests were executed using simulated environments and mocked subprocess execution to ensure reproducibility on development machines without PostgreSQL client binaries installed.
   - Live end-to-end `pg_dump` execution against a running PostgreSQL 16+ daemon requires a deployed database host and will be verified during staging deployment (Task 19F).
2. **Restore Safety in Production**:
   - `PostgreSQLBackupAdapter.validate_restore()` enforces dry-run safety and prevents overwriting the active database without `overwrite=True`. However, full point-in-time recovery on PostgreSQL production clusters must be orchestrated via designated staging databases or containerized instances to prevent accidental downtime.
