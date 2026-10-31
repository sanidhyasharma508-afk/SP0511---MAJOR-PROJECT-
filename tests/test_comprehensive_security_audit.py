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
