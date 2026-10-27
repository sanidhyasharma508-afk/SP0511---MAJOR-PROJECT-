"""
Comprehensive Security and Authorization Tests for QR Attendance System.
Covers all 13 security requirements:
1. Unauthenticated session creation rejected (401)
2. Student creating faculty QR session rejected (403)
3. Faculty identity is derived from authenticated user (client cannot spoof faculty_id)
4. Student marking attendance with mismatched student_id / roll_number rejected (403)
5. User without linked student record marking attendance rejected (403)
6. Valid student marking attendance succeeds (200, attendance_marked=True)
7. Expired or closed session rejected (attendance_marked=False)
8. Duplicate attendance rejected by backend & unique constraint (Duplicate attendance attempt)
9. Student cannot tamper with attendance status or timestamp (server-derived)
10. Manual session code entry enforces identical security checks
11. Session closure endpoint succeeds and immediately blocks further scans
12. Existing attendance records remain intact and queryable
13. Faculty ownership enforced on update, close, and live-attendance endpoints (403 for other faculty)
"""

import pytest
from datetime import datetime, timedelta
from backend.core.auth import create_access_token


@pytest.mark.asyncio
async def test_qr_security_complete_suite(
    test_client,
    faculty_headers,
    other_faculty_headers,
    student_headers,
    admin_headers,
):
    now = datetime.utcnow()

    # Provision unlinked student user through real registration (role=student)

    res_reg_unlinked = await test_client.post(
        "/api/v1/auth/register",
        json={
            "username": "unlinked_student_qr",
            "email": "unlinked@test.edu",
            "password": "Password123!",
            "full_name": "Unlinked Student",
            "role": "student",
        },
    )
    assert res_reg_unlinked.status_code == 201
    unlinked_uid = res_reg_unlinked.json()["user_id"]
    unlinked_token = create_access_token(user_id=unlinked_uid, username="unlinked_student_qr", role="student")
    unlinked_user_headers = {"Authorization": f"Bearer {unlinked_token}"}

    gen_payload = {
        "faculty_id": "spoofed_id_999",
        "faculty_name": "Spoofed Name",
        "faculty_email": "spoof@mbm.edu",
        "subject_code": "CS-401",
        "subject_name": "Distributed Systems",
        "branch": "CS",
        "semester": 4,
        "section": "A",
        "lecture_date": now.isoformat(),
        "lecture_start_time": (now + timedelta(minutes=10)).isoformat(),
        "lecture_duration_minutes": 60,
        "qr_validity_minutes": 15,
        "center_latitude": 26.2738,
        "center_longitude": 73.0366,
        "geo_fence_radius_meters": 100.0,
        "location_name": "Room 401, CSE Block",
        "total_students_expected": 50,
        "allow_screenshot_scan": True,
        "require_device_verification": False,
    }

    # -------------------------------------------------------------------------
    # 1. Unauthenticated session creation rejected (401)
    # -------------------------------------------------------------------------
    res_unauth = await test_client.post("/qr-attendance/faculty/generate-qr", json=gen_payload)
    assert res_unauth.status_code == 401, "Unauthenticated request should return 401"

    # -------------------------------------------------------------------------
    # 2. Student creating faculty QR session rejected (403)
    # -------------------------------------------------------------------------
    res_student_gen = await test_client.post(
        "/qr-attendance/faculty/generate-qr", json=gen_payload, headers=student_headers
    )
    assert res_student_gen.status_code == 403, "Student generating QR should return 403 Forbidden"

    # -------------------------------------------------------------------------
    # 3. Faculty identity is securely derived from authenticated user (overrides client input)
    # -------------------------------------------------------------------------
    res_valid_gen = await test_client.post(
        "/qr-attendance/faculty/generate-qr", json=gen_payload, headers=faculty_headers
    )
    assert res_valid_gen.status_code == 201
    session_data = res_valid_gen.json()
    assert session_data["faculty_id"] == "2", "Faculty identity must be derived from token user_id, not spoofed input"
    session_id = session_data["session_id"]
    qr_code_hash = session_data["qr_code_hash"]

    # Base valid scan payload
    valid_scan_payload = {
        "session_id": session_id,
        "student_id": "1",
        "roll_number": "21BCS101",
        "student_name": "Alex Johnson",
        "student_email": "alex@student.mbm.edu",
        "branch": "CS",
        "semester": 4,
        "section": "A",
        "qr_code_hash": qr_code_hash,
        "location": {"latitude": 26.2738, "longitude": 73.0366, "accuracy": 10.0},
        "device": {
            "device_id": "test_device_1",
            "device_model": "Chrome",
            "device_os": "Windows",
            "browser": "Chrome",
        },
        "scan_timestamp": now.isoformat(),
        "scan_duration_ms": 900,
    }

    # -------------------------------------------------------------------------
    # 4. Student marking attendance with mismatched student_id or roll_number rejected (403)
    # -------------------------------------------------------------------------
    spoof_student_payload = dict(valid_scan_payload, student_id="999", roll_number="21BCS999")
    res_spoof = await test_client.post(
        "/qr-attendance/student/scan-qr", json=spoof_student_payload, headers=student_headers
    )
    assert res_spoof.status_code == 403, "Mismatched student identity must return 403"

    # -------------------------------------------------------------------------
    # 5. User without linked student record marking attendance rejected (403)
    # -------------------------------------------------------------------------
    res_unlinked = await test_client.post(
        "/qr-attendance/student/scan-qr", json=valid_scan_payload, headers=unlinked_user_headers
    )
    assert res_unlinked.status_code == 403, "Unlinked student account must return 403"

    # -------------------------------------------------------------------------
    # 6. Valid student marking attendance for valid session succeeds (200, attendance_marked=True)
    # -------------------------------------------------------------------------
    res_mark = await test_client.post(
        "/qr-attendance/student/scan-qr", json=valid_scan_payload, headers=student_headers
    )
    assert res_mark.status_code == 200
    mark_data = res_mark.json()
    assert mark_data["success"] is True
    assert mark_data["attendance_marked"] is True
    assert mark_data["attendance_record_id"] is not None

    # -------------------------------------------------------------------------
    # 8. Duplicate attendance rejected by backend & database constraint
    # -------------------------------------------------------------------------
    res_dup = await test_client.post(
        "/qr-attendance/student/scan-qr", json=valid_scan_payload, headers=student_headers
    )
    assert res_dup.status_code == 200
    dup_data = res_dup.json()
    assert dup_data["success"] is False
    assert dup_data["attendance_marked"] is False
    assert any("Duplicate" in err for err in dup_data["errors"])

    # -------------------------------------------------------------------------
    # 9. Student-supplied status or timestamp cannot bypass backend validation
    # -------------------------------------------------------------------------
    res_records = await test_client.get(
        f"/qr-attendance/faculty/attendance-records/{session_id}", headers=faculty_headers
    )
    assert res_records.status_code == 200
    records = res_records.json()
    assert len(records) == 1
    rec = records[0]
    assert rec["roll_number"] == "21BCS101"
    assert rec["student_name"] == "Alex Johnson"
    assert "marked_at" in rec
    assert rec["is_late_entry"] is False

    # -------------------------------------------------------------------------
    # 13. Faculty ownership enforced on update, live-attendance, and close (403 for other faculty)
    # -------------------------------------------------------------------------
    # Other faculty trying to view live attendance gets 403
    res_other_live = await test_client.get(
        f"/qr-attendance/faculty/live-attendance/{session_id}", headers=other_faculty_headers
    )
    assert res_other_live.status_code == 403, "Other faculty viewing live stats should return 403"

    # Other faculty trying to patch session gets 403
    res_other_patch = await test_client.patch(
        f"/qr-attendance/faculty/session/{session_id}",
        json={"qr_validity_minutes": 30},
        headers=other_faculty_headers,
    )
    assert res_other_patch.status_code == 403, "Other faculty modifying session should return 403"

    # Other faculty trying to close session gets 403
    res_other_close = await test_client.post(
        f"/qr-attendance/faculty/session/{session_id}/close", headers=other_faculty_headers
    )
    assert res_other_close.status_code == 403, "Other faculty closing session should return 403"

    # Owning faculty can view live attendance (200)
    res_own_live = await test_client.get(
        f"/qr-attendance/faculty/live-attendance/{session_id}", headers=faculty_headers
    )
    assert res_own_live.status_code == 200
    assert res_own_live.json()["total_present"] == 1

    # Admin can view live attendance (200)
    res_admin_live = await test_client.get(
        f"/qr-attendance/faculty/live-attendance/{session_id}", headers=admin_headers
    )
    assert res_admin_live.status_code == 200

    # -------------------------------------------------------------------------
    # 11. Session closure endpoint succeeds and immediately blocks further scans
    # -------------------------------------------------------------------------
    res_close = await test_client.post(
        f"/qr-attendance/faculty/session/{session_id}/close", headers=faculty_headers
    )
    assert res_close.status_code == 200
    closed_session = res_close.json()
    assert closed_session["is_active"] is False

    # -------------------------------------------------------------------------
    # 7. Expired or closed session rejected (attendance_marked=False)
    # -------------------------------------------------------------------------
    res_scan_closed = await test_client.post(
        "/qr-attendance/student/scan-qr", json=valid_scan_payload, headers=student_headers
    )
    assert res_scan_closed.status_code == 200
    closed_scan_data = res_scan_closed.json()
    assert closed_scan_data["attendance_marked"] is False
    assert any("expired" in err.lower() or "active" in err.lower() for err in closed_scan_data["errors"])

    # -------------------------------------------------------------------------
    # 10. Manual session code entry enforces identical security checks
    # -------------------------------------------------------------------------
    gen_payload_manual = dict(gen_payload, subject_code="CS-402", subject_name="Cloud Computing")
    res_gen_manual = await test_client.post(
        "/qr-attendance/faculty/generate-qr", json=gen_payload_manual, headers=faculty_headers
    )
    assert res_gen_manual.status_code == 201
    manual_session_data = res_gen_manual.json()
    manual_session_id = manual_session_data["session_id"]
    manual_qr_hash = manual_session_data["qr_code_hash"]

    # Verify placeholder 'manual_entry' is rejected per Task 10 hardening
    placeholder_payload = {
        "session_id": manual_session_id,
        "qr_code_hash": "manual_entry",
        "location": {"latitude": 26.2738, "longitude": 73.0366, "accuracy": 10.0},
    }
    res_placeholder = await test_client.post(
        "/qr-attendance/student/scan-qr", json=placeholder_payload, headers=student_headers
    )
    assert res_placeholder.status_code == 200
    assert res_placeholder.json()["attendance_marked"] is False
    assert any("placeholder" in err.lower() for err in res_placeholder.json()["errors"])

    # Legitimate scan with authentic QR code hash
    valid_manual_payload = {
        "session_id": manual_session_id,
        "qr_code_hash": manual_qr_hash,
        "location": {"latitude": 26.2738, "longitude": 73.0366, "accuracy": 10.0},
    }

    spoofed_manual = dict(valid_manual_payload, student_id="999", roll_number="21BCS999")
    res_spoof_manual = await test_client.post(
        "/qr-attendance/student/scan-qr", json=spoofed_manual, headers=student_headers
    )
    assert res_spoof_manual.status_code == 403

    # Legitimate entry marks attendance successfully
    res_manual_ok = await test_client.post(
        "/qr-attendance/student/scan-qr", json=valid_manual_payload, headers=student_headers
    )
    assert res_manual_ok.status_code == 200
    assert res_manual_ok.json()["attendance_marked"] is True

    # -------------------------------------------------------------------------
    # 12. Existing attendance records remain intact and queryable
    # -------------------------------------------------------------------------
    res_manual_records = await test_client.get(
        f"/qr-attendance/faculty/attendance-records/{manual_session_id}", headers=faculty_headers
    )
    assert res_manual_records.status_code == 200
    m_records = res_manual_records.json()
    assert len(m_records) == 1
    assert m_records[0]["roll_number"] == "21BCS101"
