# TASK 18D — ALEMBIC SCHEMA OWNERSHIP & DECOUPLING REPORT

**Project**: Campus Automation System (MARVEL)  
**Repository**: `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`  
**Branch**: `main`  
**Task Type**: Architecture Refactoring — Schema Management Decoupling  
**Date**: November 4, 2026  

---

## 1. Executive Summary & Objective

The objective of Task 18D is to establish **Alembic as the single authoritative schema-management system** for the Campus Automation System, eliminating all competing automatic schema creation, procedural table alteration, and implicit DDL side effects from application startup and data seed routines.

### Key Architectural Accomplishments:
1. **Module-Level Table Creation Removed**: Eliminated uncontrolled `student.Base.metadata.create_all(bind=engine)` from [`backend/main.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/main.py). Importing the application now executes zero DDL statements.
2. **Procedural Migrations Decommissioned**: Deprecated and neutralized `ensure_schema()` in [`backend/seed_data.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/seed_data.py). All raw SQL `ALTER TABLE`, `CREATE UNIQUE INDEX`, and `DELETE` statements were removed. Schema evolution is now governed exclusively by versioned Alembic revisions.
3. **Fail-Closed Application Startup**: Replaced the silent-failure try-catch block in `startup_event()` with a rigorous schema inspection. If any required model tables are missing, application startup aborts immediately with a clear `RuntimeError` instructing the operator to execute `alembic upgrade head`.
4. **Data Seeder Purity & Idempotency Preserved**: [`backend/seed_data.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/seed_data.py) is now strictly a data-manipulation (DML) script. It verifies schema presence before querying and safely refuses execution on unmigrated databases.
5. **Admin Script Hardened**: [`backend/scripts/create_admin.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/scripts/create_admin.py) no longer creates tables behind Alembic's back; it checks for schema readiness and aborts cleanly if unmigrated.
6. **Actual Database Untouched**: The live application database `campus_automation.db` was **NOT modified, NOT stamped, and NOT migrated** (preserved bit-for-bit with SHA-256 `baca55ebd284e474ef79c45d01f1b311c7c8e4f9a779bcb99a596a46798ce227`).
7. **Automated Test Validation**: Added 10 new tests in [`tests/test_alembic_schema_ownership.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/tests/test_alembic_schema_ownership.py). All 210 backend tests and 20 frontend tests pass cleanly.

---

## 2. Previous vs. New Schema Initialization Flow

### Previous Flow (Procedural & Competing DDL Architecture)

```
[Module Import]
      │
      ▼
backend/main.py
      ├──> student.Base.metadata.create_all(bind=engine)  <-- Uncontrolled DDL on import
      │
[Application Startup]
      │
      ▼
startup_event()
      ├──> ensure_schema()                                <-- Competed with Alembic
      │         ├──> Base.metadata.create_all(bind=engine)
      │         └──> Procedural ALTER TABLE / CREATE INDEX via SQLite PRAGMA
      ├──> try ... except Exception: log warning          <-- Silent swallow of schema errors
      └──> seed_database()
                ├──> ensure_schema()                      <-- Repeated redundant DDL
                └──> Data insertion
```

**Flaws in Previous Architecture**:
- **Import Side Effects**: Any process importing `backend.main` (CLI tools, linters, tests, interactive shells) inadvertently created or altered database tables.
- **Race Conditions**: Multi-worker ASGI servers (e.g., Gunicorn with 4 workers) executed concurrent `create_all()` and `ALTER TABLE` operations on the same database, causing SQLite write lock conflicts (`database is locked`).
- **Schema Drift & Masked Errors**: Schema exceptions during startup were swallowed with a warning log, leading to downstream `OperationalError: no such column` failures during user requests.
- **Lack of Version Tracking**: Procedural `ensure_schema()` could not rollback changes, generate offline SQL scripts, or track schema versions.

---

### New Flow (Alembic Authoritative & Explicit Lifecycle)

```
[Explicit Deployment Step]
      │
      ▼
$ alembic upgrade head (or baseline adoption during maintenance)
      ├──> Executes version-controlled migration scripts
      └──> Registers revision in alembic_version table
      │
[Module Import]
      │
      ▼
backend/main.py  (Zero DDL, Zero side effects)
      │
[Application Startup]
      │
      ▼
startup_event()
      ├──> inspect(engine).get_table_names()
      │         │
      │         ├──> Missing Required Tables?
      │         │         └──> RAISE RuntimeError (Fail-Closed, Abort Startup)
      │         │
      │         └──> Schema Complete?
      │                   └──> If Development: seed_default_users() & seed_database() (DML Only)
      │                        If Production: Skip Seeding
      └──> Register agents, start background tasks & complete startup
```

---

## 3. Files and Functions Changed

| File Path | Function / Scope | Change Summary |
|---|---|---|
| [`backend/main.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/main.py#L40-L45) | Module Level | **Removed** `student.Base.metadata.create_all(bind=engine)` to prevent table creation upon module import. |
| [`backend/main.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/main.py#L90-L125) | `startup_event()` | **Removed** `ensure_schema()`. Added explicit read-only schema readiness inspection using `inspect(engine)`. If domain tables are missing, raises `RuntimeError` directing to `alembic upgrade head`. |
| [`backend/seed_data.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/seed_data.py#L36-L50) | `ensure_schema()` | **Deprecated & Neutralized**. Removed `Base.metadata.create_all()` and all raw SQL `ALTER TABLE` / `CREATE INDEX` statements. Emits a deprecation warning and executes zero DDL. |
| [`backend/seed_data.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/seed_data.py#L55-L75) | `seed_default_users()` | Added schema pre-check. Inspects database for `"users"` table; raises `RuntimeError` if missing rather than attempting queries on unmigrated schema. |
| [`backend/seed_data.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/seed_data.py#L130-L155) | `seed_database()` | **Removed** `ensure_schema()` call. Added schema pre-check for required domain tables (`students`, `users`, `clubs`, `events`, `schedules`); raises `RuntimeError` if unmigrated. |
| [`backend/scripts/create_admin.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/scripts/create_admin.py#L25-L35) | `create_admin()` | **Removed** `Base.metadata.create_all(bind=engine)`. Added schema pre-check verifying `"users"` table exists. |
| [`README.md`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/README.md) | Docs / Setup | Updated setup commands to emphasize `alembic upgrade head` before running the seeder or server. |
| [`tests/test_alembic_schema_ownership.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/tests/test_alembic_schema_ownership.py) | Test Suite | **Created**. 10 dedicated automated tests validating schema ownership contracts. |

---

## 4. Startup Behavior Across Database States

| Database State | Previous Startup Behavior | New Startup Behavior |
|---|---|---|
| **Empty / Unmigrated Database** | Silently created tables using `create_all()`; logged swallowed warning on mismatch. | **Fails immediately with `RuntimeError`**: `"Database schema is incomplete: missing required tables [...]. Run 'alembic upgrade head'."` |
| **Partially Migrated Database** | Silently created missing tables or executed uncontrolled `ALTER TABLE` statements. | **Fails immediately with `RuntimeError`** listing the exact missing tables. |
| **Fully Migrated Database (`alembic upgrade head`)** | Executed redundant `create_all()` and procedural PRAGMA checks; proceeded to seed. | **Succeeds cleanly**: Schema verification passes; proceeds to idempotent data seeding in development. |
| **Existing Unstamped Database (`campus_automation.db`)** | Executed redundant `create_all()`; proceeded to seed. | **Succeeds cleanly**: All 22 domain tables are verified; unstamped database remains untouched. |

---

## 5. Developer & Operator Workflows

### 5.1 Fresh Database Initialization
For local development or new production deployments:
```bash
# 1. Apply all version-controlled migrations
alembic upgrade head

# 2. (Development only) Seed initial test accounts and sample data
python -m backend.seed_data

# 3. Start the application
uvicorn backend.main:app --reload
```

### 5.2 Existing Database Baseline Adoption
For environments already running with `campus_automation.db` (containing pre-existing records):
```bash
# 1. Stop application workers
# 2. Create verified backup
python -c "from backend.core.backup_utils import backup_sqlite_database; backup_sqlite_database('campus_automation.db', 'backups')"

# 3. Verify schema conformance against Base.metadata
python -c "from sqlalchemy import create_engine; from backend.core.database_verifier import DatabaseVerifier; v = DatabaseVerifier(create_engine('sqlite:///campus_automation.db')); assert v.verify_schema().can_stamp"

# 4. Stamp baseline revision during authorized maintenance window
alembic stamp 0001_initial_baseline

# 5. Restart application
```

### 5.3 Authoring Future Schema Migrations
When schema changes are needed (e.g., adding a column to an entity):
```bash
# 1. Update the SQLAlchemy model class in backend/models/<entity>.py
# 2. Generate autogenerated revision
alembic revision --autogenerate -m "add_column_x_to_table_y"

# 3. Inspect generated migration file in alembic/versions/
# 4. Apply migration to local development database
alembic upgrade head

# 5. Run tests to confirm zero regression
pytest tests/
```

### 5.4 Data Seeding
Data seeding is strictly isolated to data population and will never alter database schemas:
```bash
python -m backend.seed_data
```

---

## 6. Automated Test Suite Results

### 6.1 Task 18D Schema Ownership Test Suite (`tests/test_alembic_schema_ownership.py`)
Ten dedicated tests verifying decoupling and fail-closed behavior:
```text
tests/test_alembic_schema_ownership.py::test_1_importing_application_does_not_create_domain_tables PASSED
tests/test_alembic_schema_ownership.py::test_2_startup_does_not_call_create_all PASSED
tests/test_alembic_schema_ownership.py::test_3_startup_does_not_invoke_procedural_schema_creation PASSED
tests/test_alembic_schema_ownership.py::test_4_seed_routines_do_not_create_tables PASSED
tests/test_alembic_schema_ownership.py::test_5_seed_routines_remain_idempotent PASSED
tests/test_alembic_schema_ownership.py::test_6_startup_against_correctly_migrated_database_works PASSED
tests/test_alembic_schema_ownership.py::test_7_startup_against_missing_tables_fails_clearly PASSED
tests/test_alembic_schema_ownership.py::test_8_existing_orm_queries_continue_working PASSED
tests/test_alembic_schema_ownership.py::test_9_existing_auth_and_security_behavior_unchanged PASSED
tests/test_alembic_schema_ownership.py::test_10_database_verifier_rejects_unmigrated_and_approves_baseline PASSED

============================= 10 passed in 15.91s =============================
```

### 6.2 Full Backend Pytest Suite
All 210 backend unit, security, integration, and migration tests pass cleanly:
```text
============================ 210 passed in 54.39s =============================
```

### 6.3 Frontend Test Suites
All 20 frontend configuration and security tests pass cleanly:
```text
ℹ tests 20
ℹ suites 3
ℹ pass 20
ℹ fail 0
```

---

## 7. Real Database Integrity Verification

The live application database `campus_automation.db` was inspected before and after all changes:

| Metric | Before Task 18D | After Task 18D | Delta | Status |
|---|---|---|---|---|
| **File Size** | 290,816 bytes | 290,816 bytes | 0 bytes | **Unmodified** |
| **SHA-256 Checksum** | `baca55ebd284e474ef79c45d01f1b311c7c8e4f9a779bcb99a596a46798ce227` | `baca55ebd284e474ef79c45d01f1b311c7c8e4f9a779bcb99a596a46798ce227` | None | **Identical** |
| **Domain Tables** | 22 tables | 22 tables | 0 | **Preserved** |
| **`alembic_version`** | Absent (`False`) | Absent (`False`) | None | **Unstamped** |

---

## 8. Known Limitations & Deployment Cautions

1. **SQLite Write Concurrency**: SQLite employs database-level write locks. Running high-concurrency workloads or multiple ASGI workers against SQLite can lead to lock contention. PostgreSQL remains strongly recommended for multi-worker production.
2. **Never Run Migrations Automatically in Multi-Worker ASGI**: In containerized or production deployments (e.g. Kubernetes, Gunicorn with multiple workers), database migrations must be run as a separate pre-start or initialization container/job (`alembic upgrade head`) before workers boot. Workers must verify readiness and abort if migrations have not landed.
3. **Authorized Stamping Window**: The actual database `campus_automation.db` remains unstamped until a formal maintenance window allows operators to apply `alembic stamp 0001_initial_baseline` following verified backups.
