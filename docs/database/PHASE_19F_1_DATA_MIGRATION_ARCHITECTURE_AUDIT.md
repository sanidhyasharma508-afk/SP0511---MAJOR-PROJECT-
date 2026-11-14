# Phase 19F.1-G — Cross-Dialect Data Migration Architecture Audit

**Project:** Campus Automation System (MARVEL)  
**Workspace:** `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`  
**Branch:** `main`  
**Phase:** 19F.1-G  
**Source Database:** SQLite 3 (`campus_automation.db`)  
**Target Database:** PostgreSQL 16+ (Staging / Production)  
**Mode:** READ-ONLY ARCHITECTURAL AUDIT & MIGRATION DESIGN (NO DATA MODIFIED)

---

## 1. Strict Safety Boundary & Audit Mandate

This document completes the Phase 19F.1 cross-dialect data migration architecture audit. In accordance with strict architectural safety guidelines:

- **Read-Only Audit Only:** No data migration was performed.
- **Source Database Immutability:** `campus_automation.db` was accessed strictly with SQLite URI read-only mode (`mode=ro`). No records were inserted, modified, or deleted. No schema or Alembic stamping operations were performed.
- **Zero Production or Staging Connections:** No connection was opened to production PostgreSQL, Supabase, or external databases. No production credentials were used.
- **Zero Schema Creation or Destruction:** No databases or tables were created, dropped, stamped, or migrated.
- **Scope:** Architecture design, inventory audit, data quality analysis, type conversion matrix, sequence synchronization safety, checkpoint atomicity, and unambiguous canonical checksum specification.

---

## 2. Complete Source Data Inventory (22 Tables, 60 Rows)

The source SQLite database contains **22 domain tables**:
- **13 Populated Tables** containing exactly **60 rows**.
- **9 Empty Tables** containing **0 rows**.
All 22 tables utilize single-column integer primary keys (`id`).

### Table Inventory Breakdown

| # | Table Name | Status | Row Count | Primary Key Range | Foreign Key Dependencies | Unique Constraints / Indexes | Sequence Restart Val |
| :---: | :--- | :---: | :---: | :--- | :--- | :--- | :---: |
| 1 | `announcements` | Populated | 3 | `id` (1..3) | None | `ix_announcements_id` | 4 |
| 2 | `clubs` | Populated | 7 | `id` (1..7) | None | `name` (unique), `ix_clubs_id` | 8 |
| 3 | `device_fingerprints` | **Empty** | **0** | `id` (none) | None | `device_id` (unique), `ix_device_fingerprints_id`, `student_id` | 1 |
| 4 | `events` | Populated | 4 | `id` (1..4) | None | `ix_events_category`, `ix_events_id`, `ix_events_name` | 5 |
| 5 | `qr_attendance_logs` | **Empty** | **0** | `id` (none) | None | `ix_qr_attendance_logs_id`, `session_id`, `student_id` | 1 |
| 6 | `qr_attendance_sessions` | Populated | 1 | `id` (1) | None | `session_id` (unique), `faculty_id`, `id` | 2 |
| 7 | `risk_logs` | Populated | 2 | `id` (1..2) | None | `ix_risk_logs_id` | 3 |
| 8 | `schedule_feedback` | **Empty** | **0** | `id` (none) | None | `ix_schedule_feedback_id` | 1 |
| 9 | `schedules` | Populated | 6 | `id` (1..6) | None | `ix_schedules_id` | 7 |
| 10 | `students` | Populated | 6 | `id` (1..6) | None | `roll_no` (unique), `ix_students_id` | 7 |
| 11 | `club_activities` | Populated | 1 | `id` (1) | `club_id` $\rightarrow$ `clubs.id` | `ix_club_activities_id` | 2 |
| 12 | `club_attendance` | **Empty** | **0** | `id` (none) | `club_id` $\rightarrow$ `clubs.id` | `ix_club_attendance_id` | 1 |
| 13 | `event_registrations` | **Empty** | **0** | `id` (none) | `event_id` $\rightarrow$ `events.id` | `(event_id, student_id)` (unique), `id`, `student_id` | 1 |
| 14 | `event_leaderboard` | **Empty** | **0** | `id` (none) | `event_id` $\rightarrow$ `events.id` | `ix_event_leaderboard_id` | 1 |
| 15 | `event_announcements` | **Empty** | **0** | `id` (none) | `event_id` $\rightarrow$ `events.id` | `ix_event_announcements_id` | 1 |
| 16 | `qr_attendance_records` | Populated | 1 | `id` (1) | `session_id` $\rightarrow$ `qr_attendance_sessions.id` | `(session_id, roll_number)` (unique), `(session_id, student_id)` (unique), `id`, `student_id`, `roll_number` | 2 |
| 17 | `club_members` | Populated | 1 | `id` (1) | `club_id` $\rightarrow$ `clubs.id`, `student_id` $\rightarrow$ `students.id` | `(club_id, student_id)` (unique), `ix_club_members_id` | 2 |
| 18 | `users` | Populated | 4 | `id` (1..4) | `linked_student_id` $\rightarrow$ `students.id` | `username` (unique), `email` (unique), `ix_users_id` | 5 |
| 19 | `complaints` | Populated | 2 | `id` (1..2) | `student_id` $\rightarrow$ `students.id` | `ix_complaints_id` | 3 |
| 20 | `attendance` | Populated | 22 | `id` (1..22) | `student_id` $\rightarrow$ `students.id` | `ix_attendance_id` | 23 |
| 21 | `study_tasks` | **Empty** | **0** | `id` (none) | `user_id` $\rightarrow$ `users.id` | `ix_study_tasks_id`, `user_id` | 1 |
| 22 | `complaint_history` | **Empty** | **0** | `id` (none) | `complaint_id` $\rightarrow$ `complaints.id` | `ix_complaint_history_id`, `complaint_id` | 1 |
| **TOTALS** | **22 Tables** | **13 Pop / 9 Empty** | **60** | — | **13 Explicit Foreign Keys** | **33 Indexes / Constraints** | — |

### Inventory Summary
- **Total Tables:** 22
- **Populated Tables (13):** `announcements` (3), `attendance` (22), `club_activities` (1), `club_members` (1), `clubs` (7), `complaints` (2), `events` (4), `qr_attendance_records` (1), `qr_attendance_sessions` (1), `risk_logs` (2), `schedules` (6), `students` (6), `users` (4).
- **Empty Tables (9):** `club_attendance` (0), `complaint_history` (0), `device_fingerprints` (0), `event_announcements` (0), `event_leaderboard` (0), `event_registrations` (0), `qr_attendance_logs` (0), `schedule_feedback` (0), `study_tasks` (0).
- **Total Records:** Exactly **60 rows**.

---

## 3. Data-Quality Audit: Executed vs. Designed Checks

Every check in this section was **ACTUALLY EXECUTED** against `campus_automation.db` using read-only Python and SQLite inspection scripts (`scratch/audit_sqlite_data.py`, `scratch/detailed_audit.py`). No sensitive record contents are exposed.

| # | Quality Check Category | Tables & Columns Examined | Validation Method | Violations Found | Execution Status |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **1** | **Duplicate Primary Keys** | All 22 domain tables on `id` column. | `SELECT id, COUNT(*) FROM "tbl" GROUP BY id HAVING COUNT(*) > 1;` | **0** | **ACTUALLY EXECUTED** |
| **2** | **Duplicate Unique Keys** | `users(username)`, `users(email)`, `students(roll_no)`, `clubs(name)`, `qr_attendance_sessions(session_id)`, `club_members(club_id, student_id)`, `qr_attendance_records(session_id, roll_number)`, `qr_attendance_records(session_id, student_id)`, `event_registrations(event_id, student_id)`, `device_fingerprints(device_id)`. | `SELECT cols, COUNT(*) FROM "tbl" WHERE col1 IS NOT NULL GROUP BY cols HAVING COUNT(*) > 1;` | **0** | **ACTUALLY EXECUTED** |
| **3** | **Orphaned Foreign Keys** | All 13 foreign keys across `attendance`, `club_activities`, `club_attendance`, `club_members`, `complaint_history`, `complaints`, `event_announcements`, `event_leaderboard`, `event_registrations`, `qr_attendance_records`, `study_tasks`, `users`. | `PRAGMA foreign_key_check;` plus cross-table join analysis (`LEFT JOIN ... WHERE parent.id IS NULL`). | **0** | **ACTUALLY EXECUTED** |
| **4** | **Invalid Enum Values** | `events.category`, `events.status`, `event_registrations.status`. | Checked `SELECT DISTINCT` against Python enum definitions (`EventCategory`, `EventStatus`, `RegistrationStatus`). Distinct values: `'TECHNICAL'`, `'CULTURAL'`, `'SPORTS'`, `'REGISTRATION_OPEN'`. | **0** | **ACTUALLY EXECUTED** |
| **5** | **Boolean Domain Violations** | 28 boolean-designated columns across `users`, `clubs`, `club_members`, `events`, `event_registrations`, `event_announcements`, `qr_attendance_sessions`, `qr_attendance_records`, `qr_attendance_logs`, `device_fingerprints`, `study_tasks`, `schedules`, `announcements`, `risk_logs`. | Checked `SELECT DISTINCT col, typeof(col)` to verify values are strictly `0` or `1`. Zero non-binary or out-of-range integer values. | **0** | **ACTUALLY EXECUTED** |
| **6** | **DateTime Consistency** | All datetime columns across all 22 tables (`created_at`, `updated_at`, `lecture_date`, `lecture_start_time`, `marked_at`, `start_date`, `end_date`, `date`, `registration_start_date`, etc.). | Regex format matching (`^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$`) and `datetime.fromisoformat()` parsing. | **0** | **ACTUALLY EXECUTED** |
| **7** | **Malformed JSON Text** | `events.prizes`, `qr_attendance_sessions.qr_code_data`, `clubs.gallery_images`, `clubs.social_media_links`, `events.gallery_images`, `event_registrations.team_members`, `event_leaderboard.statistics`, `qr_attendance_records.validation_errors`. | Parsed non-empty values via `json.loads()`. `events.prizes` and `qr_attendance_sessions.qr_code_data` parsed as valid JSON dictionaries; all other JSON columns in existing data are NULL. | **0** | **ACTUALLY EXECUTED** |
| **8** | **String Length Violations** | All string columns across all 22 tables against SQLAlchemy model `String(length)` parameters. | Audited `len(val) <= max_length` for all rows. (Max username: 19 $\le 50$; max student name: 20 $\le 100$; max club name: 21 $\le 200$). | **0** | **ACTUALLY EXECUTED** |
| **9** | **Target NOT NULL Violations** | All columns declared `nullable=False` in target SQLAlchemy models. | Scanned rows for unexpected `NULL` values (`SELECT COUNT(*) FROM "tbl" WHERE col IS NULL;`). | **0** | **ACTUALLY EXECUTED** |
| **10** | **Numeric Precision & Range** | Float columns (`events.entry_fee`, `events.score`, `qr_attendance_sessions.center_latitude`, `center_longitude`, `geo_fence_radius_meters`, `qr_attendance_records.student_latitude`, `student_longitude`, `distance_from_center`, `location_accuracy`, `qr_attendance_logs.latitude`, `longitude`). | Validated float ranges (latitude $\in [-90, 90]$, longitude $\in [-180, 180]$, entry_fee $\ge 0$). Zero NaN or infinite values. | **0** | **ACTUALLY EXECUTED** |

---

## 4. Comprehensive Cross-Dialect Type Conversion Matrix

The following table documents the exact conversion rules between SQLite 3 storage representation and PostgreSQL 16+ target types across all 22 domain models:

| Column Category | SQLite 3 Storage Representation | PostgreSQL 16+ Target Type | Conversion & Validation Rules | Distinguishing Model Types from Proposed Changes |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Keys (All 22 Tables)** | `INTEGER PRIMARY KEY` (Autoincrement rowid) | `INTEGER` / `BIGINT` with Identity / Serial Sequence | Insert explicit source ID values directly. Advance sequence post-load using corrected sequence synchronization logic. | Preserves existing model semantics; no schema changes proposed. |
| **Designated Booleans** | `INTEGER` (`0` or `1`) | `BOOLEAN` | Convert integer `1` $\rightarrow$ `True`, `0` $\rightarrow$ `False`, `NULL` $\rightarrow$ `NULL`. Reject values $\notin \{0, 1, \text{NULL}\}$. Affects: `users.is_active`, `clubs.is_active`, `clubs.accepting_members`, `club_members.is_active`, `events.requires_approval`, `events.team_event`, `qr_attendance_sessions.*`, `qr_attendance_records.*`, `device_fingerprints.*`, `study_tasks.is_completed`. | Preserves hardened Phase 19C model annotations (`Boolean`). |
| **Legacy Integer Flags** | `INTEGER` (`0` or `1`) | `INTEGER` | Preserve as raw integers (`0` or `1`). Affects: `schedules.is_active` (default 1), `announcements.is_active` (default 1), `risk_logs.resolved` (default 0). | Models explicitly declare `Integer`. Migration maintains integer semantics to avoid contract drift. |
| **Native Enums** | `TEXT` (`'TECHNICAL'`, `'SPORTS'`, `'REGISTRATION_OPEN'`, etc.) | PostgreSQL Native `ENUM` (`eventcategory`, `eventstatus`, `registrationstatus`) | SQLite stores strings in uppercase. Alembic baseline migration `0001_initial_baseline` creates PostgreSQL enum labels in uppercase. Map string values directly without case modification. Reject strings not in the declared enum domain. | Model uses `SQLEnum(EnumClass, name="...")`. Values match exact baseline labels. |
| **JSON-Like Text Columns** | `TEXT` (JSON serialized or NULL) | `TEXT` (or `JSONB` in future schema revisions) | Validate using `json.loads(val)` before insertion. Canonicalize for reconciliation via `json.dumps(obj, sort_keys=True, separators=(',', ':'))`. | Models currently declare `Text`. Stored as valid JSON text in PostgreSQL. |
| **DateTime (Naive UTC)** | `TEXT` (`'YYYY-MM-DD HH:MM:SS.ffffff'`) | `TIMESTAMP WITHOUT TIME ZONE` | Parse with `datetime.fromisoformat` or `datetime.strptime`. Preserve microsecond precision. Standard for `created_at`, `updated_at`, `lecture_start_time`, `marked_at`. | Preserves existing model default (`DateTime`). |
| **DateTime (Timezone-Aware)** | `TEXT` (`'YYYY-MM-DD HH:MM:SS.ffffff'`) | `TIMESTAMP WITH TIME ZONE` | Parse string and attach UTC timezone (`tzinfo=timezone.utc`). Target for `schedule_feedback` and `announcements` where model declares `DateTime(timezone=True)`. | Preserves existing model timezone declarations. |
| **Floating-Point Metrics** | `REAL` / `FLOAT` (IEEE 754 float) | `DOUBLE PRECISION` | Cast to standard Python `float`. Validate ranges (e.g. coordinates within geographic bounds). Round to 6 decimal places during canonical hashing. | Preserves existing `Float` column types. |
| **Foreign Keys (All 13 FKs)** | `INTEGER` | `INTEGER` referencing parent table `id` | Insert parent tables first via verified topological order (Levels 0 $\rightarrow$ 1 $\rightarrow$ 2). Ensure referenced parent IDs exist prior to batch write. | Preserves existing relational constraints. |
| **Nullable Text / Attributes** | `TEXT` / `VARCHAR` / `NULL` | `VARCHAR(N)` / `TEXT` / `NULL` | Maintain `None` as SQL `NULL`. Do not convert empty string to `NULL` or `NULL` to empty string. | Preserves existing column nullability. |

---

## 5. Safe PostgreSQL Sequence Discovery & Synchronization Design

### Analysis of PostgreSQL Sequence Semantics & Bounds Pitfall
In PostgreSQL, a sequence has an internal state consisting of `last_value` (bigint) and `is_called` (boolean):
- When `nextval(seq)` is called:
  - If `is_called = false`, it returns `last_value` and sets `is_called = true`.
  - If `is_called = true`, it increments `last_value = last_value + 1` and returns the new value.

A critical bug occurs if `setval(seq, 0, true)` is executed on an empty table:
- PostgreSQL sequences default to `MINVALUE 1`. Calling `setval(seq, 0, true)` raises:
  `ERROR: setval: value 0 is out of bounds for sequence "table_id_seq" (1..2147483647)`.
- If `setval(seq, 1, true)` is called on an empty table, the first application `INSERT` calls `nextval()`, which returns `2`, skipping ID `1`.
- If `setval(seq, 1, false)` is called on an empty table:
  `last_value = 1` and `is_called = false`. The first application `nextval()` returns `1`, perfectly preserving the sequence starting point.
- For a populated table with `MAX(id) >= 1`:
  Calling `setval(seq, MAX(id), true)` sets `last_value = MAX(id)` with `is_called = true`. The next `nextval()` returns `MAX(id) + 1`.

### Safe Sequence Discovery Rules
1. **Explicit Schema Scoping:** Limit discovery to target schema `public`.
2. **Catalog Existence Verification:** Check that table and primary key column exist in `information_schema.columns`.
3. **Safe Discovery Function:** Use `pg_get_serial_sequence('public."table_name"', 'id')`.
4. **Skip Unsequenced Columns:** If `pg_get_serial_sequence` returns `NULL`, skip sequence operations safely.
5. **Serial vs. Identity Columns:**
   - `SERIAL`: Underlying sequence attached via default `nextval()`.
   - `IDENTITY` (`GENERATED ALWAYS AS IDENTITY` or `GENERATED BY DEFAULT AS IDENTITY`): Underlying sequence also registered and discoverable via `pg_get_serial_sequence()`. If `ALWAYS`, explicit insert requires `OVERRIDING SYSTEM VALUE`.
6. **Safe Identifier Quoting:** Use `quote_ident()` in PL/pgSQL and parameter bindings in Python. Never concatenate untrusted strings.
7. **Sequence Increment Inspection:** Query `pg_sequences` for non-default `start_value` or `increment_by` if present.

### Safe Stored Procedure (All Tables in Target Schema)
```sql
DO $$
DECLARE
    tbl_name text;
    seq_name text;
    max_val bigint;
BEGIN
    FOR tbl_name IN 
        SELECT c.table_name 
        FROM information_schema.columns c
        JOIN information_schema.tables t 
          ON c.table_name = t.table_name AND c.table_schema = t.table_schema
        WHERE c.table_schema = 'public' 
          AND c.column_name = 'id'
          AND t.table_type = 'BASE TABLE'
    LOOP
        -- 1. Identify sequence attached to primary key 'id' in schema 'public'
        seq_name := pg_get_serial_sequence('public.' || quote_ident(tbl_name), 'id');
        
        -- 2. Skip tables without an auto-incrementing serial/identity sequence
        IF seq_name IS NOT NULL THEN
            EXECUTE format('SELECT MAX(id) FROM public.%I', tbl_name) INTO max_val;
            
            IF max_val IS NULL THEN
                -- Empty table: reset sequence to 1 with is_called = false
                -- so the first inserted record receives id = 1.
                PERFORM setval(seq_name, 1, false);
            ELSE
                -- Populated table: set sequence to max_val with is_called = true
                -- so the next inserted record receives id = max_val + 1.
                PERFORM setval(seq_name, max_val, true);
            END IF;
        END IF;
    END LOOP;
END $$;
```

---

## 6. Migration Architecture & Checkpoint Atomicity Design

### Checkpoint Atomicity Guarantee
To prevent inconsistent states between transferred records and tracking status:
- `_migration_checkpoints` resides inside the destination PostgreSQL database in the same schema (`public._migration_checkpoints`).
- **Single-Transaction Boundary:** For each table $T$, table data insertion, sequence synchronization, and the checkpoint status update to `COMPLETED` execute within the **EXACT SAME PostgreSQL transaction** (`BEGIN ... COMMIT`).
- **All-or-Nothing Guarantee:**
  - If the table transfer succeeds, `COMMIT` atomically commits both the inserted rows and the checkpoint record.
  - If an error, disconnect, or timeout occurs, `ROLLBACK` automatically reverts all inserted rows AND the checkpoint update. Zero partial rows remain in the target table.
- **Handling FAILED and IN_PROGRESS States:**
  - A crash mid-transfer causes PostgreSQL to automatically abort the uncommitted transaction.
  - On restart/resume: The engine inspects `_migration_checkpoints`:
    - Tables marked `PENDING`, `IN_PROGRESS`, or `FAILED` are treated as uncompleted.
    - Before re-migrating, the engine verifies the target table is empty or executes a guarded table reset.
    - **Independent Reconciliation Before Skipping:** Even if a table is marked `COMPLETED` in checkpoints, the engine executes an independent reconciliation check against source SQLite. Only if counts and canonical checksums match 100% is the table skipped. If reconciliation fails, the checkpoint is invalidated and the table is re-migrated.
- **Handling of the 9 Empty Tables:** Empty tables are processed in their topological turn: target table verified empty (0 rows), sequence initialized to `(1, false)`, checkpoint committed with `rows_migrated = 0`, and reconciliation confirms 0 = 0.
- **Handling of Circular Dependencies (Future-Proofing):** If circular foreign keys are introduced in future revisions:
  - *Two-Pass Insertion:* Insert rows with nullable circular foreign keys set to `NULL`; then execute an `UPDATE` pass once all parent rows exist.
  - *Constraint Deferral:* Execute `SET CONSTRAINTS ALL DEFERRED;` within a single multi-table transaction block.

```sql
CREATE TABLE IF NOT EXISTS public._migration_checkpoints (
    table_name VARCHAR(100) PRIMARY KEY,
    status VARCHAR(20) NOT NULL, -- PENDING, IN_PROGRESS, COMPLETED, FAILED
    rows_migrated INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    source_checksum VARCHAR(64),
    target_checksum VARCHAR(64),
    error_message TEXT
);
```

---

## 7. Unambiguous Canonical Checksum Specification (TLVE)

To mathematically prove data equality across heterogeneous engines without false matches or false alarms, reconciliation uses **Tag-Length-Value Encoding (TLVE)**.

### Encoding Format
Every field value is serialized as: `[TAG][BYTE_LENGTH]:[PAYLOAD]`

| Type Tag | Meaning | Encoding Rule | Example |
| :---: | :--- | :--- | :--- |
| `N` | SQL NULL | Fixed 0 length: `N0:` | `None` $\rightarrow$ `N0:` |
| `B` | Boolean | Fixed 1 length: `B1:T` or `B1:F` | `True` $\rightarrow$ `B1:T`, `False` $\rightarrow$ `B1:F` |
| `I` | Integer | ASCII decimal string: `I<len>:<val>` | `42` $\rightarrow$ `I2:42`, `-5` $\rightarrow$ `I2:-5` |
| `F` | Float | IEEE 754 64-bit big-endian hex: `F16:<16_hex_digits>` | `12.3456701` $\rightarrow$ `F16:4028b0fbabdd68fc` |
| `S` | String / Text | Exact UTF-8 bytes: `S<len>:<bytes>`. **NO TRIMMING.** | `"hello"` $\rightarrow$ `S5:hello`, `" hello "` $\rightarrow$ `S7: hello ` |
| `J` | JSON Text | Normalized JSON: `json.dumps(obj, sort_keys=True, separators=(',', ':'))` | `{"b":1,"a":2}` $\rightarrow$ `J13:{"a":2,"b":1}` |
| `D` | Naive DateTime | ISO format with microseconds: `D26:<YYYY-MM-DDTHH:MM:SS.ffffff>` | `2026-11-09 10:00:00` $\rightarrow$ `D26:2026-11-09T10:00:00.000000` |
| `Z` | UTC Aware DateTime | Normalized to UTC ISO format: `Z32:<YYYY-MM-DDTHH:MM:SS.ffffff+00:00>` | `2026-11-09 15:30:00+05:30` $\rightarrow$ `Z32:2026-11-09T10:00:00.000000+00:00` |
| `E` | Native Enum | Exact uppercase string: `E<len>:<val>` | `'TECHNICAL'` $\rightarrow$ `E9:TECHNICAL` |

### Disambiguation Proofs
1. **SQL NULL vs Literal String `"<NULL>"`:**
   - SQL NULL encodes as `N0:`.
   - String `"<NULL>"` encodes as `S6:<NULL>`.
   - Result: Distinct byte representations; zero collision possibility.
2. **Whitespace Preservation:**
   - `"hello"` encodes as `S5:hello`.
   - `" hello "` encodes as `S7: hello `.
   - Result: Length prefix and byte stream prevent silent whitespace tampering.
3. **Floating-Point Precision:**
   - `12.3456701` encodes as `F16:4028b0fbabdd68fc`.
   - `12.3456702` encodes as `F16:4028b0fbaf386750`.
   - Result: Distinct hex values; no silent rounding equality.
4. **Timezone Normalization:**
   - `2026-11-09 15:30:00+05:30` and `2026-11-09 10:00:00+00:00` both normalize to `Z32:2026-11-09T10:00:00.000000+00:00`.
   - Naive timestamp `2026-11-09 10:00:00` encodes as `D26:2026-11-09T10:00:00.000000`, distinctly flagged with tag `D` rather than tag `Z`.
5. **JSON Null vs SQL NULL vs String `"null"`:**
   - SQL NULL encodes as `N0:`.
   - JSON null encodes as `J4:null`.
   - String `"null"` encodes as `S4:null`.

### Row and Table Checksum Computation
1. Sort columns alphabetically by column name: $C_1, C_2, \dots, C_k$.
2. Row byte vector: $B(r) = \text{TLVE}(r[C_1]) + \text{TLVE}(r[C_2]) + \dots + \text{TLVE}(r[C_k])$.
3. Row hash: $H(r) = \text{SHA256}(B(r))$.
4. Table hash: Sort rows deterministically by Primary Key ascending ($id_1 < id_2 < \dots < id_N$).
   $$\text{Checksum}_{\text{table}} = \text{SHA256}\left(\sum_{r \in \text{Rows}} H(r)\right)$$

---

## 8. Guarded Rollback Design

Generic destructive commands (e.g. unconstrained `TRUNCATE ... CASCADE`) are prohibited. The rollback architecture enforces strict safety controls:

1. **Destination Verification:** Target connection URL must be validated with `normalize_db_identity()` and `is_production_database_target()`.
2. **Production Rejection:** Rollback operations targeting production environments (`prod`, `production`, `live`, cloud hosts) are unconditionally rejected with fatal `BackupError`.
3. **Explicit Dual Authorization:** Destructive rollback requires both:
   - `allow_destructive_rollback=True`
   - `confirm_rollback_database_name="<exact_target_db>"` matching target database identity.
4. **Pre-Rollback Re-Verification:** Target identity is re-checked immediately before issuing any DDL/DML.
5. **Preference for Database Recreation:** In staging/testing environments, dropping and recreating the disposable isolated target database is preferred over cascaded table truncation:
   ```sql
   -- Preferred safe staging reset:
   DROP DATABASE IF EXISTS campus_automation_staging_disposable;
   CREATE DATABASE campus_automation_staging_disposable;
   ```
6. **Per-Table Rollback (If Isolated Table Fails):**
   - Truncate target table within guarded transaction.
   - Delete corresponding record from `_migration_checkpoints WHERE table_name = :tbl`.
7. **Source SQLite Immutability:** The source database is opened strictly in read-only mode (`mode=ro`). Rollback operations can never reach or affect `campus_automation.db`.

---

## 9. Operational Runbook (Future Phase 19F.2 Execution)

*Note: Documented procedure for future execution only. No migration operations are performed in Phase 19F.1.*

1. **Step 1: Source Preflight**
   - Verify `campus_automation.db` file size (`290,816` bytes) and SHA-256 (`BACA55EBD284E474EF79C45D01F1B311C7C8E4F9A779BCB99A596A46798CE227`).
   - Run `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;`.
2. **Step 2: Verified SQLite Online Backup**
   - Create a point-in-time backup using `SQLiteBackupAdapter` with companion `.manifest.json`.
3. **Step 3: Destination PostgreSQL Preflight**
   - Execute heartbeat (`SELECT 1;`).
   - Run `is_production_database_target()` guard.
4. **Step 4: Target Schema Conformance**
   - Verify target status is `MIGRATED` with revision `0001_initial_baseline`.
   - Confirm all 22 domain tables exist and are empty (`count == 0`).
5. **Step 5: Initialize Checkpoint Tracking**
   - Provision `_migration_checkpoints` table in PostgreSQL.
6. **Step 6: Controlled Topological Batch Transfer**
   - Iterate Level 0 $\rightarrow$ Level 1 $\rightarrow$ Level 2.
   - For each table: stream rows from SQLite under `mode=ro`, convert types via TLVE rules, insert batch in transaction, update checkpoint to `COMPLETED` in the same transaction, and commit.
7. **Step 7: Sequence Synchronization**
   - Run safe sequence procedure: set empty tables to `(1, false)` and populated tables to `(max_id, true)`.
8. **Step 8: Foreign Key & Constraint Verification**
   - Validate PostgreSQL foreign key constraints across all 22 tables.
9. **Step 9: Three-Tier Reconciliation**
   - Tier 1: Row count equality (60 total rows, 13 populated, 9 empty).
   - Tier 2: Primary-key set equality ($\text{PK}_{\text{src}} = \text{PK}_{\text{dst}}$).
   - Tier 3: TLVE Canonical Checksum equality ($\text{Checksum}_{\text{src}} = \text{Checksum}_{\text{dst}}$).
10. **Step 10: Generate Signed Manifest**
    - Generate `migration_manifest_2026xxxx.json` capturing execution metadata and checksums.
11. **Step 11: Rollback Procedure (If Aborted)**
    - If reconciliation differs or execution halts:
      - Apply Guarded Rollback procedure to disposable target database.
      - Source SQLite database remains untouched.

---

## 10. Testing Strategy (Executed vs. Proposed)

### A. Executed Audit Tests (Completed in Phase 19F.1)
The following 11 tests were **ACTUALLY EXECUTED** against `campus_automation.db`:
1. `test_source_database_file_integrity`: PASSED (Size: 290,816 bytes, SHA-256 verified).
2. `test_sqlite_pragmas`: PASSED (`integrity_check` ok, `foreign_key_check` 0 errors).
3. `test_primary_key_uniqueness`: PASSED (0 duplicate PKs across all 22 tables).
4. `test_unique_constraint_integrity`: PASSED (0 duplicate unique keys across all tables).
5. `test_foreign_key_referential_integrity`: PASSED (0 orphan records).
6. `test_native_enum_values_and_casing`: PASSED (All enum values valid and match uppercase baseline labels).
7. `test_boolean_domain_adherence`: PASSED (All boolean columns contain strictly `0` or `1`).
8. `test_datetime_format_consistency`: PASSED (All timestamp strings parse cleanly).
9. `test_json_syntax_validity`: PASSED (All non-empty JSON columns parse via `json.loads()`).
10. `test_string_length_caps_and_nullability`: PASSED (0 length violations, 0 null violations).
11. `test_canonical_checksum_disambiguation`: PASSED (Verified TLVE disambiguation of NULL, strings, floats, datetimes, and JSON in `scratch/test_canonical_checksum.py`).

### B. Proposed Tests for Phase 19F.2 Implementation
The following test suites are **PROPOSED** for implementation in Phase 19F.2:
- **Unit Tests:**
  - Type converter functions (integer to boolean, string to timestamp, enum mapping).
  - Canonical row string formatting and checksum determinism.
  - Sequence synchronization calculation logic for empty and populated tables.
- **SQLite Integration Tests:**
  - Read-only connection rejection of write queries (`OperationalError: attempt to write a readonly database`).
  - Topological sorter DAG resolution on actual 22 models.
- **Mocked PostgreSQL Tests:**
  - Checkpoint tracking and resumption after simulated batch failure.
  - Per-table transaction rollback on simulated database exception.
  - Production database target rejection (`is_production_database_target`).
- **Real Staging Integration Tests:**
  - Full end-to-end data migration into a clean, disposable PostgreSQL 16+ instance.
  - Post-migration application `INSERT` key collision test (verifying sequence advancement).
  - Three-tier reconciliation pass with 100% checksum agreement.

---

## 11. Untested Assumptions & Explicit Limitations

To maintain strict engineering transparency, the following items are explicitly documented as **UNTESTED** on this host:
1. **Live PostgreSQL Daemon Transfer:** No data has been transferred to a running PostgreSQL 16+ instance because no local PostgreSQL daemon or Docker service is installed on this host.
2. **Live Staging Reconciliation:** Three-tier reconciliation between live PostgreSQL and SQLite has not yet been executed against real PostgreSQL storage.
3. **Completion Boundary:** Phase 19F.1 is strictly an architectural audit and design. Data migration execution is scheduled for Phase 19F.2 in an authorized staging environment.

---

## 12. Source Database Safety & Immutability Verification

To guarantee complete data preservation, `campus_automation.db` was verified before and after all audit operations:

- **Path:** `MARVEL-main/campus_automation.db`
- **File Length:** `290,816` bytes (exact match)
- **SHA-256 Checksum:** `BACA55EBD284E474EF79C45D01F1B311C7C8E4F9A779BCB99A596A46798CE227` (exact match)
- **Domain Tables:** 22 (13 populated, 9 empty)
- **Total Records:** Exactly 60 rows
- **Status:** **Untouched and pristine.** Zero writes, updates, stamps, or schema modifications occurred.
