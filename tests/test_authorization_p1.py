"""
Tests for P1 Authorization and IDOR Vulnerabilities
Verifies:
- IDOR prevention: user_id != student_id
- Attendance scoping by resolved student_id
- Complaint scoping by resolved student_id
- Academic risk scoping by resolved student_id
- Student directory restricted to faculty/staff/admin
- AI routes protected and scoped
- Schedule feedback and announcements restricted by role
- 401 Unauthorized for unauthenticated callers
- 403 Forbidden for cross-student / unauthorized role access
"""

import os
import sys
import importlib.abc
import importlib.util
from pathlib import Path

# Automatic loader for sourceless pyc modules in __pycache__
class SourcelessPycFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if not path:
            return None
        name = fullname.split(".")[-1]
        for p in path:
            py = Path(p) / f"{name}.py"
            pyc = Path(p) / "__pycache__" / f"{name}.cpython-313.pyc"
            if not py.is_file() and pyc.is_file():
                return importlib.util.spec_from_file_location(fullname, pyc)
        return None

if not any(isinstance(f, SourcelessPycFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, SourcelessPycFinder())

import pytest
from datetime import datetime, date
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.core.auth import create_access_token, TokenData
from backend.models.student import Student
from backend.models.attendance import Attendance
from backend.models.complaint import Complaint
from backend.models.risk import RiskLog
from backend.models.schedule_feedback import ScheduleFeedback, Announcement

# Import User model via sourceless loader
from backend.models.user import User

# Import routers under test
from backend.routes.attendance import router as attendance_router
from backend.routes.complaint import router as complaint_router
from backend.routes.risk import academic_risk_router, router as legacy_risk_router
from backend.routes.students import router as students_router
from backend.routes.ai import router as ai_router
from backend.routes.schedule_feedback import router as schedule_feedback_router
from backend.routes.analytics import router as analytics_router


# Create in-memory SQLite database for test isolation
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Build a test FastAPI application
app = FastAPI()
app.include_router(attendance_router)
app.include_router(complaint_router)
app.include_router(academic_risk_router)
app.include_router(legacy_risk_router)
app.include_router(students_router)
app.include_router(ai_router)
app.include_router(schedule_feedback_router)
app.include_router(analytics_router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create Students
    # Student 1: Victim (id=1, roll_no="CS999")
    student1 = Student(
        name="Victim Student",
        roll_no="CS999",
        department="Computer Science",
        semester=6,
    )
    # Student 2: Attacker (id=2, roll_no="CS001")
    student2 = Student(
        name="Attacker Student",
        roll_no="CS001",
        department="Computer Science",
        semester=6,
    )
    db.add(student1)
    db.add(student2)
    db.commit()
    db.refresh(student1)
    db.refresh(student2)

    # Create Users
    # User 1: Student account (id=1, username="CS001", linked_student_id=2)
    # CRITICAL IDOR SETUP:
    # User ID is 1, but this user belongs to Student 2 (linked_student_id=2).
    # If code compares current_user.user_id (1) == student_id (1), it would erroneously grant access to Student 1!
    user1 = User(
        username="CS001",
        email="attacker@campus.edu",
        hashed_password="hashed_pw_test",
        full_name="Attacker Student",
        role="student",
        is_active=True,
        linked_student_id=student2.id,  # 2
    )

    # User 2: Faculty account
    user2 = User(
        username="FACULTY01",
        email="faculty@campus.edu",
        hashed_password="hashed_pw_test",
        full_name="Prof. Faculty",
        role="faculty",
        is_active=True,
    )

    # User 3: Staff account
    user3 = User(
        username="STAFF01",
        email="staff@campus.edu",
        hashed_password="hashed_pw_test",
        full_name="Officer Staff",
        role="staff",
        is_active=True,
    )

    db.add(user1)
    db.add(user2)
    db.add(user3)
    db.commit()

    # Create Attendance records
    att1 = Attendance(
        student_id=student1.id,  # 1
        date=date.today(),
        status="Present",
    )
    att2 = Attendance(
        student_id=student2.id,  # 2
        date=date.today(),
        status="Present",
    )
    db.add(att1)
    db.add(att2)

    # Create Complaints
    comp1 = Complaint(
        title="Victim Issue",
        description="Private complaint from student 1",
        category="Hostel",
        status="Pending",
        student_id=student1.id,  # 1
    )
    comp2 = Complaint(
        title="Attacker Issue",
        description="Own complaint from student 2",
        category="Academic",
        status="Pending",
        student_id=student2.id,  # 2
    )
    db.add(comp1)
    db.add(comp2)

    # Create Risk Logs
    risk1 = RiskLog(
        student_id=student1.id,  # 1
        risk_type="Academic",
        severity="High",
        description="Victim risk advisory",
        resolved=0,
    )
    risk2 = RiskLog(
        student_id=student2.id,  # 2
        risk_type="Academic",
        severity="Low",
        description="Attacker risk advisory",
        resolved=0,
    )
    db.add(risk1)
    db.add(risk2)

    # Create Schedule Feedback
    fb1 = ScheduleFeedback(
        name="Victim Student",
        roll_number="CS999",
        issue_type="Timing Conflict",
        additional_comments="Conflict at 9 AM",
        status="pending",
    )
    fb2 = ScheduleFeedback(
        name="Attacker Student",
        roll_number="CS001",
        issue_type="Room Overlap",
        additional_comments="Overlap at 11 AM",
        status="pending",
    )
    db.add(fb1)
    db.add(fb2)

    db.commit()
    db.close()


def get_auth_headers(sub: str, role: str, user_id: int, linked_student_id: int = None):
    token = create_access_token(
        user_id=user_id,
        username=sub,
        role=role,
        linked_student_id=linked_student_id,
    )
    return {"Authorization": f"Bearer {token}"}


# ==================== ATTENDANCE TESTS ====================

def test_attendance_unauthenticated_rejected():
    res = client.get("/attendance/student/1")
    assert res.status_code == 401


def test_attendance_idor_numeric_mismatch_prevented():
    """
    CRITICAL: User ID is 1, but linked_student_id is 2.
    Requesting student_id 1 must be rejected with 403 Forbidden.
    """
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/attendance/student/1", headers=headers)
    assert res.status_code == 403


def test_attendance_student_can_view_own():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/attendance/student/2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["student_id"] == 2


def test_attendance_summary_cross_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/attendance/student/1/summary", headers=headers)
    assert res.status_code == 403


def test_attendance_summary_own_allowed():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/attendance/student/2/summary", headers=headers)
    assert res.status_code == 200


# ==================== COMPLAINT TESTS ====================

def test_complaints_unauthenticated_rejected():
    res = client.get("/complaints/")
    assert res.status_code == 401


def test_complaints_student_list_scoped_to_own():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/complaints/", headers=headers)
    assert res.status_code == 200
    complaints = res.json()
    # Must only contain complaints for student_id 2
    assert all(c["student_id"] == 2 for c in complaints)
    assert not any(c["student_id"] == 1 for c in complaints)


def test_complaints_cross_student_get_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    # Student 1's complaints
    res = client.get("/complaints/student/1", headers=headers)
    assert res.status_code == 403


def test_complaints_own_student_get_allowed():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/complaints/student/2", headers=headers)
    assert res.status_code == 200


def test_complaints_cannot_file_for_another_student():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    payload = {
        "title": "Forged Complaint",
        "description": "Filing on behalf of student 1 without permission",
        "category": "Academic",
        "student_id": 1,
    }
    res = client.post("/complaints/", json=payload, headers=headers)
    assert res.status_code == 403


# ==================== ACADEMIC RISK TESTS ====================

def test_risk_unauthenticated_rejected():
    res = client.get("/risk/student/1")
    assert res.status_code == 401


def test_risk_idor_cross_student_forbidden():
    """
    CRITICAL: User ID is 1, linked_student_id is 2.
    Requesting student 1's risk evaluation must return 403.
    """
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/risk/student/1", headers=headers)
    assert res.status_code == 403


def test_risk_logs_cross_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/risk-logs/student/1", headers=headers)
    assert res.status_code == 403


def test_risk_logs_own_student_allowed():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/risk-logs/student/2", headers=headers)
    assert res.status_code == 200


# ==================== STUDENT DIRECTORY TESTS ====================

def test_students_directory_student_forbidden():
    """
    Students should NOT be able to list all students in the college.
    """
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/students/", headers=headers)
    assert res.status_code == 403


def test_students_directory_faculty_allowed():
    headers = get_auth_headers(sub="FACULTY01", role="faculty", user_id=2)
    res = client.get("/students/", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 2


def test_student_get_by_id_cross_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/students/1", headers=headers)
    assert res.status_code == 403


def test_student_get_by_id_own_allowed():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/students/2", headers=headers)
    assert res.status_code == 200


# ==================== SCHEDULE FEEDBACK & ANNOUNCEMENTS TESTS ====================

def test_schedule_feedback_unauthenticated_rejected():
    res = client.get("/schedule-management/feedback")
    assert res.status_code == 401


def test_schedule_feedback_student_views_only_own():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/schedule-management/feedback", headers=headers)
    assert res.status_code == 200
    feedbacks = res.json()
    assert all(fb["roll_number"] == "CS001" for fb in feedbacks)
    assert not any(fb["roll_number"] == "CS999" for fb in feedbacks)


def test_schedule_feedback_cross_student_detail_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    # Feedback 1 belongs to CS999
    res = client.get("/schedule-management/feedback/1", headers=headers)
    assert res.status_code == 403


def test_schedule_feedback_patch_status_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.patch("/schedule-management/feedback/2", json={"status": "resolved"}, headers=headers)
    assert res.status_code == 403


def test_schedule_feedback_patch_status_staff_allowed():
    headers = get_auth_headers(sub="STAFF01", role="staff", user_id=3)
    res = client.patch("/schedule-management/feedback/2", json={"status": "resolved"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"


def test_announcements_create_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    payload = {
        "title": "Fake Announcement",
        "content": "Class cancelled",
        "priority": "high",
        "target_audience": "all",
    }
    res = client.post("/schedule-management/announcements", json=payload, headers=headers)
    assert res.status_code == 403


def test_announcements_create_faculty_allowed():
    headers = get_auth_headers(sub="FACULTY01", role="faculty", user_id=2)
    payload = {
        "title": "Official Exam Schedule",
        "content": "Midterms start next week",
        "author": "Prof. Faculty",
        "priority": "high",
        "target_audience": "all",
    }
    res = client.post("/schedule-management/announcements", json=payload, headers=headers)
    assert res.status_code == 201
    assert res.json()["title"] == "Official Exam Schedule"


# ==================== AI INTELLIGENCE ROUTE TESTS ====================

def test_ai_explain_attendance_unauthenticated_rejected():
    res = client.get("/ai/explain-attendance/1")
    assert res.status_code == 401


def test_ai_explain_attendance_cross_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/ai/explain-attendance/1", headers=headers)
    assert res.status_code == 403


def test_ai_explain_complaints_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/ai/explain-complaints", headers=headers)
    assert res.status_code == 403


def test_ai_explain_risk_cross_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    # Risk 1 belongs to student 1
    res = client.get("/ai/explain-risk/1", headers=headers)
    assert res.status_code == 403


# ==================== ANALYTICS TESTS ====================

def test_analytics_attendance_trends_unauthenticated_rejected():
    res = client.get("/analytics/attendance-trends/1")
    assert res.status_code == 401


def test_analytics_attendance_trends_cross_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/analytics/attendance-trends/1", headers=headers)
    assert res.status_code == 403


def test_analytics_heatmap_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.get("/analytics/complaint-heatmap", headers=headers)
    assert res.status_code == 403


def test_analytics_detect_anomalies_student_forbidden():
    headers = get_auth_headers(sub="CS001", role="student", user_id=1, linked_student_id=2)
    res = client.post("/analytics/detect-anomalies", headers=headers)
    assert res.status_code == 403
