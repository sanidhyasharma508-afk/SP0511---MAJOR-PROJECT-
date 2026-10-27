import pytest
from datetime import datetime, timedelta


# ==============================================================================
# 1. CLUBS & MEMBERSHIPS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_clubs_permissions_and_lifecycle(test_client, student_headers, staff_headers, admin_headers):
    """
    Test club creation, role enforcement, joining, duplicate prevention,
    membership viewing, and leaving.
    """
    # 1. Student cannot create a club (403 Forbidden)
    student_club_payload = {
        "name": "Unauthorized Student Club",
        "description": "Student trying to create club",
        "category": "Technology",
        "advisor": "None"
    }
    resp = await test_client.post("/clubs/", json=student_club_payload, headers=student_headers)
    assert resp.status_code == 403

    # 2. Staff creates a valid club
    staff_club_payload = {
        "name": "Robotics Innovators Club",
        "description": "Designing and programming robots",
        "category": "Technical",
        "advisor": "Dr. Sarah Connor"
    }
    create_resp = await test_client.post("/clubs/", json=staff_club_payload, headers=staff_headers)
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]
    initial_members = create_resp.json()["member_count"]

    # 3. Student joins the club
    join_resp = await test_client.post(f"/clubs/{club_id}/join", headers=student_headers)
    assert join_resp.status_code == 201
    join_data = join_resp.json()
    assert join_data["club_id"] == club_id
    assert join_data["position"] == "Member"

    # Verify club member count incremented
    get_club_resp = await test_client.get(f"/clubs/{club_id}", headers=student_headers)
    assert get_club_resp.status_code == 200
    assert get_club_resp.json()["member_count"] == initial_members + 1

    # 4. Duplicate join attempt should fail with 400 Bad Request
    dup_join_resp = await test_client.post(f"/clubs/{club_id}/join", headers=student_headers)
    assert dup_join_resp.status_code == 400
    assert "already a member" in dup_join_resp.json()["detail"].lower()

    # 5. Student views own memberships
    my_memberships_resp = await test_client.get("/clubs/my-memberships", headers=student_headers)
    assert my_memberships_resp.status_code == 200
    memberships = my_memberships_resp.json()
    assert any(m["club_id"] == club_id for m in memberships)

    # 6. Student cannot add activities to the club (403 Forbidden)
    act_payload = {
        "club_id": club_id,
        "title": "Hacker Meeting",
        "description": "Unauthorized meeting",
        "activity_type": "Meeting",
        "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat()
    }
    unauth_act_resp = await test_client.post(f"/clubs/{club_id}/activities", json=act_payload, headers=student_headers)
    assert unauth_act_resp.status_code == 403

    # Staff can add activity
    staff_act_resp = await test_client.post(f"/clubs/{club_id}/activities", json=act_payload, headers=staff_headers)
    assert staff_act_resp.status_code == 201

    # 7. Student leaves the club
    leave_resp = await test_client.post(f"/clubs/{club_id}/leave", headers=student_headers)
    assert leave_resp.status_code == 200
    assert leave_resp.json()["success"] is True

    # Verify member count decremented
    get_club_after_leave = await test_client.get(f"/clubs/{club_id}", headers=student_headers)
    assert get_club_after_leave.json()["member_count"] == initial_members

    # 8. Student cannot delete the club (403 Forbidden)
    del_resp = await test_client.delete(f"/clubs/{club_id}", headers=student_headers)
    assert del_resp.status_code == 403


# ==============================================================================
# 2. EVENTS & REGISTRATIONS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_events_lifecycle_capacity_and_security(test_client, student_headers, staff_headers, admin_headers):
    """
    Test event creation permissions, student registration, anti-impersonation,
    capacity bounds, duplicate prevention, cancellation, and protected operations.
    """
    now = datetime.utcnow()
    event_payload = {
        "name": "Autonomous Rover Challenge 2026",
        "description": "Build and navigate autonomous rovers through obstacle courses",
        "category": "technical",
        "registration_start_date": (now - timedelta(days=1)).isoformat(),
        "registration_end_date": (now + timedelta(days=2)).isoformat(),
        "event_start_date": (now + timedelta(days=3)).isoformat(),
        "event_end_date": (now + timedelta(days=4)).isoformat(),
        "organizer_name": "Dr. Sarah Connor",
        "organizer_email": "sarah.connor@mbm.ac.in",
        "max_participants": 2,
        "entry_fee": 0.0,
        "requires_approval": False
    }

    # 1. Student cannot create an event (403 Forbidden)
    student_create_resp = await test_client.post("/events/", json=event_payload, headers=student_headers)
    assert student_create_resp.status_code == 403

    # 2. Staff creates event
    create_resp = await test_client.post("/events/", json=event_payload, headers=staff_headers)
    assert create_resp.status_code == 201
    event_data = create_resp.json()
    event_id = event_data["id"]
    assert event_data["status"] == "registration_open"
    assert event_data["current_participants"] == 0

    # 3. Student registers for event under own identity (linked_student_id=1)
    reg_payload = {
        "event_id": event_id,
        "student_id": "1",
        "student_name": "Alex Johnson",
        "student_email": "alex.johnson@mbm.ac.in",
        "student_phone": "9876543210",
        "branch": "Computer Science",
        "year": "3rd Year",
        "roll_number": "21BCS101"
    }
    reg_resp = await test_client.post("/events/registrations", json=reg_payload, headers=student_headers)
    assert reg_resp.status_code == 201
    reg_id = reg_resp.json()["id"]

    # Verify event participant count updated
    event_check = await test_client.get(f"/events/{event_id}")
    assert event_check.json()["current_participants"] == 1

    # 4. Anti-impersonation: Student cannot register for another student_id (999)
    fake_reg_payload = {
        "event_id": event_id,
        "student_id": "999",
        "student_name": "Impersonated Student",
        "student_email": "fake@mbm.ac.in",
        "student_phone": "9876543210"
    }
    fake_reg_resp = await test_client.post("/events/registrations", json=fake_reg_payload, headers=student_headers)
    assert fake_reg_resp.status_code == 403
    assert "cannot register for event on behalf of another student" in fake_reg_resp.json()["detail"].lower()

    # 5. Prevent duplicate registration
    dup_reg_resp = await test_client.post("/events/registrations", json=reg_payload, headers=student_headers)
    assert dup_reg_resp.status_code == 400
    assert "already registered" in dup_reg_resp.json()["detail"].lower()

    # 6. Student views their registrations
    my_regs_resp = await test_client.get("/events/my-registrations", headers=student_headers)
    assert my_regs_resp.status_code == 200
    assert any(r["id"] == reg_id for r in my_regs_resp.json())

    # 7. Student cancels registration
    cancel_resp = await test_client.post(f"/events/registrations/{reg_id}/cancel", headers=student_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Verify participant count decremented
    event_after_cancel = await test_client.get(f"/events/{event_id}")
    assert event_after_cancel.json()["current_participants"] == 0

    # 8. Re-registering after cancellation succeeds
    re_reg_resp = await test_client.post("/events/registrations", json=reg_payload, headers=student_headers)
    assert re_reg_resp.status_code == 200 or re_reg_resp.status_code == 201
    event_after_re_reg = await test_client.get(f"/events/{event_id}")
    assert event_after_re_reg.json()["current_participants"] == 1

    # 9. Student cannot update or delete events
    update_resp = await test_client.put(f"/events/{event_id}", json={"name": "Hacked Event"}, headers=student_headers)
    assert update_resp.status_code == 403

    del_event_resp = await test_client.delete(f"/events/{event_id}", headers=student_headers)
    assert del_event_resp.status_code == 403

    # Student cannot create leaderboard entries or announcements
    lb_payload = {
        "event_id": event_id,
        "participant_id": "1",
        "participant_name": "Alex",
        "score": 100.0
    }
    lb_resp = await test_client.post("/events/leaderboard", json=lb_payload, headers=student_headers)
    assert lb_resp.status_code == 403


# ==============================================================================
# 3. COMPLAINTS & FEEDBACK TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_complaints_workflow_and_rbac(test_client, student_headers, staff_headers, admin_headers):
    """
    Test complaint filing, anti-impersonation, student visibility restrictions,
    staff status updates with audit trail, and rejection of invalid status transitions.
    """
    # 1. Student files a valid complaint
    complaint_payload = {
        "title": "Lab 3 Air Conditioning Malfunction",
        "description": "The AC in Computer Lab 3 is leaking water onto workstations.",
        "category": "Academic",
        "priority": "High"
    }
    create_resp = await test_client.post("/complaints/", json=complaint_payload, headers=student_headers)
    assert create_resp.status_code == 201
    comp_data = create_resp.json()
    comp_id = comp_data["id"]
    assert comp_data["status"] == "Pending"
    assert comp_data["student_id"] == 1

    # 2. Anti-impersonation: Student cannot file complaint under student_id=999
    fake_comp_payload = {
        "student_id": 999,
        "title": "Impersonated Academic Complaint",
        "description": "Filing fake complaint as another student",
        "category": "Academic"
    }
    fake_resp = await test_client.post("/complaints/", json=fake_comp_payload, headers=student_headers)
    assert fake_resp.status_code == 403
    assert "Cannot file complaint on behalf of another student" in fake_resp.json()["detail"]

    # 3. Student views own complaints list
    list_resp = await test_client.get("/complaints/", headers=student_headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == comp_id for c in list_resp.json())

    # 4. Student cannot update complaint status or resolution notes (403 Forbidden)
    student_update_resp = await test_client.put(
        f"/complaints/{comp_id}",
        json={"status": "Resolved", "resolution_notes": "I resolved it myself"},
        headers=student_headers
    )
    assert student_update_resp.status_code == 403

    # 5. Invalid status transition rejected (Pending -> Resolved is invalid; must go through Under Review/In Progress)
    invalid_trans_resp = await test_client.put(
        f"/complaints/{comp_id}",
        json={"status": "Resolved"},
        headers=staff_headers
    )
    assert invalid_trans_resp.status_code == 400
    assert "invalid status transition" in invalid_trans_resp.json()["detail"].lower()

    # 6. Staff transitions status to "In Progress" with resolution notes
    valid_trans_resp = await test_client.put(
        f"/complaints/{comp_id}",
        json={
            "status": "In Progress",
            "resolution_notes": "Dispatched maintenance team to inspect Lab 3"
        },
        headers=staff_headers
    )
    assert valid_trans_resp.status_code == 200
    assert valid_trans_resp.json()["status"] == "In Progress"
    assert "Dispatched maintenance" in valid_trans_resp.json()["resolution_notes"]

    # 7. Audit trail verification
    history_resp = await test_client.get(f"/complaints/{comp_id}/history", headers=student_headers)
    assert history_resp.status_code == 200
    history_items = history_resp.json()
    assert len(history_items) >= 2  # created + status_change
    assert history_items[0]["action"] == "created"
    assert "status_change" in history_items[1]["action"]
    assert history_items[1]["status"] == "In Progress"


# ==============================================================================
# 4. GENERAL ATTENDANCE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_general_attendance_security_and_scoping(test_client, student_headers, staff_headers, admin_headers, other_faculty_headers):
    """
    Test general attendance recording, student blocking, duplicate prevention,
    ownership enforcement, summary calculations, and faculty scoping.
    """
    # 1. Student cannot record attendance (403 Forbidden)
    student_rec_payload = {
        "student_id": 1,
        "status": "Present",
        "subject_code": "CS401",
        "remarks": "Marking myself present"
    }
    student_block_resp = await test_client.post("/attendance/", json=student_rec_payload, headers=student_headers)
    assert student_block_resp.status_code == 403

    # 2. Faculty records attendance
    target_date = datetime.utcnow()
    faculty_rec_payload = {
        "student_id": 1,
        "status": "Present",
        "subject_code": "CS401",
        "session_name": "Lecture 12 - Distributed Systems",
        "date": target_date.isoformat(),
        "remarks": "On time"
    }
    rec_resp = await test_client.post("/attendance/", json=faculty_rec_payload, headers=staff_headers)
    assert rec_resp.status_code == 201
    att_id = rec_resp.json()["id"]
    assert rec_resp.json()["status"] == "Present"
    assert rec_resp.json()["faculty_id"] == "2"  # staff1 user_id is 2

    # 3. Duplicate attendance on the same day/subject is rejected
    dup_resp = await test_client.post("/attendance/", json=faculty_rec_payload, headers=staff_headers)
    assert dup_resp.status_code == 400
    assert "already recorded" in dup_resp.json()["detail"].lower()

    # 4. Student views their own attendance records
    student_view_resp = await test_client.get("/attendance/student/1", headers=student_headers)
    assert student_view_resp.status_code == 200
    assert len(student_view_resp.json()) >= 1

    # 5. Student cannot view another student's attendance records (403 Forbidden)
    student_forbidden_resp = await test_client.get("/attendance/student/999", headers=student_headers)
    assert student_forbidden_resp.status_code == 403

    # 6. Student views attendance summary
    summary_resp = await test_client.get("/attendance/student/1/summary", headers=student_headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["student_id"] == 1
    assert summary["total_records"] >= 1
    assert summary["present_count"] >= 1
    assert summary["attendance_percentage"] > 0
    assert "CS401" in summary["by_subject"]

    # 7. Faculty scoping: another faculty member cannot edit this attendance record
    other_edit_resp = await test_client.put(
        f"/attendance/{att_id}",
        json={"status": "Absent", "remarks": "Changed by other faculty"},
        headers=other_faculty_headers
    )
    assert other_edit_resp.status_code == 403
    assert "only edit attendance records you recorded" in other_edit_resp.json()["detail"].lower()

    # Creating faculty can update the record
    owner_edit_resp = await test_client.put(
        f"/attendance/{att_id}",
        json={"status": "Late", "remarks": "Arrived 10 minutes late"},
        headers=staff_headers
    )
    assert owner_edit_resp.status_code == 200
    assert owner_edit_resp.json()["status"] == "Late"
