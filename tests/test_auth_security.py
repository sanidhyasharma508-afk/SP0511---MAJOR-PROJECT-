"""
Comprehensive Authentication and Authorization Security Test Suite
Tests all 15 required security scenarios for persistent authentication,
database-level integrity, role-based access control (RBAC), and resource ownership.
"""

import pytest
from datetime import datetime, timedelta
import jwt

from backend.core.auth import create_access_token, SECRET_KEY, ALGORITHM
from backend.models.user import User
from backend.models.student import Student


@pytest.mark.asyncio
async def test_01_user_registration_student_success(test_client):
    """Scenario 1: User registration succeeds for role 'student'"""
    payload = {
        "username": "new_student",
        "email": "new_student@campus.edu",
        "password": "Password123!",
        "full_name": "New Student",
        "role": "student",
    }
    res = await test_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "new_student"
    assert data["email"] == "new_student@campus.edu"
    assert data["role"] == "student"
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_02_registration_rejects_privileged_roles(test_client):
    """Scenario 2: Public registration strictly rejects privileged roles (admin, staff, faculty) with 403"""
    for forbidden_role in ["admin", "staff", "faculty"]:
        payload = {
            "username": f"bad_{forbidden_role}",
            "email": f"bad_{forbidden_role}@campus.edu",
            "password": "Password123!",
            "full_name": f"Bad {forbidden_role}",
            "role": forbidden_role,
        }
        res = await test_client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 403
        assert "Public self-registration is only permitted for students" in res.json()["detail"]


@pytest.mark.asyncio
async def test_03_registration_rejects_duplicates(test_client):
    """Scenario 3: Registration rejects duplicate username and email with 400 Bad Request"""
    payload = {
        "username": "unique_user",
        "email": "unique@campus.edu",
        "password": "Password123!",
        "full_name": "Unique User",
        "role": "student",
    }
    first = await test_client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    # Duplicate username
    dup_user = await test_client.post(
        "/api/v1/auth/register",
        json={**payload, "email": "different_email@campus.edu"}
    )
    assert dup_user.status_code == 400
    assert "already exists" in dup_user.json()["detail"]

    # Duplicate email
    dup_email = await test_client.post(
        "/api/v1/auth/register",
        json={**payload, "username": "different_user"}
    )
    assert dup_email.status_code == 400
    assert "already registered" in dup_email.json()["detail"]


@pytest.mark.asyncio
async def test_04_account_persists_in_database(test_client):
    """Scenario 4: User account persists in database and is verifiable across requests"""
    payload = {
        "username": "persisted_user",
        "email": "persisted@campus.edu",
        "password": "Password123!",
        "full_name": "Persisted User",
        "role": "student",
    }
    reg = await test_client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    # Log in immediately to verify persistent state
    login_res = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "persisted_user", "password": "Password123!"}
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


@pytest.mark.asyncio
async def test_05_successful_login_returns_jwt(test_client):
    """Scenario 5: Login with valid credentials succeeds and returns valid JWT"""
    res = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "admin"
    assert "password" not in data


@pytest.mark.asyncio
async def test_06_login_invalid_password_returns_401(test_client):
    """Scenario 6: Login with incorrect password returns 401 Unauthorized"""
    res = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "WrongPassword999!"}
    )
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]


@pytest.mark.asyncio
async def test_07_token_decoding_and_identity_resolution(test_client):
    """Scenario 7: Token decoding resolves current user identity via /api/v1/auth/me"""
    login_res = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "student1", "password": "student123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await test_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "student1"
    assert me_data["role"] == "student"


@pytest.mark.asyncio
async def test_08_expired_and_malformed_token_rejected(test_client):
    """Scenario 8: Expired or malformed tokens are rejected with 401 Unauthorized"""
    # Malformed token
    res_malformed = await test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"}
    )
    assert res_malformed.status_code == 401

    # Expired token
    expired_payload = {
        "sub": "admin",
        "user_id": 1,
        "role": "admin",
        "type": "access",
        "exp": datetime.utcnow() - timedelta(minutes=10)
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
    res_expired = await test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert res_expired.status_code == 401


@pytest.mark.asyncio
async def test_09_revoked_token_rejected_after_logout(test_client):
    """Scenario 9: Revoked token after logout cannot be reused (returns 401)"""
    login_res = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "staff1", "password": "staff123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify working initially
    assert (await test_client.get("/api/v1/auth/me", headers=headers)).status_code == 200

    # Logout to revoke
    logout_res = await test_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Using revoked token must fail with 401
    me_after = await test_client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401
    assert "revoked" in me_after.json()["detail"].lower()


@pytest.mark.asyncio
async def test_10_inactive_user_rejected(test_client):
    """Scenario 10: Inactive user accounts (is_active=False) cannot access protected endpoints (401)"""
    # Create an inactive user token
    token = create_access_token(user_id=9999, username="inactive_user", role="student")
    headers = {"Authorization": f"Bearer {token}"}

    # User does not exist in DB -> 401
    res = await test_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_11_role_restrictions_student_forbidden_from_staff_routes(test_client, student_headers):
    """Scenario 11: Student role cannot access faculty/staff routes (403 Forbidden)"""
    # 1. Student cannot generate QR session
    qr_payload = {
        "faculty_id": "fac_1",
        "faculty_name": "Prof",
        "subject_code": "CS-101",
        "subject_name": "CS",
        "branch": "CS",
        "semester": 1,
        "section": "A",
        "lecture_date": datetime.utcnow().isoformat(),
        "lecture_start_time": datetime.utcnow().isoformat(),
        "lecture_duration_minutes": 60,
        "qr_validity_minutes": 15,
        "center_latitude": 26.2738,
        "center_longitude": 73.0366,
        "location_name": "Room 101"
    }
    res_qr = await test_client.post(
        "/qr-attendance/faculty/generate-qr",
        json=qr_payload,
        headers=student_headers
    )
    assert res_qr.status_code == 403

    # 2. Student cannot create a class schedule
    schedule_payload = {
        "title": "Unauthorized Class",
        "event_type": "Class",
        "start_date": datetime.utcnow().isoformat(),
        "end_date": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "audience": "CS Sem 4",
        "is_active": 1
    }
    res_schedule = await test_client.post(
        "/schedules/",
        json=schedule_payload,
        headers=student_headers
    )
    assert res_schedule.status_code == 403


@pytest.mark.asyncio
async def test_12_role_restrictions_staff_forbidden_from_admin_routes(test_client, staff_headers):
    """Scenario 12: Staff/Faculty cannot access admin-only delete operations (403 Forbidden)"""
    # Staff cannot delete a student
    del_student = await test_client.delete("/students/1", headers=staff_headers)
    assert del_student.status_code == 403

    # Staff cannot delete a schedule
    del_sched = await test_client.delete("/schedules/1", headers=staff_headers)
    assert del_sched.status_code == 403


@pytest.mark.asyncio
async def test_13_student_ownership_read_protection(test_client, student_headers, admin_headers):
    """Scenario 13: Student cannot read another student's detailed record (403 Forbidden)"""
    # First ensure a second student exists
    create_res = await test_client.post(
        "/students/",
        json={
            "name": "Second Student",
            "roll_no": "21BCS999",
            "department": "Computer Science",
            "semester": 4,
            "section": "B",
        },
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    second_student_id = create_res.json()["id"]

    # student1 (linked to student_id=1) attempts to view second_student_id -> 403 Forbidden
    res = await test_client.get(f"/students/{second_student_id}", headers=student_headers)
    assert res.status_code == 403
    assert "Students can only view their own private student record" in res.json()["detail"]


@pytest.mark.asyncio
async def test_14_student_ownership_update_protection(test_client, student_headers, admin_headers):
    """Scenario 14: Student cannot modify another student's record (403 Forbidden)"""
    # Create second student
    create_res = await test_client.post(
        "/students/",
        json={
            "name": "Target Student",
            "roll_no": "21BCS888",
            "department": "Computer Science",
            "semester": 4,
            "section": "A",
        },
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    target_student_id = create_res.json()["id"]

    # student1 attempts to update target_student_id -> 403 Forbidden
    update_payload = {
        "name": "Hacked Name",
        "roll_no": "21BCS888",
        "department": "Computer Science",
        "semester": 4,
        "section": "A",
    }
    res = await test_client.put(f"/students/{target_student_id}", json=update_payload, headers=student_headers)
    assert res.status_code == 403
    assert "Students cannot modify another student's record" in res.json()["detail"]


@pytest.mark.asyncio
async def test_15_qr_and_complaint_anti_impersonation(test_client, student_headers, faculty_headers):
    """Scenario 15: QR attendance and complaint submissions block identity impersonation (403 Forbidden)"""
    # 1. Generate a valid QR session first using faculty headers
    now = datetime.utcnow()
    qr_payload = {
        "faculty_id": "fac_test",
        "faculty_name": "Dr. Test",
        "subject_code": "CS-999",
        "subject_name": "Test Subject",
        "branch": "CS",
        "semester": 4,
        "section": "A",
        "lecture_date": now.isoformat(),
        "lecture_start_time": now.isoformat(),
        "lecture_duration_minutes": 60,
        "qr_validity_minutes": 15,
        "center_latitude": 26.2738,
        "center_longitude": 73.0366,
        "geo_fence_radius_meters": 100.0,
        "location_name": "Lab 1",
        "allow_screenshot_scan": True,
        "require_device_verification": False
    }
    gen_res = await test_client.post("/qr-attendance/faculty/generate-qr", json=qr_payload, headers=faculty_headers)
    assert gen_res.status_code == 201
    session_data = gen_res.json()

    # 2. Student attempts to scan and submit attendance claiming student_id=999 (impersonation)
    impersonate_scan = {
        "session_id": session_data["session_id"],
        "student_id": "999",
        "roll_number": "21BCS999",
        "student_name": "Victim Student",
        "student_email": "victim@campus.edu",
        "branch": "CS",
        "semester": "4",
        "section": "A",
        "qr_code_hash": session_data["qr_code_hash"],
        "location": {"latitude": 26.2738, "longitude": 73.0366, "accuracy": 10.0},
        "device": {"device_id": "device_fingerprint_test_1", "device_model": "Chrome", "device_os": "Windows", "browser": "Chrome"},
        "scan_timestamp": now.isoformat(),
        "scan_duration_ms": 1000
    }
    scan_res = await test_client.post("/qr-attendance/student/scan-qr", json=impersonate_scan, headers=student_headers)
    assert scan_res.status_code == 403
    assert "Cannot mark attendance for another student" in scan_res.json()["detail"]

    # 3. Student attempts to file a complaint for another student_id=999
    complaint_payload = {
        "student_id": 999,
        "title": "Impersonated Complaint",
        "description": "Filing fake complaint as another student",
        "category": "Academic",
        "priority": "High"
    }
    cmp_res = await test_client.post("/complaints/", json=complaint_payload, headers=student_headers)
    assert cmp_res.status_code == 403
    assert "Cannot file complaint on behalf of another student" in cmp_res.json()["detail"]
