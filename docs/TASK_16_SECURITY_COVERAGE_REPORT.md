# TASK 16 & 16B — SECURITY COVERAGE VERIFICATION AND AUDIT RECONCILIATION REPORT

**Repository**: `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`  
**Branch**: `main`  
**Target Remote**: `https://github.com/sanidhyasharma508-afk/SP0511---MAJOR-PROJECT-.git`  
**Parent Remote**: `https://github.com/ruetkhandelwal29-collab/campus_automation_system.git`  
**Date**: October 31, 2026  
**Auditor**: Antigravity Security Audit & Verification Specialist  

---

## 1. Initial Git State & Progression

At the start of Task 16B:
- **Repository Root**: `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System\MARVEL-main`
- **Initial Commit**: `bcd76fc079a3e0a69ed26d73a56b3eaf2296f35a` (`test(security): expand endpoint authorization and token lifecycle coverage`)
- **Parent Repository**: `C:\Users\ruetk\OneDrive\Desktop\Campus-Automation-System` at commit `46668ea` referencing submodule commit `bcd76fc`.
- **Branch**: `main` (synchronized with `origin/main`)
- **Working Tree**: Clean (untracked changes verified and preserved).

All security-related fixes from Task 15 were confirmed in active use:
- [`backend/routes/agents.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/routes/agents.py)
- [`backend/routes/auth.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/routes/auth.py)
- [`backend/schemas/agent.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/schemas/agent.py)
- [`backend/core/auth.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/core/auth.py)
- [`frontend/config.js`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/frontend/config.js)
- [`tests/test_comprehensive_security_audit.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/tests/test_comprehensive_security_audit.py)
- [`frontend/test/frontend_security.test.js`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/frontend/test/frontend_security.test.js)

---

## 2. Registered Endpoint Inventory & Count Reconciliation

A runtime reflection query on `backend.main.app.routes` confirms exactly **178 registered HTTP endpoints** across all backend routers.

### Reconciliation of Discrepancy (178 vs. 158)
The initial Task 16 summary table listed 158 routes due to the following specific factors:
1. **`dashboard.py` (+6 endpoints)**: The dashboard router was omitted entirely from the earlier breakdown table.
2. **`study_task.py` (+10 endpoints)**: Handlers in `study_task.py` are mounted across 3 router prefixes for backwards compatibility (`/api/v1/study-tasks`, `/v1/study-tasks`, `/study-tasks`), producing 24 route registrations rather than 14.
3. **`risk.py` (+3 endpoints)**: Contains 3 distinct APIRouters (`/risk-logs`, `/risk`, `/academic-risk`), totaling 13 route registrations rather than 10.
4. **`auth.py` (+2 endpoints)**: Contains dual routes/aliases (`/api/v1/auth/me` and `/api/v1/auth/admin/create-user`), totaling 10 registrations rather than 8.
5. **`events.py` (-1 endpoint)**: Contains 23 distinct endpoints rather than 24.

**Net reconciliation**: $158 + 6 + 10 + 3 + 2 - 1 = 178$ endpoints.

Across the application, these 178 registered routes map to **159 unique endpoint handler functions** (due to multi-prefix compatibility mountings).

### Complete Module Breakdown

| Router / Module | Prefix | Route Count | Primary Authorization Mechanism |
| :--- | :--- | :---: | :--- |
| `health.py` | `/health` | 1 | Public health check |
| `backend.main` | `/`, `/health/full` | 2 | Root redirects & detailed health check |
| `fastapi.applications` | `/docs`, `/redoc`, `/openapi.json` | 4 | Public interactive API documentation |
| `auth.py` | `/api/v1/auth` | 10 | Public entrypoints (login/register/refresh), Token revocation (logout), Protected user profile |
| `students.py` | `/students` | 5 | Faculty/Staff management, Student self-ownership for read/update, Admin deletion |
| `attendance.py` | `/attendance` | 7 | Faculty creation/modification, Student self-ownership for history/summary, Admin deletion |
| `complaint.py` | `/complaints` | 7 | Student self-ownership for creation/history/view, Staff status updates, Admin deletion |
| `schedule.py` | `/schedules` | 7 | Staff/Admin authoring/deletion, Public/Role-filtered institutional viewing |
| `schedule_feedback.py` | `/schedule-management` | 10 | Student self-ownership for feedback, Faculty announcement authoring & stats |
| `events.py` | `/events` | 23 | Faculty event authoring & management, Student registration self-ownership, Public schedules |
| `qr_attendance.py` | `/qr-attendance` | 11 | Faculty dynamic QR generation & monitoring, Student anti-impersonation scanning |
| `risk.py` | `/risk`, `/academic-risk`, `/risk-logs` | 13 | Student self-isolation (`/my-risk`), Scoped faculty evaluation, Staff risk logging |
| `dashboard.py` | `/dashboard` | 6 | Student self-view (`/student/me`), Department-scoped faculty oversight |
| `agents.py` | `/agents` | 3 | Public discovery (`GET /`), Role-restricted task execution (`POST /execute`) |
| `analytics.py` | `/analytics` | 7 | Faculty heatmaps & trends, Staff anomaly triggers, Student-isolated trend views |
| `clubs.py` | `/clubs` | 25 | Club leader/Faculty authoring, Student self-ownership on memberships |
| `ai.py` | `/ai` | 13 | Student self-isolated explanations, Faculty pattern intelligence, Knowledge base queries |
| `study_task.py` | `/api/v1/study-tasks`, `/v1/study-tasks`, `/study-tasks` | 24 | Strict user ownership isolation (`user_id == current_user.user_id`) |
| **Total Registered Endpoints** | | **178** | |

---

## 3. Authorization Coverage Matrix & Untested Inventory

The complete 178-endpoint authorization matrix is documented in [`docs/AUTHORIZATION_MATRIX.md`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/docs/AUTHORIZATION_MATRIX.md).

### Summary by Classification
- **Public by design**: 38 endpoints (OpenAPI documentation, health checks, login/register auth entrypoints, public event summaries, schedule catalogs).
- **Authenticated user**: 25 endpoints (General knowledge base queries, personal feedback, dashboard summary).
- **Student self-owned**: 44 endpoints (Enforcing student self-ownership via `linked_student_id`, `Student.roll_no`, or `task.user_id == current_user.user_id`).
- **Faculty-authorized**: 56 endpoints (Requiring `require_faculty` or `require_staff` with department/section academic scope checks).
- **Administrator-only**: 15 endpoints (User creation, student/record deletions, administrative overrides).

### Tested vs. Untested Inventory
- **Tested in Automated Regression Suites**: **106 endpoints** (60% direct automated test assertion coverage).
- **Untested via Automated Tests (Verified Clean via Manual Source Code Audit)**: **72 endpoints** (40%).

#### Untested Endpoints Prioritized by Risk:
1. **Medium-Risk (Administrative / Modifying Endpoints - Verified via Source Inspection)**:
   - `PATCH /events/leaderboard/{entry_id}` (requires `require_faculty`)
   - `DELETE /events/leaderboard/{entry_id}` (requires `require_faculty`)
   - `PATCH /events/announcements/{announcement_id}` (requires `require_faculty`)
   - `DELETE /events/announcements/{announcement_id}` (requires `require_faculty`)
   - `PATCH /schedule-management/announcements/{announcement_id}` (requires `require_faculty`)
   - `DELETE /schedule-management/announcements/{announcement_id}` (requires `require_staff`)
   - `PUT /risk-logs/{risk_id}` (requires `require_faculty`)
   - `DELETE /risk-logs/{risk_id}` (requires `require_admin`)
   - `PUT /clubs/{club_id}/activities/{activity_id}` (checks club organizer permission)
   - `DELETE /clubs/{club_id}/activities/{activity_id}` (checks club organizer permission)
2. **Low-Risk (Read-Only / Scoped Aggregations - Verified via Source Inspection)**:
   - `GET /schedule-management/feedback/stats/summary` (requires `require_faculty`)
   - `GET /events/{event_id}/stats` (public high-level counts)
   - `GET /events/stats/overview` (public aggregate counts)
   - `GET /ai/insights/attendance-patterns` (requires `require_faculty`)
   - `GET /ai/insights/complaint-patterns` (requires `require_faculty`)
   - `GET /ai/insights/intervention-strategies/{risk_type}` (requires `require_faculty`)
   - `GET /ai/why-complaints-increased` (requires `require_faculty`)
   - `GET /qr-attendance/faculty/absent-list/{session_id}` (requires `require_faculty`)
3. **No-Risk (Public Information / OpenAPI Documentation)**:
   - `GET /docs`, `GET /redoc`, `GET /openapi.json`, `GET /docs/oauth2-redirect`
   - `GET /events/upcoming`, `GET /events/announcements`
   - `GET /clubs/dashboard/all-clubs-summary`, `GET /clubs/dashboard/upcoming-events`

---

## 4. Refresh Token and Logout Security

All 11 verification points were inspected and tested:
1. **Distinct Token Types**: Access tokens (`type: "access"`) and refresh tokens (`type: "refresh"`) are strictly separated.
2. **Refresh Tokens Rejected as Access Tokens**: Passing a refresh token to protected routes returns `401 Unauthorized` ("Invalid token type").
3. **Access Tokens Rejected as Refresh Tokens**: Passing an access token to `/api/v1/auth/refresh` returns `401 Unauthorized` ("Invalid refresh token").
4. **User Binding**: Refresh tokens decode `user_id` and query the persistent database user record.
5. **Expiration Handling**: Expired refresh tokens raise `ExpiredSignatureError` and return `401`.
6. **Revocation Enforcement**: `refresh` verifies `is_token_blacklisted(request.refresh_token)`; revoked refresh tokens return `401` ("Token has been revoked").
7. **Dual Revocation on Logout**: Logging out revokes both the access token and the refresh token.
8. **Anti-Revocation Manipulation (Remediated in Task 16)**:
   - *Vulnerability Identified*: `logout` previously accepted a `refresh_token` string without checking if it belonged to the authenticated caller. An attacker could submit another user's refresh token and revoke their session. Furthermore, the access token was blacklisted before validating the refresh token.
   - *Fix Implemented*: Re-ordered validation in [`backend/routes/auth.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/routes/auth.py#L432-L465) to decode and verify ownership of both `token` and `refresh_token` before blacklisting either. Mismatched ownership triggers `403 Forbidden` ("Cannot revoke token belonging to another user"), leaving existing tokens intact.
9. **Repeated Logout Safety**: Repeated logout calls with already-revoked tokens fail safely with `401 Unauthorized`.
10. **Concurrent Refresh Consistency**: The frontend API client memoizes active in-flight refresh requests (`_refreshPromise`), ensuring concurrent `401` triggers share exactly one network call without race conditions.
11. **Persistence Limitation Identified**:
   - The token blacklist (`_token_blacklist` in [`backend/core/auth.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/core/auth.py#L224)) is stored in an in-memory Python `set()`.
   - *Operational Limitation*: Across backend service restarts or across multi-worker process boundaries without a shared store (e.g., Redis), in-memory blacklists do not persist. Revoked tokens whose TTL has not yet elapsed could be accepted if the process restarts before token expiry (30 minutes). Documented as an architectural consideration for distributed production deployments.

---

## 5. Agent Execution Authorization

The agent subsystem in [`backend/routes/agents.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/backend/routes/agents.py) was audited and hardened:
- **Anonymous Execution**: Strictly blocked (`POST /agents/execute` requires `TokenData = Depends(get_current_user)`).
- **Role-Based Agent Execution Matrix**:
  - `admission`: Restricted to `admin` and `staff`. Students attempting execution receive `403 Forbidden`.
  - `grades`: Restricted to `faculty`, `staff`, and `admin`. Students attempting execution receive `403 Forbidden`.
  - `attendance`: Permitted for students (self-tracking) and faculty/staff/admin.
  - `registration`: Permitted for all authenticated campus roles.
- **Anti-Impersonation in Agent Parameters**: If a student supplies `student_id` or `user_id` inside `request.parameters`, it is validated against the caller's authenticated identity (`current_user.user_id`, `current_user.linked_student_id`, `current_user.sub`). Mismatched parameters trigger `403 Forbidden` ("Cannot execute agent with another student's identifier").
- **Error Sanitization**: Catch-all exceptions log internal stack traces privately to application logs and return a generic sanitized error message (`"Agent execution encountered an error"`).

---

## 6. QR Attendance Lifecycle Guarantees

A complete API lifecycle test in [`tests/test_comprehensive_security_audit.py`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/tests/test_comprehensive_security_audit.py) verified:
1. **Creation Authorization**: Only `require_faculty` can call `/qr-attendance/faculty/generate-qr`. Students attempting generation receive `403 Forbidden`.
2. **Cryptographic Binding**: QR tokens incorporate unique UUIDs, random 16-byte hex secrets, and SHA-256 hashes verified with `secrets.compare_digest`.
3. **Bypass Rejection**: Placeholder hashes (`hash_placeholder`, `manual_entry`, `demo_scan`) are unconditionally rejected.
4. **Geofencing**: Haversine distance checks reject scans submitted outside the classroom radius (`is_within_geofence: false`).
5. **Anti-Impersonation**: Student identity is derived exclusively from the authenticated database user/student record. Attempts to pass another student's roll number or student ID fail with `403 Forbidden`.
6. **Duplicate Prevention**: Both pre-query checks and database unique constraints (`QRAttendanceRecord.session_id` + `QRAttendanceRecord.student_id`) catch duplicate scans and rollback via `try...except IntegrityError`.

---

## 7. Frontend XSS and Token Handling Verification

Node.js test suite [`frontend/test/frontend_security.test.js`](file:///C:/Users/ruetk/OneDrive/Desktop/Campus-Automation-System/MARVEL-main/frontend/test/frontend_security.test.js) passed with **20/20 test assertions**:
- **DOM XSS Sanitization**: `DOMUtils.escapeHtml` escapes `<`, `>`, `&`, `"`, and `'`. Unsafe URL schemes (`javascript:`, `data:`, `vbscript:`) are neutralized by `isSafeUrl` and `sanitizeUrl`.
- **AST Sink Inspection**: Verified that innerHTML string concatenation of unescaped API data has been completely replaced with safe `textContent` and `document.createTextNode` across `dashboard-analytics.js`, `schedule-management.js`, `qr-attendance.js`, `club-attendance.js`, and `clubs-pages.js`.
- **Failed Refresh Cleanup**: When `/auth/refresh` fails with a 401, all stored access tokens, refresh tokens, and expiry timestamps are purged from `localStorage` and `sessionStorage`.
- **403 Non-Logout**: A `403 Forbidden` error thrown by a restricted endpoint does NOT clear tokens or log out the user.
- **Log Hygiene**: Access and refresh tokens are excluded from error messages, URLs, and browser console output.

---

## 8. Full Test Execution Results

### 1. Backend Pytest Suite
Command: `python -m pytest tests/ -q`
- **Total Tests**: **188**
- **Passed**: **188** (100%)
- **Failed**: 0
- **Skipped**: 0
- **Errors**: 0
- **Warnings**: 0
- **Execution Time**: 26.06s

### 2. Frontend Node.js Suite
Command: `cd frontend && npm test`
- **Total Tests**: **20**
- **Passed**: **20** (100%)
- **Failed**: 0
- **Execution Time**: 211ms

---

## 9. Documented Architectural Limitations

1. **In-Memory Token Blacklist**:
   - `_token_blacklist` is an in-memory set. Token revocations do not persist across server reboots. For multi-node or persistent production deployments, a Redis or SQLite revocation store should be integrated.
2. **Headless Browser Execution**:
   - Frontend tests are executed in Node.js with DOM unit mocks and AST source pattern verifications. While all rendering sinks were audited and tested, live end-to-end browser rendering tests (e.g. Playwright) were not executed in this environment.
