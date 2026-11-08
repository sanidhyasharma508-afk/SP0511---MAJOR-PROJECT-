# PHASE 19D: DUAL-DIALECT ALEMBIC MIGRATION HARDENING

**Project:** Campus Automation System (MARVEL)  
**Workspace:** `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`  
**Branch:** `main`  
**Dialects Supported:** SQLite 3 (Dev/Test) & PostgreSQL 16+ (Staging/Production)  
**Status:** COMPLETE & VERIFIED

---

## 1. MIGRATION ARCHITECTURE

The MARVEL database migration infrastructure utilizes Alembic as the single authoritative schema-management framework. Phase 19D hardened the migration environment (`alembic/env.py`) to reliably support both SQLite 3 and PostgreSQL 16+ without duplicate logic, silent database misdirection, or credential leaks.

### Architectural Principles:
1. **Centralized URL Resolution:**
   - Both online and offline migration contexts dynamically resolve the target URL via `get_url()`.
   - Normalizes legacy/bare PostgreSQL schemes (`postgres://`, `postgresql://`) to modern Psycopg 3 (`postgresql+psycopg://`).
   - Resolves relative SQLite paths (`sqlite:///./...`) against the application base directory (`BASE_DIR`), ensuring deterministic invocation regardless of the execution working directory.
2. **Credential Sanitization & Auditability:**
   - Database credentials are masked via `mask_database_url()` before any migration logs or diagnostics are emitted.
   - Every migration invocation explicitly logs the detected dialect and masked target database.
3. **Dialect Enforcement:**
   - Dialect is inspected from the normalized URL (`make_url(url).get_backend_name()`).
   - Unsupported dialects (e.g., MySQL, Oracle) are rejected immediately with a descriptive `ValueError`.

---

## 2. CURRENT REVISION GRAPH

The current migration graph has a single linear history with exactly one authoritative head:

```mermaid
flowchart LR
    A["(base)"] --> B["0001_initial_baseline<br/>(head)"]
```

- **Head Revision:** `0001_initial_baseline`
- **Revises:** `None` (Root baseline)
- **Branch Labels:** `None`
- **Depends On:** `None`
- **Tables Created:** 22 domain tables + 1 `alembic_version` tracking table.
- **Verification:** Verified via `ScriptDirectory.get_heads()` and automated tests.

---

## 3. SQLITE BEHAVIOR & TRANSACTION SAFETY

SQLite has specific DDL limitations compared to enterprise relational databases:
1. **Table Re-creation (Batch Mode):**
   - SQLite does not natively support `ALTER TABLE ... DROP COLUMN` or complex constraint changes.
   - `alembic/env.py` configures `render_as_batch=True` for both online and offline SQLite executions.
   - Alembic automatically executes batch alterations via copy-to-temporary-table operations (`_alembic_tmp_<table_name>`).
2. **Foreign Key PRAGMA Lifecycle:**
   - In SQLite, `PRAGMA foreign_keys` cannot be toggled inside an active multi-statement transaction (doing so is silently ignored by the SQLite engine).
   - `alembic/env.py` was hardened to execute `PRAGMA foreign_keys=OFF;` **prior** to entering `context.begin_transaction()`.
   - A `try...finally` block guarantees `PRAGMA foreign_keys=ON;` is executed after transaction commit or rollback, preserving referential integrity across tests.
3. **Connection Pooling:**
   - SQLite online migrations use `pool.NullPool` with `connect_args={"check_same_thread": False}`.
   - The engine is explicitly disposed via `connectable.dispose()` in a `finally` block to prevent Windows file locking.

---

## 4. POSTGRESQL BEHAVIOR & DDL SPECIFICATIONS

PostgreSQL 16+ provides enterprise-grade transactional DDL capabilities:
1. **Transactional DDL:**
   - PostgreSQL executes `CREATE TABLE`, `ALTER TABLE`, and index operations inside an atomic transaction.
   - If any statement in a migration fails, the entire migration rolls back automatically, preventing partial schema state corruption.
2. **Batch Mode Disabled:**
   - `render_as_batch=False` is set for PostgreSQL, allowing direct, performant native `ALTER TABLE` operations.
3. **Offline SQL Generation:**
   - Verified via `alembic upgrade head --sql` using `postgresql+psycopg://`.
   - Generates 17,152 bytes of static PostgreSQL DDL without requiring an active database server.
   - Generated DDL output excludes plaintext database credentials.

---

## 5. ENUM STRATEGY

PostgreSQL enforces strict custom enum types (`CREATE TYPE ... AS ENUM`), whereas SQLite uses table-level `CHECK` constraints.

### Canonical Named Enums in MARVEL:
| Enum Class | Python Definition | PostgreSQL Type Name | Values Persisted | Table / Column |
|---|---|---|---|---|
| `EventCategory` | `backend/models/events.py` | `eventcategory` | `'SPORTS'`, `'TECHNICAL'`, `'CULTURAL'`, `'GAMING'`, `'WORKSHOP'`, `'COMPETITION'` | `events.category` |
| `EventStatus` | `backend/models/events.py` | `eventstatus` | `'UPCOMING'`, `'REGISTRATION_OPEN'`, `'REGISTRATION_CLOSED'`, `'ONGOING'`, `'COMPLETED'`, `'CANCELLED'` | `events.status` |
| `RegistrationStatus` | `backend/models/events.py` | `registrationstatus` | `'PENDING'`, `'APPROVED'`, `'REJECTED'`, `'WAITLISTED'`, `'CANCELLED'` | `event_registrations.status` |

### Parity & Non-Recreation Guarantee:
- In Task 19C, `backend/models/events.py` was hardened to specify explicit names: `SQLEnum(EventCategory, name="eventcategory")`.
- This matches the exact type names defined in `alembic/versions/0001_initial_baseline.py`.
- Alembic offline SQL generation verifies that PostgreSQL emits:
  ```sql
  CREATE TYPE eventcategory AS ENUM ('SPORTS', 'TECHNICAL', 'CULTURAL', 'GAMING', 'WORKSHOP', 'COMPETITION');
  CREATE TYPE eventstatus AS ENUM ('UPCOMING', 'REGISTRATION_OPEN', 'REGISTRATION_CLOSED', 'ONGOING', 'COMPLETED', 'CANCELLED');
  CREATE TYPE registrationstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'WAITLISTED', 'CANCELLED');
  ```
- Because model metadata and migration definitions use identical names, Alembic autogeneration does not attempt to drop, recreate, or rename these types.

---

## 6. AUTOGENERATION ACCURACY & ZERO DRIFT

Alembic `compare_metadata` and `produce_migrations` were executed against an upgraded baseline database:
- **Autogenerate Operations Count:** `0`
- **Schema Drift Detected:** `None`
- **Result:** Complete 100% synchronization between `Base.metadata` (all 22 models) and `0001_initial_baseline.py`.

---

## 7. MODEL-TO-BASELINE DISCREPANCY AUDIT

| Item | Model Representation | Baseline Representation | Discrepancy Classification | Resolution / Impact |
|---|---|---|---|---|
| Event Enums | `SQLEnum(..., name="...")` | `sa.Enum(..., name='...')` | **None** | Completely identical; zero drift |
| Bounded VARCHARs | `String(100)`, `String(50)`, etc. | `sa.String(length=100)`, etc. | **None** | Completely identical; zero drift |
| Active Flags (`is_active`, `resolved`) | `Column(Integer, default=1/0)` | `sa.Column('is_active', sa.Integer())` | **None** | Identical integer types; preserves API and verifier compatibility |
| JSON-like Fields (`prizes`, `gallery_images`) | `Column(Text)` | `sa.Column('prizes', sa.Text())` | **None** | Portable across SQLite and PostgreSQL |
| Risk Log Student ID | `Column(Integer, nullable=True)` | `sa.Column('student_id', sa.Integer())` | **None** | Identical unconstrained column; prevents FK drift |

---

## 8. TEST EXECUTION & RESULTS

### 8.1 Dedicated Dual-Dialect Suite (`tests/test_dialect_migrations.py`)
10 tests implemented and verified:
1. `TestAlembicRevisionGraph.test_single_authoritative_head`: PASSED
2. `TestAlembicRevisionGraph.test_revision_metadata`: PASSED
3. `TestSQLiteMigrationExecution.test_full_upgrade_downgrade_reupgrade_cycle`: PASSED
4. `TestSQLiteMigrationExecution.test_repeated_upgrade_head_is_idempotent`: PASSED
5. `TestAutogenerationAccuracy.test_zero_metadata_drift_against_baseline`: PASSED
6. `TestPostgreSQLMigrationSupport.test_postgresql_offline_sql_generation`: PASSED
7. `TestPostgreSQLMigrationSupport.test_postgresql_offline_downgrade_sql_generation`: PASSED
8. `TestDialectEnvironmentAndSecurity.test_url_normalization_postgres_schemes`: PASSED
9. `TestDialectEnvironmentAndSecurity.test_unsupported_dialect_raises_value_error`: PASSED
10. `TestDialectEnvironmentAndSecurity.test_credential_masking_in_migration_logging`: PASSED

### 8.2 Full Test Suite Regression Summary
- **Backend Test Suite:** **263 passed in 82.07s** (up from 253; 0 failures, 0 errors, 0 skipped).
- **Frontend Test Suite:** **20 passed in 176ms** (0 failures, 0 skipped).
- **Database Safety Verification:**
  - Database: `campus_automation.db`
  - Size: 290,816 bytes (100% unmodified)
  - SHA-256: `BACA55EBD284E474EF79C45D01F1B311C7C8E4F9A779BCB99A596A46798CE227`

---

## 9. DEFERRED MIGRATIONS (PHASE 20 SCOPE)

The following schema transformations are intentionally deferred until live PostgreSQL staging migration:
1. **Integer to Boolean Column Type Alterations:**
   - `announcements.is_active` (`INTEGER` -> `BOOLEAN`)
   - `schedules.is_active` (`INTEGER` -> `BOOLEAN`)
   - `risk_logs.resolved` (`INTEGER` -> `BOOLEAN`)
2. **Text to Native JSONB:**
   - `events.prizes` (`TEXT` -> `JSONB`)
   - `clubs.gallery_images` (`TEXT` -> `JSONB`)
   - `clubs.social_media_links` (`TEXT` -> `JSONB`)
3. **Formal Foreign Key Creation on Loose Identifiers:**
   - `risk_logs.student_id` -> `students.id` (`ON DELETE SET NULL`)

---

## 10. SAFE OPERATOR INSTRUCTIONS FOR FUTURE MIGRATIONS

### 1. Generating Migrations Offline (Reviewing SQL Before Execution):
```bash
# SQLite offline DDL
alembic upgrade head --sql

# PostgreSQL offline DDL
alembic -x db="postgresql+psycopg://user:pass@host:5432/db" upgrade head --sql
```

### 2. Autogenerating New Revisions:
```bash
# Generate revision from model changes (must be reviewed and tested before applying)
alembic revision --autogenerate -m "describe_schema_change"
```

### 3. Applying Migrations Safely:
- Never apply migrations directly against production without a verified snapshot backup.
- In SQLite environments, always verify foreign keys with `PRAGMA foreign_key_check;` and `PRAGMA integrity_check;`.
- In PostgreSQL environments, ensure migrations run inside transactional blocks and verify permissions on custom enum types.
