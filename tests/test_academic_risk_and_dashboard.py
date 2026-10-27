import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from backend.core.auth import create_access_token


@pytest.mark.asyncio
async def test_01_insufficient_data_returns_clean_response(test_client: AsyncClient, staff_headers: dict):
    """
    Students with 0 attendance and 0 tasks return INSUFFICIENT_DATA without division-by-zero errors.
    """
    # 1. Create a student with no records
    create_res = await test_client.post(
        "/students/",
        headers=staff_headers,
        json={
            "name": "Blank Student",
            "roll_no": "21BLANK01",
            "department": "Electrical Engineering",
            "semester": 2,
            "section": "A",
            "email": "blank@campus.edu",
        },
    )
    assert create_res.status_code == 201
    student_id = create_res.json()["id"]

    # 2. Query academic risk
    risk_res = await test_client.get(f"/risk/student/{student_id}", headers=staff_headers)
    assert risk_res.status_code == 200
    data = risk_res.json()

    assert data["student_id"] == student_id
    assert data["risk_level"] == "INSUFFICIENT_DATA"
    assert data["risk_score"] is None
    assert data["data_sufficiency"] == "INSUFFICIENT_DATA"
    assert data["observed_facts"]["total_sessions"] == 0
    assert data["observed_facts"]["attendance_percentage"] is None
    assert data["observed_facts"]["marks_recorded"] is False
    assert "No marks or examination grade records exist" in data["observed_facts"]["marks_note"]
    assert len(data["contributing_reasons"]) > 0


@pytest.mark.asyncio
async def test_02_missing_grades_explicitly_documented_without_penalty(test_client: AsyncClient, staff_headers: dict):
    """
    Missing marks/grades are explicitly documented and not treated as failing/zero.
    """
    # 1. Create a student with 100% attendance
    st_res = await test_client.post(
        "/students/",
        headers=staff_headers,
        json={
            "name": "High Attender",
            "roll_no": "21HIGH01",
            "department": "Civil Engineering",
            "semester": 3,
            "section": "A",
            "email": "high@campus.edu",
        },
    )
    assert st_res.status_code == 201
    student_id = st_res.json()["id"]

    # Add 5 present attendance records
    now = datetime.utcnow()
    for i in range(5):
        await test_client.post(
            "/attendance/",
            headers=staff_headers,
            json={
                "student_id": student_id,
                "subject_code": "CE201",
                "date": (now - timedelta(days=i + 1)).isoformat(),
                "status": "Present",
                "session_name": f"Lecture {i + 1}",
            },
        )

    # 2. Evaluate academic risk
    risk_res = await test_client.get(f"/risk/student/{student_id}", headers=staff_headers)
    assert risk_res.status_code == 200
    data = risk_res.json()

    assert data["risk_level"] == "LOW"
    assert data["risk_score"] == 0  # No penalty for missing grades
    assert data["observed_facts"]["marks_recorded"] is False
    assert any("marks/grades are not recorded" in r.lower() for r in data["contributing_reasons"])


@pytest.mark.asyncio
async def test_03_deduplication_of_qr_and_general_attendance(
    test_client: AsyncClient, student_headers: dict, staff_headers: dict
):
    """
    Unified attendance engine deduplicates general attendance and QR attendance
    records sharing the same student, date, and subject code.
    """
    # Use student1 (id=1, roll_no="21BCS101", CSE)
    student_id = 1
    same_date = datetime(2026, 10, 15, 10, 0, 0)

    # 1. Create general attendance record for 2026-10-15, CS301
    await test_client.post(
        "/attendance/",
        headers=staff_headers,
        json={
            "student_id": student_id,
            "subject_code": "CS301",
            "date": same_date.isoformat(),
            "status": "Present",
        },
    )

    # 2. Create QR session and record for same day and subject
    qr_session_res = await test_client.post(
        "/qr-attendance/faculty/generate-qr",
        headers=staff_headers,
        json={
            "faculty_id": "fac_101",
            "faculty_name": "Dr. Smith",
            "subject_code": "CS301",
            "subject_name": "Data Structures",
            "branch": "Computer Science Engineering",
            "semester": "4",
            "section": "A",
            "lecture_date": same_date.isoformat(),
            "lecture_start_time": same_date.isoformat(),
            "center_latitude": 26.29,
            "center_longitude": 73.02,
            "qr_validity_minutes": 10,
        },
    )
    assert qr_session_res.status_code == 201
    session_id = qr_session_res.json()["session_id"]
    qr_hash = qr_session_res.json()["qr_code_hash"]

    # Mark attendance via QR as student1
    scan_res = await test_client.post(
        "/qr-attendance/student/scan-qr",
        headers=student_headers,
        json={
            "session_id": session_id,
            "qr_code_hash": qr_hash,
            "student_id": str(student_id),
            "roll_number": "21BCS101",
            "student_name": "Alex Johnson",
            "location": {
                "latitude": 26.29,
                "longitude": 73.02,
            },
        },
    )
    assert scan_res.status_code == 200

    # 3. Add an Absent record on a different day
    diff_date = datetime(2026, 10, 16, 10, 0, 0)
    await test_client.post(
        "/attendance/",
        headers=staff_headers,
        json={
            "student_id": student_id,
            "subject_code": "CS301",
            "date": diff_date.isoformat(),
            "status": "Absent",
        },
    )

    # 4. Check Risk evaluation
    risk_res = await test_client.get(f"/risk/student/{student_id}", headers=staff_headers)
    assert risk_res.status_code == 200
    risk_data = risk_res.json()

    # Total sessions must be 2 (October 15 deduplicated into 1, October 16 is second)
    assert risk_data["observed_facts"]["total_sessions"] == 2
    assert risk_data["observed_facts"]["attended_sessions"] == 1
    assert risk_data["observed_facts"]["attendance_percentage"] == 50.0


@pytest.mark.asyncio
async def test_04_low_attendance_and_subject_deficits_scoring(test_client: AsyncClient, staff_headers: dict):
    """
    Attendance below 60% triggers +40 pts penalty plus subject deficit points,
    resulting in HIGH or MEDIUM risk.
    """
    st_res = await test_client.post(
        "/students/",
        headers=staff_headers,
        json={
            "name": "Low Attender",
            "roll_no": "21LOW01",
            "department": "Computer Science Engineering",
            "semester": 4,
            "section": "A",
            "email": "low@campus.edu",
        },
    )
    student_id = st_res.json()["id"]

    # Add 1 Present and 4 Absent records in CS101 (20% attendance)
    now = datetime.utcnow()
    await test_client.post(
        "/attendance/",
        headers=staff_headers,
        json={
            "student_id": student_id,
            "subject_code": "CS101",
            "date": now.isoformat(),
            "status": "Present",
        },
    )
    for i in range(1, 5):
        await test_client.post(
            "/attendance/",
            headers=staff_headers,
            json={
                "student_id": student_id,
                "subject_code": "CS101",
                "date": (now - timedelta(days=i)).isoformat(),
                "status": "Absent",
            },
        )

    risk_res = await test_client.get(f"/risk/student/{student_id}", headers=staff_headers)
    assert risk_res.status_code == 200
    data = risk_res.json()

    assert data["observed_facts"]["attendance_percentage"] == 20.0
    assert data["risk_score"] >= 45  # 40 (attendance < 60%) + 5 (CS101 < 75%)
    assert data["risk_level"] in ("MEDIUM", "HIGH")
    assert any("CS101" in s for s in data["observed_facts"]["subjects_below_threshold"])


@pytest.mark.asyncio
async def test_05_study_tasks_engagement_and_overdue_penalties(
    test_client: AsyncClient, student_headers: dict, staff_headers: dict
):
    """
    Overdue study tasks contribute to the academic risk score and show up in the dashboard.
    """
    # Create an overdue study task for student1
    past_due = (datetime.utcnow() - timedelta(days=2)).isoformat()
    task_res = await test_client.post(
        "/api/v1/study-tasks",
        headers=student_headers,
        json={
            "title": "Overdue DS Assignment",
            "description": "Complete binary tree traversal",
            "duration_minutes": 60,
            "remaining_seconds": 1800,
            "due_date": past_due,
        },
    )
    assert task_res.status_code == 201

    # Check student dashboard
    dash_res = await test_client.get("/dashboard/student/me", headers=student_headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()

    assert dash_data["study_tasks"]["total_tasks"] >= 1
    assert dash_data["study_tasks"]["overdue_tasks"] >= 1
    assert dash_data["study_tasks"]["study_hours"] >= 0.5


@pytest.mark.asyncio
async def test_06_student_can_access_own_risk_via_my_risk(test_client: AsyncClient, student_headers: dict):
    """Authenticated student can read their own academic risk evaluation via /risk/my-risk"""
    response = await test_client.get("/risk/my-risk", headers=student_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["student_name"] == "Alex Johnson"
    assert data["roll_no"] == "21BCS101"
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_07_student_cannot_access_another_student_risk(
    test_client: AsyncClient, student_headers: dict, staff_headers: dict
):
    """Student attempting to view another student's risk evaluation is rejected with 403 Forbidden"""
    # Create another student
    other_res = await test_client.post(
        "/students/",
        headers=staff_headers,
        json={
            "name": "Other Peer",
            "roll_no": "21PEER99",
            "department": "Computer Science Engineering",
            "semester": 4,
            "section": "A",
            "email": "peer@campus.edu",
        },
    )
    assert other_res.status_code == 201
    other_id = other_res.json()["id"]

    # Student1 attempts to read other_id
    forbidden_res = await test_client.get(f"/risk/student/{other_id}", headers=student_headers)
    assert forbidden_res.status_code == 403
    assert "Access denied" in forbidden_res.json()["detail"]


@pytest.mark.asyncio
async def test_08_faculty_scope_enforcement(test_client: AsyncClient, admin_headers: dict, staff_headers: dict):
    """
    Faculty access to student risk is scoped to their authorized teaching/department scope.
    """
    # 1. Create a student in Aerospace Engineering
    aero_res = await test_client.post(
        "/students/",
        headers=staff_headers,
        json={
            "name": "Aero Student",
            "roll_no": "21AERO01",
            "department": "Aerospace Engineering",
            "semester": 6,
            "section": "A",
            "email": "aero@campus.edu",
        },
    )
    student_id = aero_res.json()["id"]

    # 2. Admin provisions an unscoped faculty user in the database
    fac_create_res = await test_client.post(
        "/api/v1/auth/admin/create-user",
        headers=admin_headers,
        json={
            "username": "fac_unscoped",
            "email": "fac_unscoped@campus.edu",
            "password": "Password123!",
            "role": "faculty",
            "full_name": "Prof. Unscoped",
        },
    )
    assert fac_create_res.status_code == 201
    fac_user_id = fac_create_res.json()["user_id"]

    unscoped_faculty_token = create_access_token(user_id=fac_user_id, username="fac_unscoped", role="faculty")
    unscoped_headers = {"Authorization": f"Bearer {unscoped_faculty_token}"}

    # Should be rejected with 403
    forbidden_res = await test_client.get(f"/risk/student/{student_id}", headers=unscoped_headers)
    assert forbidden_res.status_code == 403

    # 3. Staff / Admin have institutional access
    admin_res = await test_client.get(f"/risk/student/{student_id}", headers=admin_headers)
    assert admin_res.status_code == 200


@pytest.mark.asyncio
async def test_09_student_dashboard_consolidated_payload(test_client: AsyncClient, student_headers: dict):
    """
    GET /dashboard/student/me returns the consolidated dashboard payload for the authenticated student.
    """
    response = await test_client.get("/dashboard/student/me", headers=student_headers)
    assert response.status_code == 200
    data = response.json()

    assert "student" in data
    assert data["student"]["name"] == "Alex Johnson"
    assert "attendance" in data
    assert "academics" in data
    assert data["academics"]["grades_available"] is False
    assert data["academics"]["cgpa"] is None
    assert "study_tasks" in data
    assert "academic_risk" in data
    assert "campus_involvement" in data


@pytest.mark.asyncio
async def test_10_student_cannot_access_privileged_dashboard_endpoints(
    test_client: AsyncClient, student_headers: dict
):
    """Students cannot access faculty or admin dashboard reporting endpoints (403 Forbidden)"""
    res1 = await test_client.get("/dashboard/risks/students", headers=student_headers)
    assert res1.status_code == 403

    res2 = await test_client.get("/dashboard/attendance/low-attendance", headers=student_headers)
    assert res2.status_code == 403

    res3 = await test_client.get("/dashboard/complaints/priority", headers=student_headers)
    assert res3.status_code == 403

    res4 = await test_client.get("/dashboard/schedule/conflicts", headers=student_headers)
    assert res4.status_code == 403


@pytest.mark.asyncio
async def test_11_faculty_and_admin_can_access_dashboard_metrics(
    test_client: AsyncClient, staff_headers: dict
):
    """Staff and faculty can access authorized dashboard endpoints"""
    res1 = await test_client.get("/dashboard/risks/students", headers=staff_headers)
    assert res1.status_code == 200

    res2 = await test_client.get("/dashboard/attendance/low-attendance", headers=staff_headers)
    assert res2.status_code == 200

    res3 = await test_client.get("/dashboard/summary", headers=staff_headers)
    assert res3.status_code == 200
    summary = res3.json()
    assert "total_students" in summary
    assert "students_at_risk" in summary

    # Unauthenticated access rejected
    unauth_res = await test_client.get("/dashboard/summary")
    assert unauth_res.status_code == 401


@pytest.mark.asyncio
async def test_12_timetable_my_schedule_and_audience_filtering(
    test_client: AsyncClient, student_headers: dict, staff_headers: dict
):
    """
    GET /schedules/my-schedule returns relevant institutional schedules based on user audience scope.
    """
    now = datetime.utcnow()
    # Create Schedule 1 for "All"
    await test_client.post(
        "/schedules/",
        headers=staff_headers,
        json={
            "title": "Campus Convocation",
            "description": "Annual student convocation",
            "event_type": "Event",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=5, hours=2)).isoformat(),
            "location": "Auditorium",
            "audience": "All",
        },
    )

    # Create Schedule 2 for student's department ("Computer Science Engineering")
    await test_client.post(
        "/schedules/",
        headers=staff_headers,
        json={
            "title": "CSE Midterm Exam",
            "description": "Midterm examinations for CSE",
            "event_type": "Exam",
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=10, hours=3)).isoformat(),
            "location": "Exam Hall 1",
            "audience": "Computer Science Engineering",
        },
    )

    # Create Schedule 3 for different department ("Civil Engineering")
    await test_client.post(
        "/schedules/",
        headers=staff_headers,
        json={
            "title": "Civil Surveying Lab",
            "description": "Field lab for civil students",
            "event_type": "Class",
            "start_date": (now + timedelta(days=3)).isoformat(),
            "end_date": (now + timedelta(days=3, hours=2)).isoformat(),
            "location": "Field A",
            "audience": "Civil Engineering",
        },
    )

    # Student 1 is CSE department
    sched_res = await test_client.get("/schedules/my-schedule", headers=student_headers)
    assert sched_res.status_code == 200
    schedules = sched_res.json()

    titles = [s["title"] for s in schedules]
    assert "Campus Convocation" in titles
    assert "CSE Midterm Exam" in titles
    assert "Civil Surveying Lab" not in titles


@pytest.mark.asyncio
async def test_13_students_cannot_modify_institutional_schedules(
    test_client: AsyncClient, student_headers: dict
):
    """Students cannot create, update, or delete institutional schedules (403 Forbidden)"""
    now = datetime.utcnow()
    # 1. Attempt create
    create_res = await test_client.post(
        "/schedules/",
        headers=student_headers,
        json={
            "title": "Hacked Class",
            "description": "Fake class",
            "event_type": "Class",
            "start_date": (now + timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=1, hours=1)).isoformat(),
            "location": "Room 101",
        },
    )
    assert create_res.status_code == 403

    # 2. Attempt update
    update_res = await test_client.put(
        "/schedules/1",
        headers=student_headers,
        json={"title": "Altered Class"},
    )
    assert update_res.status_code == 403

    # 3. Attempt delete
    delete_res = await test_client.delete("/schedules/1", headers=student_headers)
    assert delete_res.status_code == 403


@pytest.mark.asyncio
async def test_14_schedule_validation_and_duplicate_prevention(
    test_client: AsyncClient, staff_headers: dict
):
    """
    Schedule creation rejects invalid dates (end <= start) and duplicate active schedules (409 Conflict).
    """
    now = datetime.utcnow()
    # 1. Invalid time range
    bad_time_res = await test_client.post(
        "/schedules/",
        headers=staff_headers,
        json={
            "title": "Bad Time Class",
            "event_type": "Class",
            "start_date": (now + timedelta(days=2)).isoformat(),
            "end_date": (now + timedelta(days=1)).isoformat(),  # End before start
            "location": "Room 202",
        },
    )
    assert bad_time_res.status_code == 400

    # 2. Valid creation
    good_res = await test_client.post(
        "/schedules/",
        headers=staff_headers,
        json={
            "title": "Unique Workshop",
            "event_type": "Event",
            "start_date": (now + timedelta(days=7)).isoformat(),
            "end_date": (now + timedelta(days=7, hours=2)).isoformat(),
            "location": "Hall B",
        },
    )
    assert good_res.status_code == 201

    # 3. Duplicate creation attempt
    dup_res = await test_client.post(
        "/schedules/",
        headers=staff_headers,
        json={
            "title": "Unique Workshop",
            "event_type": "Event",
            "start_date": (now + timedelta(days=7)).isoformat(),
            "end_date": (now + timedelta(days=7, hours=2)).isoformat(),
            "location": "Hall B",
        },
    )
    assert dup_res.status_code == 409
    assert "identical" in dup_res.json()["detail"].lower()
