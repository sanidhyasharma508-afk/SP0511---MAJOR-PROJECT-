# PHASE 19 — TASK 19A: POSTGRESQL COMPATIBILITY AUDIT & MIGRATION DESIGN

**Project:** Campus Automation System (MARVEL)  
**Workspace:** `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`  
**Branch:** `main`  
**Date:** November 2026  
**Status:** AUDIT & DESIGN COMPLETE (READ-ONLY AUDIT PHASE)  

---

## 1. Executive Summary & Existing Database Architecture

### 1.1 Context & Purpose
The Campus Automation System (MARVEL) is evolving from a localized, single-file SQLite database into an enterprise-grade, high-concurrency, multi-college campus automation platform backed by PostgreSQL 16+.

This document constitutes the comprehensive technical audit and architectural migration blueprint for Task 19A. In accordance with strict architectural governance:
- **Scope:** Audit and design only. No application source code has been altered.
- **Data Protection:** The live SQLite database ([`campus_automation.db`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/campus_automation.db)) remains pristine and untouched.
- **Dual-Engine Principle:** SQLite support is intentionally preserved for zero-dependency local development and lightning-fast in-memory unit testing, while PostgreSQL is established as the staging and production database.

### 1.2 Current SQLite Database State
The existing development database was verified prior to and following this audit:
- **Physical Path:** [`campus_automation.db`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/campus_automation.db)
- **File Size:** 290,816 bytes (284 KB)
- **Cryptographic SHA-256 Checksum:** `baca55ebd284e474ef79c45d01f1b311c7c8e4f9a779bcb99a596a46798ce227`
- **Domain Tables:** 22 tables (verified against SQLAlchemy `Base.metadata`)
- **Alembic Version State:** Unstamped (`alembic_version` table absent)
- **Database Readiness Classification:** `COMPATIBLE_UNSTAMPED` (verified via `DatabaseVerifier`)

### 1.3 The Production Imperative: Why SQLite Cannot Serve Production MARVEL
During Phase 14 and Phase 17 stress tests, SQLite exhibited structural operational limits under simulated multi-student campus workloads:
1. **Single-Writer Bottleneck:** SQLite locks the entire database file during write transactions. Under high-throughput scenarios (e.g. 500 students scanning a 3-minute QR attendance code simultaneously at 9:00 AM), SQLite transactions queue up and fail with `sqlite3.OperationalError: database is locked`.
2. **Multi-Worker Crash Hazard:** In multi-worker application deployments (e.g., Uvicorn `--workers 4` or Gunicorn), worker processes compete for the same OS file lock. Because SQLite locks operate at the file-system level without a centralized memory manager across separate processes, inter-process lock contention results in frequent HTTP 500 errors.
3. **Type Laxity vs. Strict Enterprise Schema:** SQLite uses *type affinity* rather than strict typing. It permits booleans to be stored as arbitrary integers, ignores string length bounds, lacks native JSONB indexing, and does not validate datetimes against real timestamp types.
4. **Lack of Row-Level Locking:** SQLite does not support `SELECT ... FOR UPDATE`. Critical campus workflows—such as event registration caps (preventing overselling seats) and QR code replay prevention—require atomic row-level locks.

### 1.4 Architectural Vision: The Dual-Engine Platform
The target architecture preserves SQLite for zero-dependency local developer bootstrapping and ultra-fast in-memory test suites (`sqlite:///:memory:` running 225 unit tests in seconds), while designating PostgreSQL 16+ as the authoritative staging and production engine with full connection pooling, MVCC concurrency, native JSONB, and row-level locks.

```
+-----------------------------------------------------------------------------------+
|                        FASTAPI APPLICATION LAYER                                 |
|                                                                                   |
|  [routes/auth] [routes/students] [routes/qr_attendance] [routes/events] ...       |
+-----------------------------------------+-----------------------------------------+
                                          |
                               [backend/database.py]
                                          |
                      +-------------------+-------------------+
                      |                                       |
           (Development / CI)                       (Staging / Production)
                      |                                       |
         +------------v------------+              +-----------v-------------+
         |      SQLite Engine      |              |    PostgreSQL Engine    |
         |                         |              |                         |
         | - Zero-config local dev |              | - Multi-Worker MVCC     |
         | - In-memory test runner |              | - QueuePool (10+20)     |
         | - PRAGMA foreign_keys   |              | - Row Locks (FOR UPDATE)|
         | - NullPool/StaticPool   |              | - JSONB Indexing        |
         +-------------------------+              +-------------------------+
```

---

## 2. Model-by-Model PostgreSQL Compatibility Matrix (All 22 Models)

The codebase defines exactly 22 SQLAlchemy ORM models across 8 model files in [`backend/models/`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/). Every single model was inspected for PostgreSQL compatibility.

| # | Model Class | DB Table | Source File | PK Strategy | Column Data Types & Incompatibilities | Foreign Keys & Constraints | PostgreSQL Migration Assessment |
|---|-------------|----------|-------------|-------------|---------------------------------------|----------------------------|---------------------------------|
| 1 | `User` | `users` | [`user.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/user.py) | `id: Integer` (autoincrement) | `is_active: Boolean` (SQLite 0/1 vs PG native bool); `created_at, updated_at: DateTime` | `linked_student_id -> students.id`; Unique: `username`, `email` | **COMPATIBLE WITH CONVERSION:** Needs integer-to-boolean casting and sequence sync. |
| 2 | `Student` | `students` | [`student.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/student.py) | `id: Integer` (autoincrement) | `name, roll_no, department, section`: Unbounded `String` (maps to `TEXT` or `VARCHAR` without limit) | Root Table; Unique: `roll_no` | **COMPATIBLE:** Root entity. Recommend explicit lengths (`VARCHAR(100)`). |
| 3 | `StudyTask` | `study_tasks` | [`study_task.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/study_task.py) | `id: Integer` (autoincrement) | `is_completed: Boolean` (SQLite 0/1); `due_date, completed_at, reminder_at: DateTime` | `student_id -> students.id` (CASCADE) | **COMPATIBLE WITH CONVERSION:** Needs boolean conversion. |
| 4 | `Club` | `clubs` | [`club.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/club.py) | `id: Integer` (autoincrement) | `gallery_images, social_media_links: Text` (stores raw JSON strings); `is_active, accepting_members: Boolean` | Root Table; Unique: `name`; `created_by: Integer` (loose, no FK) | **COMPATIBLE:** JSON strings should eventually migrate to native `JSONB`. |
| 5 | `ClubActivity` | `club_activities` | [`club.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/club.py) | `id: Integer` (autoincrement) | `budget, actual_cost: Float` | `club_id -> clubs.id` (CASCADE); `created_by: Integer` (loose) | **COMPATIBLE.** |
| 6 | `ClubMember` | `club_members` | [`club.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/club.py) | `id: Integer` (autoincrement) | `is_active: Boolean` | `club_id -> clubs.id` (CASCADE); `student_id -> students.id` (CASCADE); `UniqueConstraint(club_id, student_id)` | **COMPATIBLE WITH CONVERSION.** |
| 7 | `ClubAttendance` | `club_attendance` | [`club.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/club.py) | `id: Integer` (autoincrement) | `attended: Boolean` | `club_id -> clubs.id` (CASCADE); `activity_id -> club_activities.id` (CASCADE); `student_id: Integer` (loose, missing FK); `UniqueConstraint(activity_id, student_id)` | **COMPATIBLE:** Add FK `student_id -> students.id` in future revision. |
| 8 | `Event` | `events` | [`events.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/events.py) | `id: Integer` (autoincrement) | `category: SQLEnum(EventCategory)`; `status: SQLEnum(EventStatus)`; `gallery_images, prizes: Text` (JSON); `requires_approval, team_event: Boolean` | Root Table; `created_by: Integer` (loose) | **CRITICAL ENUM ISSUE:** Python model values are lowercase (`sports`), but baseline Alembic enum has uppercase names (`SPORTS`). PG will throw `DataError`. Must specify `values_callable`. |
| 9 | `EventRegistration` | `event_registrations` | [`events.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/events.py) | `id: Integer` (autoincrement) | `status: SQLEnum(RegistrationStatus)`; `team_members: Text` (JSON); `team_leader: Boolean`; `student_id: String(50)` (stores roll number string, not integer FK) | `event_id -> events.id` (CASCADE); `UniqueConstraint(event_id, student_id)` | **CRITICAL ENUM ISSUE:** Same enum case mismatch as `Event`. |
| 10 | `EventLeaderboard` | `event_leaderboard` | [`events.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/events.py) | `id: Integer` (autoincrement) | `score: Float`; `statistics: Text` (JSON) | `event_id -> events.id` (CASCADE) | **COMPATIBLE.** |
| 11 | `EventAnnouncement` | `event_announcements` | [`events.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/events.py) | `id: Integer` (autoincrement) | `is_pinned, is_active: Boolean` | `event_id -> events.id` (CASCADE); `created_by: Integer` (loose) | **COMPATIBLE WITH CONVERSION.** |
| 12 | `Complaint` | `complaints` | [`complaint.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/complaint.py) | `id: Integer` (autoincrement) | `title, category, status, priority`: Unbounded `String` | `student_id -> students.id`; `assigned_to: Integer` (loose) | **COMPATIBLE.** |
| 13 | `ComplaintHistory` | `complaint_history` | [`complaint.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/complaint.py) | `id: Integer` (autoincrement) | `old_status, new_status: String(50)` | `complaint_id -> complaints.id` (CASCADE); `changed_by_user_id: Integer` (loose) | **COMPATIBLE.** |
| 14 | `RiskLog` | `risk_logs` | [`risk.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/risk.py) | `id: Integer` (autoincrement) | `resolved: Integer` (default 0, acts as bool); `risk_type, severity: String` (unbounded) | `student_id: Integer` (loose, missing FK) | **COMPATIBLE:** Stays integer in PG unless explicit migration converts to boolean. |
| 15 | `Schedule` | `schedules` | [`schedule.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/schedule.py) | `id: Integer` (autoincrement) | `is_active: Integer` (default 1, acts as bool); `title, event_type: String` (unbounded) | Root Table | **COMPATIBLE.** |
| 16 | `ScheduleFeedback` | `schedule_feedback` | [`schedule_feedback.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/schedule_feedback.py) | `id: Integer` (autoincrement) | `issue_type: String(100)` (uses String, not Enum!); `created_at, resolved_at: DateTime(timezone=True)` | Root Table | **COMPATIBLE:** PostgreSQL maps to native `TIMESTAMPTZ`. |
| 17 | `Announcement` | `announcements` | [`schedule_feedback.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/schedule_feedback.py) | `id: Integer` (autoincrement) | `is_active: Integer` (default 1); `created_at, expires_at: DateTime(timezone=True)` | Root Table | **COMPATIBLE.** |
| 18 | `QRAttendanceSession` | `qr_attendance_sessions` | [`qr_attendance.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/qr_attendance.py) | `id: Integer` (autoincrement) | `center_latitude, center_longitude, geo_fence_radius_meters: Float`; `is_active, is_expired, is_cancelled: Boolean`; `qr_code_data: Text` | Root Table; Unique: `session_id`; `faculty_id: String(50)` (loose) | **COMPATIBLE WITH CONVERSION.** |
| 19 | `QRAttendanceRecord` | `qr_attendance_records` | [`qr_attendance.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/qr_attendance.py) | `id: Integer` (autoincrement) | `student_latitude, student_longitude: Float`; 9 `Boolean` columns (`is_within_geofence`, etc.); `validation_errors: Text` (JSON) | `session_id -> qr_attendance_sessions.id` (CASCADE); `UniqueConstraint(session_id, roll_number)`; `student_id: String(50)` (loose) | **COMPATIBLE WITH CONVERSION:** Extensive boolean conversion required. |
| 20 | `QRAttendanceLog` | `qr_attendance_logs` | [`qr_attendance.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/qr_attendance.py) | `id: Integer` (autoincrement) | 4 `Boolean` columns (`qr_valid`, etc.); `latitude, longitude: Float` | `session_id: Integer` (loose); `student_id: String(50)` (loose) | **COMPATIBLE WITH CONVERSION.** |
| 21 | `DeviceFingerprint` | `device_fingerprints` | [`qr_attendance.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/qr_attendance.py) | `id: Integer` (autoincrement) | `is_active, is_blocked: Boolean` | Unique: `device_id`; `student_id: String(50)` (loose) | **COMPATIBLE WITH CONVERSION.** |
| 22 | `Attendance` | `attendance` | [`attendance.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/models/attendance.py) | `id: Integer` (autoincrement) | `status, remarks: String` (unbounded); `date: DateTime` | `student_id -> students.id`; Indexes: `faculty_id`, `subject_code` | **COMPATIBLE.** |

---

## 3. Concurrency, Connection Pooling & Production Operations

### 3.1 Concurrency Model Comparison
```
Feature                    SQLite (Current)                   PostgreSQL 16+ (Target)
-------------------------  ---------------------------------  -------------------------------------
Concurrency Model          File lock / Single-writer WAL      Multi-Version Concurrency Control (MVCC)
Reader-Writer Contention   Writers block on active readers    Readers NEVER block writers
Multi-Worker Support       Unstable (OS lock collisions)      Native & limitless via connection pool
Row-Level Locking          Unsupported                        Native (`SELECT ... FOR UPDATE`)
Advisory Locks             Unsupported                        Native (`pg_advisory_xact_lock`)
Transaction Isolation      Serialized via file lock           READ COMMITTED (default), REPEATABLE READ, SERIALIZABLE
Connection Pool            NullPool / StaticPool              QueuePool (pre-fork safe, multiplexed)
```

### 3.2 Solving Multi-Worker Failures with Connection Pooling
Under Uvicorn with multiple worker processes (`uvicorn backend.main:app --workers 4`), SQLite fails because separate OS processes cannot coordinate locks on a single `.db` file.

With PostgreSQL, every worker maintains a dedicated `QueuePool` communicating over TCP/UNIX sockets to the PostgreSQL daemon:
- **`pool_size = 10`**: Establishes 10 persistent, pre-authenticated connections per worker process.
- **`max_overflow = 20`**: Permits up to 20 additional burst connections during traffic spikes (e.g., class dismissal attendance rush).
- **`pool_timeout = 30`**: Gracefully blocks incoming requests up to 30s before timing out, preventing instant 500 error cascades.
- **`pool_recycle = 1800`**: Automatically recycles connections older than 30 minutes, preventing TCP dead-pipe drops by intermediate cloud load balancers or firewalls.
- **`pool_pre_ping = True`**: Issues a lightweight test heartbeat (`SELECT 1`) on checkout to discard dead/closed sockets.

### 3.3 Critical Race Condition Remediations via Row-Level Locks (`SELECT FOR UPDATE`)
Two critical business operations require PostgreSQL row-level locks that SQLite cannot provide:
1. **Event Registration Participant Cap ([`backend/routes/events.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/routes/events.py)):**
   - *Problem:* Two students submit registration for the final remaining slot simultaneously. In SQLite, both read `current_participants = 99 / 100`, both pass validation, and both write, causing overselling (101/100).
   - *PostgreSQL Solution:*
     ```python
     event = db.query(Event).filter(Event.id == event_id).with_for_update().first()
     if event.is_full():
         raise HTTPException(status_code=400, detail="Event is full")
     event.current_participants += 1
     ```
2. **Proxy-Free QR Attendance Scanning ([`backend/routes/qr_attendance.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/routes/qr_attendance.py)):**
   - *Problem:* Concurrent scans with duplicate devices or concurrent scan attempts for the same roll number.
   - *PostgreSQL Solution:* Row-level locking on `QRAttendanceSession` and device fingerprint checks inside an atomic transaction.

---

## 4. Multi-College Architecture Readiness

To scale MARVEL into a reusable multi-college platform, multi-tenancy must be designed upfront.

### 4.1 Evaluation of Multi-Tenancy Models

```
Architecture Strategy              Isolation Level  Migration Complexity  Infrastructure Cost  Recommendation
---------------------------------  ---------------  --------------------  -------------------  ----------------------
Model A: Shared Database & Schema  Logical (RLS)    Low (single DB)       Lowest               RECOMMENDED (Default)
Model B: Schema-per-College        Medium (schema)  High (loop schemas)   Moderate             Alternative for mid-tier
Model C: Database-per-College      Physical (DB)    High (N databases)    Highest              Enterprise option
```

### 4.2 Recommended Architecture: Shared Database + Composite Tenant Keys + Row-Level Security (RLS)
1. **Core College Registry Table:**
   ```sql
   CREATE TABLE colleges (
       id SERIAL PRIMARY KEY,
       code VARCHAR(20) UNIQUE NOT NULL,      -- e.g., 'CAMPUS_MAIN', 'ENG_COLLEGE'
       name VARCHAR(200) NOT NULL,
       subdomain VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'main.campus.edu'
       is_active BOOLEAN DEFAULT TRUE,
       created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
   );
   ```
2. **Tenant Discriminator Column:**
   Add `college_id = Column(Integer, ForeignKey("colleges.id"), nullable=False, index=True)` to all tenant-scoped tables.
3. **Composite Unique Constraints:**
   - `users`: `UniqueConstraint('college_id', 'username')` and `UniqueConstraint('college_id', 'email')` (allows same username/email across different colleges).
   - `students`: `UniqueConstraint('college_id', 'roll_no')`.
   - `clubs`: `UniqueConstraint('college_id', 'name')`.
   - `qr_attendance_sessions`: `UniqueConstraint('college_id', 'session_id')`.
4. **PostgreSQL Row-Level Security (RLS):**
   ```sql
   ALTER TABLE students ENABLE ROW LEVEL SECURITY;
   CREATE POLICY student_tenant_isolation ON students
       USING (college_id = current_setting('app.current_college_id')::int);
   ```
   FastAPI middleware extracts the tenant from the authenticated JWT or request domain and executes `SET LOCAL app.current_college_id = :id;` on every database session checkout.

---

## 5. Non-Destructive Data Migration Protocol

The real SQLite database ([`campus_automation.db`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/campus_automation.db)) contains 22 domain tables and live seed records. The migration protocol must guarantee **zero data loss, zero primary key drift, and complete relational integrity**.

### 5.1 Topological Dependency Sort (3-Tier DAG)
Tables must be extracted from SQLite and inserted into PostgreSQL strictly following foreign key dependencies:

```
TIER 0 (Root Nodes - No Incoming Foreign Keys)
---------------------------------------------------------------------------------------------------------
[students] [clubs] [events] [schedules] [schedule_feedback] [announcements] [risk_logs] 
[qr_attendance_sessions] [qr_attendance_logs] [device_fingerprints]
       |          |        |                                          |
       +-----+    |        +---------------+                          |
       |     |    |                        |                          |
       |     v    v                        v                          v
TIER 1 |  [club_activities]       [event_registrations]    [qr_attendance_records]
       |  [club_members]          [event_leaderboard]
       |                          [event_announcements]
       v
  [users] [study_tasks] [complaints] [attendance]
       |          |
       v          v
TIER 2 [club_attendance] [complaint_history]
```

#### Detailed Execution Order:
1. **Tier 0 (10 Tables):** `students`, `clubs`, `events`, `schedules`, `schedule_feedback`, `announcements`, `risk_logs`, `qr_attendance_sessions`, `qr_attendance_logs`, `device_fingerprints`.
2. **Tier 1 (10 Tables):** `users`, `study_tasks`, `club_activities`, `club_members`, `event_registrations`, `event_leaderboard`, `event_announcements`, `complaints`, `attendance`, `qr_attendance_records`.
3. **Tier 2 (2 Tables):** `club_attendance`, `complaint_history`.

### 5.2 Type Transformation Pipeline
During data extraction, values must be transformed before PostgreSQL insertion:
- **Booleans:** Convert integer `0`/`1` to Python `bool` (`False`/`True`).
- **Dates & Times:** Parse ISO-8601 strings into timezone-aware UTC datetime objects.
- **Enums:** Map uppercase/lowercase mismatches explicitly so enum checks succeed.
- **Nulls:** Convert empty strings or sentinel values to SQL `NULL` where appropriate.

### 5.3 PostgreSQL Sequence Synchronization (Mandatory Post-Load)
Because SQLite records have explicit primary keys (1, 2, 3...), inserting them with explicit IDs does NOT advance PostgreSQL internal sequences. If sequences are not updated, the next application insert will fail with `UniqueViolation: duplicate key value violates unique constraint`.

After data import, the following query must execute for all 22 tables:
```sql
SELECT setval(pg_get_serial_sequence('table_name', 'id'), COALESCE((SELECT MAX(id) FROM table_name), 1));
```

### 5.4 Verification & Rollback Protocol
1. **Verification Checks:**
   - Table-by-table row count matching (`sqlite_count == pg_count`).
   - Primary key matching (set of all IDs in SQLite equals set of all IDs in PostgreSQL).
   - Foreign key constraint validation: `SELECT conname FROM pg_constraint WHERE NOT convalidated;`.
   - JSON data payload checksum comparison (excluding timestamp format differences).
2. **Rollback Strategy:**
   - The source SQLite database is accessed exclusively in **read-only mode** (`file:campus_automation.db?mode=ro`).
   - If verification fails at any stage, the PostgreSQL schema is wiped using `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, leaving the original SQLite database completely pristine and unaltered.

---

## 6. Alembic Migration Strategy for PostgreSQL

### 6.1 Dual-Dialect Compatibility
The initial baseline revision [`alembic/versions/0001_initial_baseline.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/alembic/versions/0001_initial_baseline.py) was generated against SQLite with `batch_alter_table`.
- **In [`alembic/env.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/alembic/env.py):**
  - `render_as_batch = is_sqlite` dynamically disables batch mode on PostgreSQL.
  - On PostgreSQL, Alembic emits standard transactional DDL (`ALTER TABLE`, `ADD CONSTRAINT`).
- **Enum Handling:**
  - In PostgreSQL, Alembic requires `sa.Enum` to specify `name='enum_name'`.
  - To prevent casing conflicts, models must specify `values_callable=lambda x: [e.value for e in x]`.

---

## 7. Dual-Engine Architecture Design (Development vs Production)

### 7.1 Cross-Platform Driver Management
In `requirements.txt`:
```txt
# Current problematic entry:
psycopg2-binary>=2.9.9; platform_system != "Windows"

# Recommended cross-platform solution:
psycopg[binary]>=3.2.0; python_version >= "3.10"
# OR universal binary:
psycopg2-binary>=2.9.9
```
`psycopg` (v3) provides official pre-built universal wheels across Windows, macOS, and Linux without needing local C/C++ compilation or PostgreSQL client headers.

### 7.2 Dynamic Engine Initialization ([`backend/database.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/database.py))
```python
DATABASE_URL = settings.get_database_url()

if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool if ":memory:" in DATABASE_URL else pool.NullPool,
        echo=settings.DB_ECHO and settings.is_development,
    )
else:
    # PostgreSQL Configuration
    engine = create_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=settings.DB_ECHO and settings.is_development,
    )
```

---

## 8. Risk Assessment & Prioritized Mitigation Matrix

| Severity | Issue Description | Root Cause | Impact | Proposed Mitigation | Phase / Task |
|---|---|---|---|---|---|
| **CRITICAL** | **Enum Casing Mismatch** | `EventCategory`, `EventStatus`, `RegistrationStatus` use lowercase values in Python but uppercase names in Alembic baseline | `DataError` on every event or registration insert under PG | Add `values_callable` to model Enums; update baseline migration script | **Task 19C** |
| **CRITICAL** | **Sequence Out-of-Sync** | Explicit ID inserts during data load bypass PostgreSQL serial sequences | `UniqueViolation` crashes on subsequent application inserts | Execute `setval(pg_get_serial_sequence(...))` for all 22 tables post-migration | **Task 19F** |
| **CRITICAL** | **Windows Driver Exclusion** | `psycopg2-binary` platform restriction in `requirements.txt` | Windows developers and CI runners cannot connect to PostgreSQL | Migrate to `psycopg[binary]>=3.2` or remove platform restriction | **Task 19B** |
| **HIGH** | **Missing Connection Pooling** | `database.py` does not pass `pool_size` or `pool_pre_ping` to `create_engine` | Connection drops, 500 errors under multi-worker Uvicorn | Configure `QueuePool` with `pool_pre_ping=True` and `pool_recycle=1800` | **Task 19B** |
| **HIGH** | **Unbounded String Fields** | `Student`, `Complaint`, `Attendance` use `Column(String)` without length | Maps to unbounded `TEXT` in PG; impedes length validation & indexing | Add explicit lengths (`String(100)`, `String(200)`) across models | **Task 19C** |
| **HIGH** | **Stringified JSON Storage** | `Club`, `Event`, `QRAttendance` store JSON in `Text` columns | Cannot query inside JSON fields, lack of schema validation | Retain `Text` for backward compatibility, provide optional `JSONB` migration | **Task 19C** |
| **MEDIUM** | **Verifier PRAGMA Incompatibility** | `database_verifier.py` uses SQLite PRAGMAs and expects integer booleans | Verification crashes or produces false positive mismatches on PG | Branch verifier on `dialect.name == "postgresql"`; verify schemas via `pg_catalog` | **Task 19E** |
| **MEDIUM** | **Backup Utility SQLite Lock-In** | `backup_utils.py` relies on `sqlite3.backup` API | Production database backups fail or cannot be triggered | Implement `PostgresBackupAdapter` invoking `pg_dump` | **Task 19E** |
| **MEDIUM** | **Timezone Inconsistencies** | Mix of `DateTime` (naive UTC) and `DateTime(timezone=True)` | Potential timestamp offset confusion during queries | Standardize on UTC timezone-aware datetimes | **Task 19C** |
| **LOW** | **`datetime.utcnow()` Deprecation** | Python 3.12 deprecates naive `datetime.utcnow()` | Deprecation warnings in logs | Migrate to `datetime.now(timezone.utc)` | **Task 19C** |
| **LOW** | **Redundant Primary Key Indexes** | Alembic generated explicit `ix_table_id` indexes on PKs | Extra index maintenance overhead in PostgreSQL | Drop redundant secondary index on columns that already have a primary key | **Task 19D** |

---

## 9. Phased Implementation Roadmap (Tasks 19B – 19H)

```
[Task 19B] Cross-Platform Drivers & Dual-Engine Configuration
    |
[Task 19C] Model Hardening & PostgreSQL Schema Compatibility (Enums, Types, Lengths)
    |
[Task 19D] PostgreSQL Dual-Dialect Alembic Setup
    |
[Task 19E] Dialect-Aware DatabaseVerifier & PostgreSQL Backup Adapter
    |
[Task 19F] Non-Destructive Data Migration Script & Verification Tool
    |
[Task 19G] PostgreSQL Automated Testing Suite & Testcontainers Setup
    |
[Task 19H] Production Deployment & Multi-Worker Concurrency Benchmarking
```

### Task 19B: Dual-Engine Database Configuration & Cross-Platform Driver Setup
- **Objective:** Enable seamless dual-engine database connectivity for both SQLite and PostgreSQL.
- **Deliverables:** Updated `requirements.txt`, updated `backend/core/config.py`, updated `backend/database.py` with `QueuePool` + `pool_pre_ping`.
- **Exit Criteria:** Application connects to local or remote PostgreSQL when `DATABASE_URL=postgresql://...` is provided, while continuing to pass all 225 existing unit tests on SQLite.

### Task 19C: Model Hardening & PostgreSQL Schema Compatibility
- **Objective:** Fix Enum casing mismatches, add bounded string lengths, and standardize datetime timezone awareness across all 22 models.
- **Deliverables:** Patched `backend/models/events.py`, `backend/models/student.py`, etc.
- **Exit Criteria:** Models validate identically across SQLite and PostgreSQL dialects.

### Task 19D: PostgreSQL Dual-Dialect Alembic Setup
- **Objective:** Verify and adjust Alembic baseline to run cleanly against both SQLite and PostgreSQL.
- **Deliverables:** Verified `alembic/versions/0001_initial_baseline.py` and `alembic/env.py`.
- **Exit Criteria:** `alembic upgrade head` and `alembic downgrade base` succeed on empty SQLite and PostgreSQL databases.

### Task 19E: Dialect-Aware DatabaseVerifier & PostgreSQL Backup Adapter
- **Objective:** Adapt `DatabaseVerifier` to inspect PostgreSQL catalogs and create a production backup utility using `pg_dump`.
- **Deliverables:** Updated `backend/core/database_verifier.py`, `backend/core/backup_utils.py`.
- **Exit Criteria:** `DatabaseVerifier.verify_database()` returns `MIGRATED` on a correctly migrated PostgreSQL database.

### Task 19F: Non-Destructive Data Migration Script & Verification Tool
- **Objective:** Execute streamed transfer from `campus_automation.db` to PostgreSQL following the 3-Tier DAG with sequence resynchronization.
- **Deliverables:** `scripts/migrate_sqlite_to_postgres.py`, `scripts/verify_migration.py`.
- **Exit Criteria:** All 22 tables transferred, row counts and PKs match 100%, sequences synced, zero records lost.

### Task 19G: PostgreSQL Automated Testing Suite & Testcontainers Setup
- **Objective:** Configure CI and local test pipelines to run the full test suite against PostgreSQL using Docker or Testcontainers.
- **Deliverables:** `tests/test_postgres_compatibility.py`, GitHub Actions workflow update.
- **Exit Criteria:** All 225 backend unit and integration tests pass on PostgreSQL.

### Task 19H: Production Deployment & Multi-Worker Concurrency Benchmarking
- **Objective:** Validate multi-worker performance under simulated high-concurrency loads (QR attendance storm).
- **Deliverables:** Locust / k6 concurrency benchmark scripts, performance benchmark report.
- **Exit Criteria:** Zero `database is locked` or timeout errors under 4 Uvicorn workers and 500 concurrent requests.

---

## 10. Verification of Current State

Prior to task closeout, the application state was verified against strict safety rules:
1. **Actual Database Integrity:**
   - **Path:** [`campus_automation.db`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/campus_automation.db)
   - **Size:** 290,816 bytes (identical to pre-audit baseline).
   - **SHA-256 Checksum:** `baca55ebd284e474ef79c45d01f1b311c7c8e4f9a779bcb99a596a46798ce227` (identical to pre-audit baseline).
   - **Table Count:** 22 domain tables.
   - **Alembic Version:** Unstamped.
2. **Automated Test Results:**
   - **Backend Pytest Suite:** 225 passed in 59.81s (100% pass rate).
   - **Frontend Node Test Suite:** 20 passed in 226ms (100% pass rate).
3. **Repository State:**
   - No application source code was modified.
   - No database schemas were altered.
