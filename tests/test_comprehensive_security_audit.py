"""
Comprehensive Application Security Audit & Regression Test Suite
Phase 9 of TASK 15

Verifies:
1. Unauthenticated agent task execution rejection (POST /agents/execute -> 401).
2. Authenticated agent task execution success (POST /agents/execute -> 200).
3. Both access and refresh tokens blacklisted on logout; refresh token cannot be reused.
4. Deactivated user immediate rejection on protected endpoints.
5. Student cross-resource IDOR protection (students, attendance, complaints, risk, clubs).
6. Student privilege escalation prevention in profile update.
7. Role-based access control blocking students from faculty/staff/admin endpoints.
"""

import pytest
from backend.core.auth import create_access_token, create_refresh_token
from backend.models.user import User
from backend.models.student import Student
from backend.models.complaint import Complaint
from backend.models.attendance import Attendance
from backend.database import get_db
from datetime import datetime


@pytest.mark.asyncio
async def test_agents_execute_requires_auth(test_client, student_headers):
    """
    VULNERABILITY REPRODUCTION & REMEDIATION VERIFICATION:
    Unauthenticated request to POST /agents/execute must be rejected with 401 Unauthorized.
    Authenticated request must be accepted.
    """
    payload = {
        "agent_name": "attendance",
        "task": "analyze attendance trends",
        "parameters": {},
    }

    # 1. Unauthenticated request -> must return 401 Unauthorized
    unauth_resp = await test_client.post("/agents/execute", json=payload)
    assert unauth_resp.status_code == 401
    assert "not authenticated" in unauth_resp.json().get("detail", "").lower()

    # 2. Authenticated request -> must succeed with 200 OK
    auth_resp = await test_client.post("/agents/execute", json=payload, headers=student_headers)
    assert auth_resp.status_code == 200
    data = auth_resp.json()
    assert data["status"] == "success"
    assert data["agent_name"] == "attendance"
    assert data["result"]["processed"] is True


@pytest.mark.asyncio
async def test_agents_execute_invalid_agent(test_client, student_headers):
    """Authenticated request with unknown agent name returns 404."""
    payload = {
        "agent_name": "nonexistent_agent",
        "task": "run test",
        "parameters": {},
    }
    resp = await test_client.post("/agents/execute", json=payload, headers=student_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_logout_revokes_both_access_and_refresh_tokens(test_client):
    """
    VERIFICATION:
    Logout blacklists both access token and refresh token.
    Revoked refresh token cannot be used to refresh tokens.
    """
    login_resp = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "student1", "password": "student123"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # Verify access works initially
    prof_resp = await test_client.get("/api/v1/auth/profile", headers=auth_headers)
    assert prof_resp.status_code == 200

    # Logout with both access and refresh tokens
    logout_resp = await test_client.post(
        "/api/v1/auth/logout",
        headers=auth_headers,
        json={"token": access_token, "refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200

    # 1. Access token is blacklisted
    blocked_access = await test_client.get("/api/v1/auth/profile", headers=auth_headers)
    assert blocked_access.status_code == 401
    assert "revoked" in blocked_access.json().get("detail", "").lower()

    # 2. Refresh token is blacklisted
    blocked_refresh = await test_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert blocked_refresh.status_code == 401
    assert "revoked" in blocked_refresh.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_deactivated_account_denied_access(test_client, student_headers):
    """
    VERIFICATION:
    Deactivated account (is_active=False) is denied access immediately.
    """
    # Deactivate student1 in DB
    override_fn = test_client._transport.app.dependency_overrides.get(get_db)
    if override_fn:
        db = next(override_fn())
        try:
            student_user = db.query(User).filter(User.username == "student1").first()
            if student_user:
                student_user.is_active = False
                db.commit()
        finally:
            db.close()

    resp = await test_client.get("/api/v1/auth/profile", headers=student_headers)
    assert resp.status_code == 401
    assert "inactive" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_cross_student_idor_protections(test_client, student_headers):
    """
    VERIFICATION:
    Students cannot read another student's profile, attendance, complaints, or risk data.
    """
    # Create student 2 in the database
    override_fn = test_client._transport.app.dependency_overrides.get(get_db)
    if override_fn:
        db = next(override_fn())
        try:
            s2 = Student(
                name="Student Two",
                roll_no="2024CS002",
                department="Computer Science",
                semester=4,
                section="A",
            )
            db.add(s2)
            db.commit()
            db.refresh(s2)
            s2_id = s2.id
        finally:
            db.close()

    # 1. Student1 cannot view Student2's record
    resp_student = await test_client.get(f"/students/{s2_id}", headers=student_headers)
    assert resp_student.status_code == 403

    # 2. Student1 cannot view Student2's attendance
    resp_att = await test_client.get(f"/attendance/student/{s2_id}", headers=student_headers)
    assert resp_att.status_code == 403

    # 3. Student1 cannot view Student2's complaints
    resp_comp = await test_client.get(f"/complaints/student/{s2_id}", headers=student_headers)
    assert resp_comp.status_code == 403

    # 4. Student1 cannot view Student2's academic risk
    resp_risk = await test_client.get(f"/risk/student/{s2_id}", headers=student_headers)
    assert resp_risk.status_code == 403

    # 5. Student1 cannot view Student2's club memberships
    resp_clubs = await test_client.get(f"/clubs/memberships/student/{s2_id}", headers=student_headers)
    assert resp_clubs.status_code == 403


@pytest.mark.asyncio
async def test_privilege_escalation_in_profile_update(test_client, student_headers):
    """
    VERIFICATION:
    Students cannot escalate privilege by setting role='admin' in profile update.
    """
    resp = await test_client.put(
        "/api/v1/auth/profile",
        headers=student_headers,
        json={"role": "admin"},
    )
    assert resp.status_code == 403
    assert "role" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_student_blocked_from_privileged_endpoints(test_client, student_headers):
    """
    VERIFICATION:
    Students are blocked with 403 Forbidden from accessing faculty/staff/admin endpoints.
    """
    # 1. Faculty risk overview
    r1 = await test_client.get("/dashboard/risks/students", headers=student_headers)
    assert r1.status_code == 403

    # 2. Low attendance institutional overview
    r2 = await test_client.get("/dashboard/attendance/low-attendance", headers=student_headers)
    assert r2.status_code == 403

    # 3. Analytics complaint heatmap
    r3 = await test_client.get("/analytics/complaint-heatmap", headers=student_headers)
    assert r3.status_code == 403

    # 4. Trigger anomaly detection (staff only)
    r4 = await test_client.post("/analytics/detect-anomalies", headers=student_headers)
    assert r4.status_code == 403

    # 5. Create institutional schedule (staff only)
    r5 = await test_client.post(
        "/schedules/",
        headers=student_headers,
        json={
            "title": "Unauthorized Exam",
            "event_type": "Exam",
            "start_date": "2026-11-01T10:00:00",
            "end_date": "2026-11-01T12:00:00",
        },
    )
    assert r5.status_code == 403


@pytest.mark.asyncio
async def test_logout_manipulation_cannot_revoke_other_user_tokens(test_client):
    """
    VERIFICATION (Phase 3 Item 8):
    A refresh token or access token belonging to another user cannot be revoked
    through a manipulated logout request.
    """
    # 1. Login user A (student1)
    res_a = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "student1", "password": "student123"},
    )
    assert res_a.status_code == 200
    toks_a = res_a.json()
    headers_a = {"Authorization": f"Bearer {toks_a['access_token']}"}

    # 2. Login user B (staff1)
    res_b = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "staff1", "password": "staff123"},
    )
    assert res_b.status_code == 200
    toks_b = res_b.json()
    headers_b = {"Authorization": f"Bearer {toks_b['access_token']}"}

    # 3. User A attempts to revoke User B's refresh token via manipulated logout
    manipulated_logout = await test_client.post(
        "/api/v1/auth/logout",
        headers=headers_a,
        json={"refresh_token": toks_b["refresh_token"]},
    )
    assert manipulated_logout.status_code == 403
    assert "another user" in manipulated_logout.json().get("detail", "").lower()

    # 4. User A attempts to revoke User B's access token via manipulated logout
    manipulated_logout_acc = await test_client.post(
        "/api/v1/auth/logout",
        headers=headers_a,
        json={"token": toks_b["access_token"]},
    )
    assert manipulated_logout_acc.status_code == 403
    assert "another user" in manipulated_logout_acc.json().get("detail", "").lower()

    # 5. Verify User B's tokens remain completely valid and usable
    b_profile = await test_client.get("/api/v1/auth/profile", headers=headers_b)
    assert b_profile.status_code == 200

    b_refreshed = await test_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": toks_b["refresh_token"]},
    )
    assert b_refreshed.status_code == 200
    assert "access_token" in b_refreshed.json()


@pytest.mark.asyncio
async def test_agent_execution_role_boundaries_and_anti_impersonation(test_client, student_headers, faculty_headers, admin_headers):
    """
    VERIFICATION (Phase 4):
    - Students cannot execute privileged agents ('admission', 'grades').
    - Faculty and Admin can execute appropriate privileged agents.
    - Students cannot impersonate other students via execution parameters.
    """
    # 1. Student blocked from executing 'grades' agent -> 403
    resp_student_grades = await test_client.post(
        "/agents/execute",
        headers=student_headers,
        json={"agent_name": "grades", "task": "modify course grades"},
    )
    assert resp_student_grades.status_code == 403
    assert "not authorized" in resp_student_grades.json().get("detail", "").lower()

    # 2. Student blocked from executing 'admission' agent -> 403
    resp_student_admin = await test_client.post(
        "/agents/execute",
        headers=student_headers,
        json={"agent_name": "admission", "task": "process applicant"},
    )
    assert resp_student_admin.status_code == 403
    assert "not authorized" in resp_student_admin.json().get("detail", "").lower()

    # 3. Faculty permitted to execute 'grades' agent -> 200
    resp_fac_grades = await test_client.post(
        "/agents/execute",
        headers=faculty_headers,
        json={"agent_name": "grades", "task": "calculate class averages"},
    )
    assert resp_fac_grades.status_code == 200
    assert resp_fac_grades.json()["status"] == "success"

    # 4. Admin permitted to execute 'admission' agent -> 200
    resp_adm = await test_client.post(
        "/agents/execute",
        headers=admin_headers,
        json={"agent_name": "admission", "task": "verify applicant rosters"},
    )
    assert resp_adm.status_code == 200
    assert resp_adm.json()["status"] == "success"

    # 5. Student cannot supply another student's ID in parameters -> 403
    resp_spoof = await test_client.post(
        "/agents/execute",
        headers=student_headers,
        json={
            "agent_name": "attendance",
            "task": "fetch report",
            "parameters": {"student_id": 9999},
        },
    )
    assert resp_spoof.status_code == 403
    assert "another student" in resp_spoof.json().get("detail", "").lower()

    # 6. Student can supply their own student ID in parameters -> 200
    resp_own = await test_client.post(
        "/agents/execute",
        headers=student_headers,
        json={
            "agent_name": "attendance",
            "task": "fetch report",
            "parameters": {"student_id": 1},
        },
    )
    assert resp_own.status_code == 200
    assert resp_own.json()["status"] == "success"


@pytest.mark.asyncio
async def test_qr_attendance_full_lifecycle_and_guarantees(test_client, faculty_headers, student_headers):
    """
    VERIFICATION (Phase 5):
    Complete QR attendance lifecycle:
    - Session generation by faculty.
    - Time-bound QR payload and cryptographic hash binding.
    - Student scan validation within geofence.
    - Duplicate attendance prevention.
    - Cross-student impersonation rejection.
    - Student cannot generate QR session.
    """
    now = datetime.utcnow()

    # 1. Student attempting to generate QR session is rejected (403)
    gen_payload = {
        "subject_code": "CS301",
        "subject_name": "Database Systems",
        "branch": "Computer Science",
        "semester": "5",
        "lecture_date": now.isoformat(),
        "lecture_start_time": now.isoformat(),
        "lecture_duration_minutes": 60,
        "center_latitude": 28.6139,
        "center_longitude": 77.2090,
        "geo_fence_radius_meters": 100.0,
        "qr_validity_minutes": 15,
        "require_device_verification": False,
    }
    student_attempt = await test_client.post(
        "/qr-attendance/faculty/generate-qr",
        headers=student_headers,
        json=gen_payload,
    )
    assert student_attempt.status_code == 403

    # 2. Faculty creates authentic QR session -> 201 Created
    fac_session = await test_client.post(
        "/qr-attendance/faculty/generate-qr",
        headers=faculty_headers,
        json=gen_payload,
    )
    assert fac_session.status_code == 201
    session_info = fac_session.json()
    session_id = session_info["session_id"]
    qr_hash = session_info["qr_code_hash"]

    # 3. Student scans with invalid/tampered hash -> rejected
    scan_tampered = {
        "session_id": session_id,
        "qr_code_hash": "tampered_fake_hash_1234567890",
        "location": {"latitude": 28.6139, "longitude": 77.2090, "accuracy": 5.0},
    }
    resp_tampered = await test_client.post(
        "/qr-attendance/student/scan-qr",
        headers=student_headers,
        json=scan_tampered,
    )
    assert resp_tampered.status_code == 200
    assert resp_tampered.json()["success"] is False
    assert resp_tampered.json()["attendance_marked"] is False

    # 4. Student scans with placeholder hash -> rejected
    scan_placeholder = {
        "session_id": session_id,
        "qr_code_hash": "hash_placeholder",
        "location": {"latitude": 28.6139, "longitude": 77.2090, "accuracy": 5.0},
    }
    resp_placeholder = await test_client.post(
        "/qr-attendance/student/scan-qr",
        headers=student_headers,
        json=scan_placeholder,
    )
    assert resp_placeholder.status_code == 200
    assert resp_placeholder.json()["success"] is False

    # 5. Student scans attempting to impersonate another student ID -> 403
    scan_spoof = {
        "session_id": session_id,
        "qr_code_hash": qr_hash,
        "student_id": "9999",
        "location": {"latitude": 28.6139, "longitude": 77.2090, "accuracy": 5.0},
    }
    resp_spoof = await test_client.post(
        "/qr-attendance/student/scan-qr",
        headers=student_headers,
        json=scan_spoof,
    )
    assert resp_spoof.status_code == 403
    assert "mismatch" in resp_spoof.json().get("detail", "").lower()

    # 6. Student scans outside geofence -> rejected
    scan_outside = {
        "session_id": session_id,
        "qr_code_hash": qr_hash,
        "location": {"latitude": 29.0000, "longitude": 78.0000, "accuracy": 5.0},
    }
    resp_outside = await test_client.post(
        "/qr-attendance/student/scan-qr",
        headers=student_headers,
        json=scan_outside,
    )
    assert resp_outside.status_code == 200
    assert resp_outside.json()["success"] is False
    assert resp_outside.json()["is_within_geofence"] is False

    # 7. Student scans authentically within geofence -> Success
    scan_valid = {
        "session_id": session_id,
        "qr_code_hash": qr_hash,
        "location": {"latitude": 28.6139, "longitude": 77.2090, "accuracy": 5.0},
    }
    resp_valid = await test_client.post(
        "/qr-attendance/student/scan-qr",
        headers=student_headers,
        json=scan_valid,
    )
    assert resp_valid.status_code == 200
    data_valid = resp_valid.json()
    assert data_valid["success"] is True
    assert data_valid["attendance_marked"] is True

    # 8. Duplicate scan for the same session -> rejected (duplicate prevented)
    resp_dup = await test_client.post(
        "/qr-attendance/student/scan-qr",
        headers=student_headers,
        json=scan_valid,
    )
    assert resp_dup.status_code == 200
    assert resp_dup.json()["success"] is False
    assert "already marked" in resp_dup.json()["message"].lower()
