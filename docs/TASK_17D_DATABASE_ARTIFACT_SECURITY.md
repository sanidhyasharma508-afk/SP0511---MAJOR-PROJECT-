# TASK 17D — SENSITIVE DATABASE ARTIFACT SECURITY AND REPOSITORY CONTAINMENT

**Project**: Campus Automation System (MARVEL)
**Repository**: `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`
**Branch**: `main`
**Main Remote**: `https://github.com/sanidhyasharma508-afk/SP0511---MAJOR-PROJECT-.git`
**Parent Remote**: `https://github.com/ruetkhandelwal29-collab/campus_automation_system.git`
**Audit Target**: Git-Tracked Legacy Database Artifacts & Credential Exposure Containment
**Date**: November 2, 2026

---

## 1. Affected Files and Locations

During the Task 17 database architecture audit, two legacy SQLite database files were identified as actively tracked in the Git repository tree.

| # | File Path in Repository | File Size | Git Tracking Status (Pre-Task) | Git Introduction Commit | Commit Date & Author |
|---|---|---|---|---|---|
| 1 | `SP0511---MAJOR-PROJECT--master/campusautomation_QR_attendence/database.db` | 20,480 bytes | **Tracked** | [`e16102f`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/) (*"Improved dashboard styling and layout"*) | Feb 17, 2026 by Sanidhya Sharma |
| 2 | `SP0511---MAJOR-PROJECT--master/test.db` | 221,184 bytes | **Tracked** | [`68bf88c`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/) (*"Initial project setup"*) | Feb 17, 2026 by Sanidhya Sharma |

In addition, two untracked local runtime database files were verified to exist on disk:
- `campus_automation.db` (290,816 bytes, root directory): active SQLite database initialized by `backend/seed_data.py`. Untracked and excluded by `.gitignore`.
- `test.db` (0 bytes, root directory): transient test placeholder, untracked and excluded by `.gitignore`.

---

## 2. Sensitive Data Categories Discovered

Direct binary and SQL inspection of both tracked files revealed that they are pre-alpha prototype and test databases containing confidential credentials and student personally identifiable information (PII).

### Category 1: Unhashed Plaintext Authentication Credentials
Discovered in `SP0511---MAJOR-PROJECT--master/campusautomation_QR_attendence/database.db` inside the legacy `users` table:
- **Table Name**: `users`
- **Columns**: `id` (INTEGER), `role` (TEXT), `username` (TEXT), `password` (TEXT)
- **Total Records**: 2 active user records
- **Data Exposed**: Plaintext passwords stored directly without hashing (e.g., bcrypt/Argon2/PBKDF2). The passwords are short numeric strings (`1***`).
- **Roles**: Faculty/Staff (`t*****r`) and Student (`s*****t`).

### Category 2: Student Personally Identifiable Information (PII)
Discovered in `SP0511---MAJOR-PROJECT--master/test.db` across the `students` table:
- **Table Name**: `students`
- **Columns**: `id` (INTEGER), `name` (TEXT), `roll_no` (TEXT), `department` (TEXT), `semester` (TEXT)
- **Total Records**: 1 active record
- **Data Exposed**: Full student name, academic roll number formatted to match Indian university standards, and department code.

### Category 3: Student Grievances & Schedule Feedback
Discovered in `SP0511---MAJOR-PROJECT--master/test.db` inside `schedule_feedback`:
- **Table Name**: `schedule_feedback`
- **Columns**: `id`, `name`, `roll_number`, `issue_type`, `preferred_timing`, `additional_comments`, `status`, `created_at`, `resolved_at`
- **Total Records**: 1 active record
- **Data Exposed**: Student personal name, roll number, specific complaints regarding timetable clashes, and submission timestamps.

### Category 4: Institutional Notices and Faculty Identification
Discovered in `SP0511---MAJOR-PROJECT--master/test.db` inside `announcements`:
- **Table Name**: `announcements`
- **Columns**: `id`, `title`, `content`, `author`, `priority`, `target_audience`, `is_active`, `created_at`, `expires_at`
- **Total Records**: 1 active record
- **Data Exposed**: Announcement title, body text regarding campus schedule modifications, and named faculty author (`D************a`).

---

## 3. Redacted Evidence

All evidence below is masked to protect credentials and personal identifiers.

### A. Evidence from `database.db` (`campusautomation_QR_attendence`)
```text
Table: users (row_count: 2)
  Columns: [('id', 'INTEGER'), ('role', 'TEXT'), ('username', 'TEXT'), ('password', 'TEXT')]
  Row 1 (Redacted): [1, 't*****r', 'T**1', '1**4']
  Row 2 (Redacted): [2, 's*****t', 'S**1', '1**4']

Table: sessions (row_count: 0)
  Columns: ['session_id', 'teacher_id', 'lat', 'lon', 'radius', 'expiry', 'active']

Table: attendance (row_count: 0)
  Columns: ['student_id', 'session_id', 'time']
```

### B. Evidence from `test.db` (`SP0511---MAJOR-PROJECT--master`)
```text
Table: students (row_count: 1)
  Columns: ['id', 'name', 'roll_no', 'department', 'semester']
  Row 1 (Redacted): [1, 'S******A', 'M****3', 'c*e', 5]

Table: schedule_feedback (row_count: 1)
  Columns: ['id', 'name', 'roll_number', 'issue_type', 'preferred_timing', 'additional_comments', 'status', 'created_at', 'resolved_at']
  Row 1 (Redacted): [1, 'R**********a', '2******1', 'C****************h', '2*****************************s', 'T*************************************************************************************************.', 'p*****g', '2*****************0', NULL]

Table: announcements (row_count: 1)
  Columns: ['id', 'title', 'content', 'author', 'priority', 'target_audience', 'is_active', 'created_at', 'expires_at']
  Row 1 (Redacted): [1, 'L*********************d', 'T******************************************************************************************************************************************************.', 'D************a', 'h**h', 'C*********r', 1, '2*****************0', '2************************5']
```

---

## 4. Credential and Data Risk Assessment

### 1. Do exposed credentials correspond to actual application accounts?
**NO.** Inspection of the active modern user database (`campus_automation.db`) and initialization code in [`backend/seed_data.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/seed_data.py#L163-L195) confirms:
- Modern accounts are provisioned with usernames: `admin`, `staff1`, `student1`, and `staff2`.
- The usernames `T101` and `S201` do **not** exist in the modern database.
- Modern authentication evaluates `hashed_password` using `passlib` with PBKDF2/bcrypt (`backend/core/auth.py`), whereas `database.db` uses an obsolete flat schema (`users.password`).

### 2. Could the exposed credentials still authenticate?
**NO** against the current codebase:
- In the active application, submitting `T101` or `S201` to `POST /auth/login` returns `401 Unauthorized` (`"Invalid username or password"`) because the accounts are absent from the database.
- However, if any external legacy prototype server or developer staging instance is still running the original script from `campusautomation_QR_attendence`, those instances would be immediately vulnerable to unauthorized access.

### 3. Do affected accounts have privileged roles?
**YES.**
- Account `T101` holds role `teacher`. In the QR attendance prototype, the teacher role permits creating attendance sessions, generating QR codes, and viewing attendance logs.
- Account `S201` holds role `student`.

### 4. Is the data production-like or synthetic?
- **Credentials (`database.db`)**: Clearly synthetic/mock developer test data (`1234` passwords, sequential IDs `T101`/`S201`).
- **Student Records (`test.db`)**: Contains realistic university identifiers (student names, roll numbers like `21BCS...`, department codes). While likely created during initial developer testing, they follow real-world student identity formats and constitute sensitive student PII.

### 5. Credential Rotation and Invalidation Action Plan
Even though the accounts do not exist in the active production schema, the following defense-in-depth measures are mandated:
1. **Explicit Ban in Seeding**: Ensure `backend/seed_data.py` never provisions `T101` or `S201`.
2. **Password Blacklist**: Add `1234`, `password`, and common weak credentials to password strength validation in [`backend/core/auth.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/core/auth.py).
3. **Environment Verification**: Confirm no staging or test server is running the standalone Flask script in `campusautomation_QR_attendence`.

---

## 5. Git History Exposure Assessment

### 1. Affected Commit Range & Blob Identifiers
Both database files are embedded directly in the repository Git object database:

```text
Blob SHA (database.db): 039631828f0da88bafa7d3856c6e9740575d3f93 (20,480 bytes)
  Introduced in commit: e16102f (Feb 17, 2026 - "Improved dashboard styling and layout")
  Present in all commits: e16102f..HEAD (33 sequential commits)

Blob SHA (test.db):     b806e3f7913e148941ff273db69b4560a1f71727 (221,184 bytes)
  Introduced in commit: 68bf88c (Feb 17, 2026 - "Initial project setup")
  Present in all commits: 68bf88c..HEAD (37 sequential commits)
```

Both blobs have remained byte-for-byte identical since their introduction.

### 2. Why Untracking at HEAD Is Insufficient for Complete Removal
Executing `git rm --cached` removes the files from HEAD and prevents them from appearing in future commits. However:
- Git is an immutable, append-only content-addressable store.
- Any clone of the repository retains the packfiles containing blobs `039631828f0...` and `b806e3f...`.
- Running `git checkout e16102f` or querying `git cat-file -p 039631828f0...` immediately recovers the original database files.
- Full erasure requires rewriting historical commits to purge the blobs from the Git tree.

### 3. Recommended History-Cleaning Procedure (Future Option)
If complete history purging is required:
1. Tool: Use `git-filter-repo` (recommended over legacy `git filter-branch` or BFG).
2. Command:
   ```bash
   git-filter-repo --path SP0511---MAJOR-PROJECT--master/campusautomation_QR_attendence/database.db                    --path SP0511---MAJOR-PROJECT--master/test.db                    --invert-paths
   ```
3. Remote Coordination:
   - Coordinated force-push (`git push origin --force --all`) to the upstream repository.
   - All team members must discard existing local clones and re-clone from scratch to avoid re-introducing the pruned commits.
   - The parent repository (`Campus-Automation-System`) must update its submodule commit reference.

### 4. Why History Rewriting Was NOT Executed in Task 17D
Per explicit user instructions and sound Git security governance:
- **Zero Force-Push Rule**: Shared remote history must never be rewritten without advance coordination with all collaborators.
- **Submodule Integrity**: Rewriting SHAs in `MARVEL-main` alters all 37 commit hashes, detaching the parent repository submodule pointer and invalidating earlier audit references.
- **Containment First**: Task 17D establishes full containment at HEAD, preventing future tracking, while documenting historical exposure for an authorized maintenance window.

---

## 6. Safe Repository Containment Actions Taken

### 1. Updated `.gitignore`
Enhanced `.gitignore` in `MARVEL-main` to comprehensively ignore all database binaries, SQLite journals, write-ahead logs, shared-memory files, and backup dumps:

```gitignore
# Databases created locally and SQLite artifacts
*.db
*.db-journal
*.db-wal
*.db-shm
*.sqlite
*.sqlite3
*.sqlite3-journal
*.sqlite3-wal
*.sqlite3-shm
*.rdb
*.dump
backups/
```

### 2. Removed Sensitive Database Files from Git Tracking (`git rm --cached`)
Executed non-destructive removal from the Git staging index:
```bash
git rm --cached "SP0511---MAJOR-PROJECT--master/campusautomation_QR_attendence/database.db"
git rm --cached "SP0511---MAJOR-PROJECT--master/test.db"
```
* **Local Preservation**: The physical database files on disk (`SP0511---MAJOR-PROJECT--master/...`) were preserved intact.
* **Tracking State**: Both files transitioned from tracked to ignored.
* **Clean Status**: Because `.gitignore` includes `*.db`, the files do not appear as untracked files in `git status`.

### 3. Verified Application Startup and Seeding
Executed `ensure_schema()` and `seed_database()` from [`backend/seed_data.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/seed_data.py):
- The modern SQLite database (`campus_automation.db`) initializes cleanly.
- No untracked files or database leaks are introduced.

---

## 7. Verification and Testing Results

| Test / Verification Item | Execution Command / Procedure | Result | Evidence / Details |
|---|---|---|---|
| **Git Tracking Verification** | `git ls-files "*.db"` | **PASS** | Returns 0 tracked database files. |
| **Local File Preservation** | `Test-Path <file>` | **PASS** | Both files remain physically present on disk. |
| **`.gitignore` Effectiveness** | `git status` | **PASS** | Neither file appears as untracked; working tree is clean. |
| **Automated Test Suite** | `python -m pytest -q` | **PASS** | **188 passed** in 20.45s; 0 regressions. |
| **Database Initialization** | `seed_database()` | **PASS** | Schema verified and accounts seeded without error. |
| **Non-Destructive Boundary** | `git diff --name-only` | **PASS** | Only `.gitignore`, `docs/TASK_17D_DATABASE_ARTIFACT_SECURITY.md`, and index deletions changed. |

---

## 8. Summary of Remaining Risks and Explicit Approval Requirements

1. **HEAD Containment**: **COMPLETE**. No database files are tracked in the current commit or future commits.
2. **Historical Exposure**: **OPEN IN GIT HISTORY (COMMITS `68bf88c` through `dce6b0a`)**.
3. **Approval Status for History Rewriting**:
   - History rewriting requires explicit user authorization before running `git-filter-repo` and force-pushing.
   - Until authorized, the historical exposure is managed by ensuring credentials are inactive and untracked at HEAD.
