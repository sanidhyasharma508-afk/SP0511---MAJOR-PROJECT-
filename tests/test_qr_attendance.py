"""
Tests for QR-based Attendance System with Geo-Fencing and Role-Based Authorization
Tests faculty generation, unauthorized rejections, anti-impersonation, student scan, and live dashboards
"""

import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_full_qr_attendance_flow(test_client, faculty_headers, student_headers):
    now = datetime.utcnow()
    
    gen_payload = {
        "faculty_id": "faculty_001",
        "faculty_name": "Dr. Sharma",
        "faculty_email": "sharma@mbm.edu",
        "subject_code": "CS-302",
        "subject_name": "Computer Networks",
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
        "location_name": "Room 304, Main Block",
        "total_students_expected": 60,
        "allow_screenshot_scan": True,
        "require_device_verification": False
    }

    # 1a. Unauthenticated request to generate QR session is rejected (401)
    unauth_gen = await test_client.post("/qr-attendance/faculty/generate-qr", json=gen_payload)
    assert unauth_gen.status_code == 401

    # 1b. Student attempting to generate faculty QR is forbidden (403)
    student_gen = await test_client.post("/qr-attendance/faculty/generate-qr", json=gen_payload, headers=student_headers)
    assert student_gen.status_code == 403

    # 1c. Faculty generates QR session successfully (201)
    gen_res = await test_client.post("/qr-attendance/faculty/generate-qr", json=gen_payload, headers=faculty_headers)
    assert gen_res.status_code == 201
    session_data = gen_res.json()
    assert "session_id" in session_data
    assert session_data["is_active"] is True
    session_id = session_data["session_id"]

    # 2. Faculty retrieves QR code image
    img_res = await test_client.get(f"/qr-attendance/faculty/qr-image/{session_id}", headers=faculty_headers)
    assert img_res.status_code == 200
    img_data = img_res.json()
    assert "qr_code_base64" in img_data
    assert len(img_data["qr_code_base64"]) > 50

    scan_payload = {
        "session_id": session_id,
        "student_id": "1",
        "roll_number": "21BCS101",
        "student_name": "Alex Johnson",
        "student_email": "alex@student.mbm.edu",
        "branch": "CS",
        "semester": 4,
        "section": "A",
        "qr_code_hash": session_data["qr_code_hash"],
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 10.0
        },
        "device": {
            "device_id": "device_win_demo_1",
            "device_model": "Chrome on Windows",
            "device_os": "Windows",
            "browser": "Chrome"
        },
        "scan_timestamp": now.isoformat(),
        "scan_duration_ms": 1200
    }

    # 3a. Unauthenticated student scan is rejected (401)
    unauth_scan = await test_client.post("/qr-attendance/student/scan-qr", json=scan_payload)
    assert unauth_scan.status_code == 401

    # 3b. Authenticated student scan passes (200)
    scan_res = await test_client.post("/qr-attendance/student/scan-qr", json=scan_payload, headers=student_headers)
    assert scan_res.status_code == 200
    scan_result = scan_res.json()
    assert scan_result["success"] is True
    assert scan_result["attendance_marked"] is True

    # 3c. Impersonation attempt: student trying to submit for another student_id is forbidden (403)
    impersonate_payload = dict(scan_payload, student_id="999", roll_number="21BCS999")
    impersonate_res = await test_client.post("/qr-attendance/student/scan-qr", json=impersonate_payload, headers=student_headers)
    assert impersonate_res.status_code == 403

    # 4. Duplicate scan attempt is rejected
    dup_res = await test_client.post("/qr-attendance/student/scan-qr", json=scan_payload, headers=student_headers)
    assert dup_res.status_code == 200
    dup_result = dup_res.json()
    assert dup_result["success"] is False
    assert dup_result["attendance_marked"] is False
    assert "Duplicate attendance attempt" in dup_result["errors"]

    # 5. Live attendance stats for faculty
    stats_res = await test_client.get(f"/qr-attendance/faculty/live-attendance/{session_id}", headers=faculty_headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_present"] == 1
    assert stats["total_expected"] == 60

    # 6. Student dashboard reflects attendance
    dash_res = await test_client.get("/qr-attendance/student/dashboard/1", headers=student_headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["student_id"] == "1"
    assert dash_data["today_attended"] >= 1
    assert len(dash_data["recent_attendance"]) >= 1
