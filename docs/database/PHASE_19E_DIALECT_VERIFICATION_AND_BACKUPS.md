# Phase 19E-G — Dialect-Aware Database Verification & Backup Architecture

**Project:** Campus Automation System (MARVEL)  
**Workspace:** `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`  
**Target Dialects:** SQLite 3 (Dev/Test) and PostgreSQL 16+ (Staging/Production)  
**Mode:** Strict Audit, Restore Safety Hardening & Safe Recovery Verification

---

## 1. Executive Summary

Phase 19E-G completes the dialect-aware database verification and backup architecture supporting both SQLite 3 and PostgreSQL 16+, with strict safety controls governing PostgreSQL restore operations.

Prior to this phase, `DatabaseVerifier` relied on SQLite-specific `PRAGMA integrity_check` and `PRAGMA foreign_key_check` queries that failed against PostgreSQL engines, while `backup_utils.py` was tightly coupled to SQLite's C-level `sqlite3.backup` API without support for PostgreSQL enterprise backups. In Phase 19E-F and Phase 19E-G, both modules were refactored into modular, dialect-aware architectures:
1. **`DatabaseVerifier` (`backend/core/database_verifier.py`)**:
   - Detects the active database dialect (`sqlite` or `postgresql`) and rejects unsupported engines.
   - Preserves portable SQLAlchemy reflection across all 22 domain tables, columns, data types, nullability, primary keys, foreign keys, unique constraints, and indexes.
   - Isolates SQLite PRAGMA checks to SQLite engines only.
   - Introduces PostgreSQL connectivity heartbeat (`SELECT 1;`), schema qualification, custom native ENUM inspection (`eventcategory`, `eventstatus`, `registrationstatus`), and sequence reflection.
   - Retains 100% backward compatibility for the five canonical migration readiness states (`FRESH`, `MIGRATED`, `COMPATIBLE_UNSTAMPED`, `INCOMPATIBLE`, `UNKNOWN_REVISION`).
2. **Modular Backup & Restore Architecture (`backend/core/backup_utils.py`)**:
   - Defines a structured, secret-free `BackupManifest` capturing backup identifiers, dialect, masked database identity, UTC timestamps, format, file path, size, SHA-256 checksum, Alembic revision, verification status, and tool version.
   - Implements `SQLiteBackupAdapter` using the SQLite Online Backup API (`sqlite3.backup`) under active WAL mode, post-backup PRAGMA integrity validation, SHA-256 hashing, and non-destructive restore.
   - Implements `PostgreSQLBackupAdapter` with:
     - `create_backup()`: executes `pg_dump` with custom (`-Fc`) / plain (`-Fp`) formats and strict credential isolation via the `PGPASSWORD` process environment variable (never exposed on command line arguments or logs).
     - `verify_backup()`: inspects `b"PGDMP"` magic bytes and TOC contents via `pg_restore --list`.
     - `validate_restore()`: validates backup existence, integrity, destination database specification, alias normalization, production environment guards, and guards against accidental overwriting of active databases or existing non-empty databases.
     - `restore()`: executes `pg_restore` targeting an explicitly identified destination database with `--no-owner --no-privileges`, strict destructive authorization checks for the `clean` option, and `PGPASSWORD` environment isolation.
     - Missing-tool diagnostics (`BackupToolNotFoundError`) and credential sanitization (`sanitize_text()`).
   - Retains backward-compatible functional wrappers (`backup_sqlite_database` and `restore_sqlite_database`).
3. **Automated Testing Suite (`tests/test_dialect_verification_and_backups.py`)**:
   - Includes 34 comprehensive automated tests covering dialect detection, SQLite verifier checks, PostgreSQL simulated heartbeat/enums/sequences, SQLite backup/restore/manifests, PostgreSQL command argument safety/password isolation/missing tool handling, restore validation, destination identity alias detection, production target rejection, non-empty database protection, explicit destructive authorization, credential isolation, failure cleanup safety, and factory dispatch.
   - Full regression suite increased from **263 passed to 297 passed** (backend) and **20 passed** (frontend).
   - Production database `campus_automation.db` remained strictly untouched with identical SHA-256 checksum and size.

---

## 2. Verification Classification & Testing Distinctions

To ensure complete engineering transparency, test coverage and verification status are classified into distinct categories:

### A. Real SQLite Verification (100% Verified)
- Real SQLite online backups executed via `sqlite3.backup` API under WAL mode.
- Real SQLite backup integrity check executed via `PRAGMA integrity_check;`.
- Real SQLite restore executed into isolated temporary database files and verified via table inspection and Alembic revision queries.
- Zero mock objects used for SQLite test suites.

### B. Mocked / Simulated PostgreSQL Tests (100% Passing in Mocked Environment)
- PostgreSQL adapter tested using controlled subprocess mock fixtures (`mock_executor`, `mock_restore_executor`).
- Verified:
  - Command line vector generation: `['pg_dump', '-h', host, '-p', port, '-U', user, '-F', 'c', '-f', target_path, database]`.
  - Safe default restore vector (NO `--clean`): `['pg_restore', '-h', host, '-p', port, '-U', user, '-d', target_db, '--no-owner', '--no-privileges', backup_path]`.
  - Destructive restore vector (WITH `--clean`): only generated when explicitly authorized via `allow_destructive_clean=True` and matching `confirm_destructive_clean_database_name`.
  - **Existing Non-Empty Database Protection:** Rejects restoring into non-empty databases unless `allow_destructive_clean=True`.
  - **Active Database Identity & Alias Protection:** Normalizes hostnames (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`), port (5432), and URI schemes, rejecting restorations over the active database across all alias representations.
  - **Production Environment Target Rejection:** Rejects restoration into production hosts or database names (`prod`, `production`, `live`, `supabase`, `rds.amazonaws.com`, etc.).
  - **Password Environment Isolation:** Passwords NEVER appear in command line arguments (`-W` is excluded; raw strings are absent). Passwords are provided strictly through `env["PGPASSWORD"]`.
  - **Manifest Sanitization:** Generated `BackupManifest` contains masked database identity (`postgresql+psycopg://campus_user:***@host:5432/db`) and zero secrets.
  - **Error Output Sanitization:** Exceptions and stderr messages pass through `sanitize_text()`, stripping raw passwords or URI credentials.
  - **Missing Tool Handling:** Non-existent `pg_dump` or `pg_restore` binaries raise `BackupToolNotFoundError`.
  - **Failure Cleanup Safety:** Temporary files created during failed operations are cleaned up immediately without touching existing assets.

### C. Real PostgreSQL Integration & Recovery Status (Explicitly Untested)
- **Status:** **UNTESTED AGAINST A LIVE POSTGRESQL DAEMON**.
- **Reason:** No local PostgreSQL 16+ server instance, Docker daemon, or CLI tools (`pg_dump`, `pg_restore`, `psql`) are installed on the local Windows development machine.
- **Strict Compliance:** In accordance with safety rules, production and Supabase database credentials were **NEVER** used to run test restores or generate test dumps.
- **Future Milestone:** Full live end-to-end `pg_dump` and `pg_restore` cycles must be executed in a dedicated staging environment (Task 19F) with disposable target databases.

---

## 3. Files Created and Modified

### Created Files
- `tests/test_dialect_verification_and_backups.py`: Automated test suite containing 34 unit, integration, and safety tests.
- `docs/database/PHASE_19E_DIALECT_VERIFICATION_AND_BACKUPS.md`: This comprehensive architectural record.

### Modified Files
- `backend/core/database_verifier.py`: Dialect detection, PostgreSQL heartbeat, schema qualification, custom enum inspection, sequence checks, and enriched report dataclasses.
- `backend/core/backup_utils.py`: Modular adapter architecture with `BackupManifest`, `BaseBackupAdapter`, `SQLiteBackupAdapter`, `PostgreSQLBackupAdapter` (including `create_backup`, `verify_backup`, `validate_restore`, and `restore`), `get_backup_adapter`, destination identity normalization, active database alias protection, non-empty database protection, production target guard, explicit destructive clean authorization, and credential sanitization.

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

---

## 5. Secret-Free Backup Manifest Example

Backups generated by both adapters are accompanied by a companion `.manifest.json` file containing structured metadata:

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

---

## 6. Restore Safety Controls & Guardrails

The recovery procedure in `PostgreSQLBackupAdapter.restore()` and `validate_restore()` enforces ten strict safety controls:
1. **Safe Default (NO `--clean`):** The `clean` (`-c`) flag is NEVER passed by default. Silent dropping or recreating of schema objects is strictly prohibited.
2. **Existing Non-Empty Database Protection:** Restoration into an existing non-empty database is rejected by default (`target_is_empty=False`). Overwriting requires explicit destructive authorization.
3. **Explicit Destructive Authorization:** To execute a destructive restore (`clean=True`), the caller must explicitly provide both:
   - `allow_destructive_clean=True`
   - `confirm_destructive_clean_database_name=<target_db>` matching the destination database name exactly.
4. **Active Database Protection & Alias Detection:** Restoration over the active source database is strictly refused. Destination hostnames (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`), port (5432 default), schemes (`postgres://` / `postgresql://`), and case-insensitive database names are normalized to detect and reject active database collisions across all alias variations.
5. **Production Target Protection:** Direct restoration into production environments is prohibited. The system analyzes destination hostnames and database names against production markers (`prod`, `production`, `live`, `supabase`, `rds.amazonaws.com`, `cloudsql`, etc.) and raises a `BackupError`.
6. **Explicit Destination Specification:** Destination databases must be explicitly provided. Missing, empty, whitespace-only, or inferred destinations are rejected.
7. **No Automatic Restore on Startup:** Automatic restoration or database resetting on application startup is strictly prohibited.
8. **Credential Isolation:** Passwords are provided exclusively via the subprocess environment dictionary: `env["PGPASSWORD"] = password`. Command line arguments and process vectors NEVER contain credentials.
9. **Sanitized Diagnostics:** All error messages, standard output, and process exceptions pass through `sanitize_text()`, ensuring credentials and URIs are masked.
10. **Failure Cleanup Safety:** Temporary files and failed artifacts are unlinked cleanly without touching destination databases or unrelated filesystem resources.

---

## 7. Test Results and Baseline Comparison

| Test Suite | Previous Baseline | Phase 19E-G Result | Status |
| :--- | :--- | :--- | :--- |
| `tests/test_dialect_verification_and_backups.py` | 0 | **34 passed** | **PASSED** (2.83s) |
| Full Backend Regression Suite (`pytest tests/`) | 263 passed | **297 passed** | **PASSED** (44.82s) |
| Frontend Test Suite (`npm test`) | 20 passed | **20 passed** | **PASSED** (149.92ms) |

### Test Suite Breakdown (`tests/test_dialect_verification_and_backups.py`)
1. `test_verifier_accepts_sqlite`: PASSED (Real SQLite)
2. `test_verifier_accepts_postgresql`: PASSED (Mocked engine)
3. `test_verifier_rejects_unsupported_dialects`: PASSED (Unit)
4. `test_sqlite_fresh_database`: PASSED (Real SQLite)
5. `test_sqlite_migrated_database`: PASSED (Real SQLite)
6. `test_sqlite_compatible_unstamped_database`: PASSED (Real SQLite)
7. `test_sqlite_executes_integrity_and_foreign_key_pragmas`: PASSED (Real SQLite)
8. `test_postgresql_heartbeat_execution`: PASSED (Mocked dialect)
9. `test_postgresql_schema_qualification`: PASSED (Mocked dialect)
10. `test_postgresql_native_enum_verification_pass`: PASSED (Mocked inspector)
11. `test_postgresql_native_enum_verification_missing_enum`: PASSED (Mocked inspector)
12. `test_postgresql_native_enum_verification_missing_label`: PASSED (Mocked inspector)
13. `test_sqlite_backup_creation_and_manifest`: PASSED (Real SQLite)
14. `test_sqlite_backup_overwrite_protection`: PASSED (Real SQLite)
15. `test_sqlite_restore_and_validate_restore`: PASSED (Real SQLite)
16. `test_postgresql_command_construction_and_no_password_in_cli`: PASSED (Mocked pg_dump)
17. `test_postgresql_missing_tool_raises_tool_not_found`: PASSED (Mocked pg_dump)
18. `test_postgresql_backup_sanitizes_errors`: PASSED (Mocked pg_dump)
19. `test_postgresql_validate_restore_guards_active_database`: PASSED (Mocked pg_restore)
20. `test_postgresql_restore_command_construction_and_password_isolation_mocked`: PASSED (Mocked pg_restore)
21. `test_postgresql_restore_missing_tool_raises_tool_not_found_mocked`: PASSED (Mocked pg_restore)
22. `test_postgresql_restore_sanitizes_errors_mocked`: PASSED (Mocked pg_restore)
23. `test_postgresql_restore_protects_active_database_mocked`: PASSED (Mocked pg_restore)
24. `test_postgresql_restore_default_does_not_pass_clean_flag_mocked`: PASSED (Mocked pg_restore safety)
25. `test_postgresql_restore_rejects_existing_non_empty_database_without_explicit_authorization_mocked`: PASSED (Mocked pg_restore safety)
26. `test_postgresql_restore_rejects_active_source_database_mocked`: PASSED (Mocked pg_restore safety)
27. `test_postgresql_restore_rejects_active_database_via_aliases_mocked`: PASSED (Mocked pg_restore safety)
28. `test_postgresql_restore_rejects_production_target_mocked`: PASSED (Mocked pg_restore safety)
29. `test_postgresql_restore_rejects_missing_or_empty_destination_mocked`: PASSED (Mocked pg_restore safety)
30. `test_postgresql_restore_allows_clean_only_with_full_explicit_authorization_mocked`: PASSED (Mocked pg_restore safety)
31. `test_postgresql_restore_allows_clean_into_empty_database_mocked`: PASSED (Mocked pg_restore safety)
32. `test_credential_values_never_appear_in_subprocess_arguments_or_sanitized_logs_mocked`: PASSED (Mocked pg_restore safety)
33. `test_postgresql_restore_failure_cleanup_does_not_affect_unrelated_resources_mocked`: PASSED (Mocked pg_restore safety)
34. `test_get_backup_adapter_sqlite_path`: PASSED (Factory)
35. (Also includes factory tests `test_get_backup_adapter_sqlite_url`, `test_get_backup_adapter_postgresql_url`, `test_get_backup_adapter_from_engine`, `test_backup_sqlite_database_functional_wrapper`, `test_sanitize_text_utility`).

---

## 8. Production Database Safety & Integrity Verification

To adhere strictly to non-destructive constraints, the application database `campus_automation.db` was verified before and after Phase 19E-G implementation:

- **File Path:** `MARVEL-main/campus_automation.db`
- **File Length:** `290,816` bytes (exact match)
- **SHA-256 Checksum:** `BACA55EBD284E474EF79C45D01F1B311C7C8E4F9A779BCB99A596A46798CE227` (exact match)
- **Verification Status:** **Pristine and untouched.** No migrations, stamping, or table modifications were executed against this database.

---

## 9. Explicit Limitations & Remaining Operational Requirements

1. **Live PostgreSQL Daemon Verification:**
   - Real `pg_dump` and `pg_restore` cycles against a running PostgreSQL 16+ daemon could not be performed on the local development machine because no local PostgreSQL server, `pg_dump`/`pg_restore` binaries, or Docker daemon exist on the Windows host.
   - All PostgreSQL verification on this host is performed via simulated/mocked subprocess executions.
2. **Standard of Completion:**
   - As per task guidelines, PostgreSQL backup and recovery is **NOT labeled as fully verified in production** until a real isolated PostgreSQL backup and restore cycle has succeeded on a running PostgreSQL 16+ instance in staging (Task 19F).
