"""
Regression Test Suite for Task 10: Eliminating QR Attendance Verification Bypasses

Verifies all 10 required test cases:
1. Missing verification hash is rejected.
2. Empty or whitespace verification hash is rejected.
3. Placeholder values (hash_placeholder, manual_entry, demo_scan) are rejected.
4. Tampered or mismatched verification hash is rejected.
5. Expired QR session is rejected.
6. Valid QR attendance succeeds for an authorized student within the geofence.
7. Student cannot mark attendance for another student (HTTP 403 Forbidden).
8. Unauthorized user cannot create a QR session (HTTP 401/403).
9. Duplicate attendance submissions are rejected / flagged.
10. Legitimate manual attendance by authorized staff continues to work via its designated route.
"""

import sys
import importlib.abc
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta

# Sourceless pyc finder for runtime loading of compiled pyc models
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
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.core.auth import create_access_token
from backend.models.student import Student
from backend.models.user import User
from backend.models.attendance import Attendance
from backend.models.qr_attendance import (
    QRAttendanceSession,
    QRAttendanceRecord,
    QRAttendanceLog,
    DeviceFingerprint,
)

# Routers under test
from backend.routes.qr_attendance import router as qr_attendance_router
from backend.routes.attendance import router as attendance_router

# Setup isolated in-memory SQLite database
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()
app.include_router(qr_attendance_router)
app.include_router(attendance_router)

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
    student1 = Student(
        id=1,
        name="Alice Student",
        roll_no="2024CS001",
        department="Computer Science",
        semester=4,
        section="A",
    )
    student2 = Student(
        id=2,
        name="Bob Student",
        roll_no="2024CS002",
        department="Computer Science",
        semester=4,
        section="A",
    )
    db.add(student1)
    db.add(student2)
    db.commit()

    # Create Users
    faculty_user = User(
        id=10,
        username="prof_sharma",
        email="prof_sharma@campus.edu",
        hashed_password="hashed_password_test",
        full_name="Prof. Sharma",
        role="faculty",
        is_active=True,
    )
    staff_user = User(
        id=20,
        username="staff_john",
        email="staff_john@campus.edu",
        hashed_password="hashed_password_test",
        full_name="John Staff",
        role="staff",
        is_active=True,
    )
    student1_user = User(
        id=101,
        username="2024CS001",
        email="alice@campus.edu",
        hashed_password="hashed_password_test",
        full_name="Alice Student",
        role="student",
        linked_student_id=1,
        is_active=True,
    )
    student2_user = User(
        id=102,
        username="2024CS002",
        email="bob@campus.edu",
        hashed_password="hashed_password_test",
        full_name="Bob Student",
        role="student",
        linked_student_id=2,
        is_active=True,
    )

    db.add_all([faculty_user, staff_user, student1_user, student2_user])
    db.commit()
    db.close()


@pytest.fixture
def faculty_headers():
    token = create_access_token(
        user_id=10, username="prof_sharma", role="faculty"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff_headers():
    token = create_access_token(
        user_id=20, username="staff_john", role="staff"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student1_headers():
    token = create_access_token(
        user_id=101, username="2024CS001", role="student", linked_student_id=1
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student2_headers():
    token = create_access_token(
        user_id=102, username="2024CS002", role="student", linked_student_id=2
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def active_qr_session(faculty_headers):
    """Generates an authentic active QR session via the faculty endpoint."""
    now = datetime.utcnow()
    payload = {
        "subject_code": f"CS301_{now.timestamp()}",
        "subject_name": "Operating Systems",
        "branch": "Computer Science",
        "semester": "4",
        "section": "A",
        "lecture_date": now.isoformat(),
        "lecture_start_time": now.isoformat(),
        "lecture_duration_minutes": 60,
        "center_latitude": 26.2738,
        "center_longitude": 73.0366,
        "geo_fence_radius_meters": 50.0,
        "location_name": "Lab 101",
        "qr_validity_minutes": 10,
        "total_students_expected": 60,
        "require_device_verification": False,
    }
    response = client.post(
        "/qr-attendance/faculty/generate-qr",
        json=payload,
        headers=faculty_headers,
    )
    assert response.status_code == 201, f"Failed to create session: {response.text}"
    session_data = response.json()

    # Query DB to get the generated qr_code_hash
    db = TestingSessionLocal()
    session = db.query(QRAttendanceSession).filter(
        QRAttendanceSession.session_id == session_data["session_id"]
    ).first()
    qr_hash = session.qr_code_hash
    session_id = session.session_id
    db.close()

    return {"session_id": session_id, "qr_code_hash": qr_hash}


# -------------------------------------------------------------------------
# Test 1: Missing verification hash is rejected
# -------------------------------------------------------------------------
def test_missing_verification_hash_is_rejected(student1_headers, active_qr_session):
    payload = {
        "session_id": active_qr_session["session_id"],
        # qr_code_hash omitted
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 5.0,
        },
    }
    response = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert response.status_code in (200, 400, 422)
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is False
        assert data["attendance_marked"] is False
        assert data["validation_results"]["qr_valid"] is False
        assert any("hash" in str(err).lower() for err in (data.get("errors") or []))

    # Verify no attendance record was persisted
    db = TestingSessionLocal()
    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.student_id == "1"
    ).all()
    assert len(records) == 0
    db.close()


# -------------------------------------------------------------------------
# Test 2: Empty or whitespace verification hash is rejected
# -------------------------------------------------------------------------
@pytest.mark.parametrize("empty_hash", ["", "   ", "\t", "\n  \t "])
def test_empty_or_whitespace_hash_is_rejected(student1_headers, active_qr_session, empty_hash):
    payload = {
        "session_id": active_qr_session["session_id"],
        "qr_code_hash": empty_hash,
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 5.0,
        },
    }
    response = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert response.status_code in (200, 400, 422)
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is False
        assert data["attendance_marked"] is False
        assert data["validation_results"]["qr_valid"] is False

    db = TestingSessionLocal()
    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.student_id == "1"
    ).all()
    assert len(records) == 0
    db.close()


# -------------------------------------------------------------------------
# Test 3: Placeholder values (hash_placeholder, manual_entry, demo_scan) rejected
# -------------------------------------------------------------------------
@pytest.mark.parametrize(
    "placeholder",
    [
        "hash_placeholder",
        "manual_entry",
        "demo_scan",
        "HASH_PLACEHOLDER",
        "Manual_Entry",
        "DEMO_SCAN",
        " manual_entry ",
    ],
)
def test_placeholder_hashes_are_rejected(student1_headers, active_qr_session, placeholder):
    payload = {
        "session_id": active_qr_session["session_id"],
        "qr_code_hash": placeholder,
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 5.0,
        },
    }
    response = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert response.status_code in (200, 400, 422)
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is False
        assert data["attendance_marked"] is False
        assert data["validation_results"]["qr_valid"] is False
        assert any(
            "placeholder" in str(err).lower() or "security" in str(err).lower()
            for err in (data.get("errors") or [])
        )

    db = TestingSessionLocal()
    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.student_id == "1"
    ).all()
    assert len(records) == 0
    db.close()


# -------------------------------------------------------------------------
# Test 4: Tampered or mismatched verification hash is rejected
# -------------------------------------------------------------------------
def test_tampered_or_mismatched_hash_is_rejected(student1_headers, active_qr_session):
    tampered_hash = "a" * 64  # valid SHA-256 length string, but wrong hash
    payload = {
        "session_id": active_qr_session["session_id"],
        "qr_code_hash": tampered_hash,
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 5.0,
        },
    }
    response = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["attendance_marked"] is False
    assert data["validation_results"]["qr_valid"] is False
    assert any("mismatch" in str(err).lower() for err in (data.get("errors") or []))

    db = TestingSessionLocal()
    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.student_id == "1"
    ).all()
    assert len(records) == 0
    db.close()


# -------------------------------------------------------------------------
# Test 5: Expired QR session is rejected
# -------------------------------------------------------------------------
def test_expired_qr_session_is_rejected(faculty_headers, student1_headers):
    # Create an expired session
    db = TestingSessionLocal()
    now = datetime.utcnow()
    past = now - timedelta(minutes=15)
    expired_session = QRAttendanceSession(
        session_id="expired-session-12345",
        faculty_id="10",
        faculty_name="Prof. Sharma",
        subject_code="CS302",
        subject_name="Algorithms",
        branch="Computer Science",
        semester="4",
        lecture_date=past,
        lecture_start_time=past,
        lecture_end_time=past + timedelta(minutes=60),
        qr_code_data="{}",
        qr_code_hash="genuine_hash_for_expired_session_12345",
        qr_generated_at=past,
        qr_expires_at=past + timedelta(minutes=5),  # expired 10 minutes ago
        qr_validity_minutes=5,
        center_latitude=26.2738,
        center_longitude=73.0366,
        geo_fence_radius_meters=50.0,
        is_active=False,
        is_expired=True,
    )
    db.add(expired_session)
    db.commit()
    db.refresh(expired_session)
    expired_session_db_id = expired_session.id
    db.close()

    payload = {
        "session_id": "expired-session-12345",
        "qr_code_hash": "genuine_hash_for_expired_session_12345",
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 5.0,
        },
    }
    response = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["attendance_marked"] is False
    assert any("expired" in str(err).lower() for err in (data.get("errors") or []))

    db = TestingSessionLocal()
    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.session_id == expired_session_db_id
    ).all()
    assert len(records) == 0
    db.close()


# -------------------------------------------------------------------------
# Test 6: Valid QR attendance succeeds for authorized student within geofence
# -------------------------------------------------------------------------
def test_valid_qr_attendance_succeeds(student1_headers, active_qr_session):
    payload = {
        "session_id": active_qr_session["session_id"],
        "qr_code_hash": active_qr_session["qr_code_hash"],
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 10.0,
        },
    }
    response = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["attendance_marked"] is True
    assert data["validation_results"]["qr_valid"] is True
    assert data["validation_results"]["location_valid"] is True

    # Verify record in database
    db = TestingSessionLocal()
    session = db.query(QRAttendanceSession).filter(
        QRAttendanceSession.session_id == active_qr_session["session_id"]
    ).first()
    record = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.session_id == session.id,
        QRAttendanceRecord.student_id == "1",
    ).first()
    assert record is not None
    assert record.roll_number == "2024CS001"
    assert record.attendance_status in ("present", "late")
    db.close()


# -------------------------------------------------------------------------
# Test 7: Student cannot mark attendance for another student
# -------------------------------------------------------------------------
def test_student_cannot_mark_attendance_for_another_student(
    student1_headers, active_qr_session
):
    # Student 1 attempts to submit Student 2's roll number and student ID
    payload = {
        "session_id": active_qr_session["session_id"],
        "qr_code_hash": active_qr_session["qr_code_hash"],
        "student_id": "2",
        "roll_number": "2024CS002",
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 5.0,
        },
    }
    response = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert response.status_code == 403
    assert "identity mismatch" in response.text.lower() or "cannot mark attendance" in response.text.lower()

    # Ensure Student 2 was NOT marked present
    db = TestingSessionLocal()
    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.roll_number == "2024CS002"
    ).all()
    assert len(records) == 0
    db.close()


# -------------------------------------------------------------------------
# Test 8: Unauthorized user cannot create a QR session
# -------------------------------------------------------------------------
def test_unauthorized_user_cannot_create_qr_session(student1_headers):
    payload = {
        "subject_code": "CS401",
        "subject_name": "Distributed Systems",
        "branch": "Computer Science",
        "semester": "6",
        "lecture_date": datetime.utcnow().isoformat(),
        "lecture_start_time": datetime.utcnow().isoformat(),
        "lecture_duration_minutes": 60,
        "center_latitude": 26.2738,
        "center_longitude": 73.0366,
        "geo_fence_radius_meters": 50.0,
    }
    # Unauthenticated call
    unauth_resp = client.post("/qr-attendance/faculty/generate-qr", json=payload)
    assert unauth_resp.status_code == 401

    # Student attempting to create session
    forbidden_resp = client.post(
        "/qr-attendance/faculty/generate-qr",
        json=payload,
        headers=student1_headers,
    )
    assert forbidden_resp.status_code == 403


# -------------------------------------------------------------------------
# Test 9: Duplicate attendance submissions are rejected / flagged
# -------------------------------------------------------------------------
def test_duplicate_attendance_submission_rejected(student1_headers, active_qr_session):
    payload = {
        "session_id": active_qr_session["session_id"],
        "qr_code_hash": active_qr_session["qr_code_hash"],
        "location": {
            "latitude": 26.2738,
            "longitude": 73.0366,
            "accuracy": 10.0,
        },
    }
    # First attendance scan must succeed
    resp1 = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True
    assert resp1.json()["attendance_marked"] is True

    # Immediate second attendance scan for the same session must be rejected
    resp2 = client.post(
        "/qr-attendance/student/scan-qr",
        json=payload,
        headers=student1_headers,
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["success"] is False
    assert data["attendance_marked"] is False
    assert any(
        "already marked" in str(msg).lower() or "duplicate" in str(msg).lower()
        for msg in [data.get("message")] + (data.get("errors") or [])
    )

    # Verify still exactly 1 record in database
    db = TestingSessionLocal()
    session = db.query(QRAttendanceSession).filter(
        QRAttendanceSession.session_id == active_qr_session["session_id"]
    ).first()
    count = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.session_id == session.id,
        QRAttendanceRecord.student_id == "1",
    ).count()
    assert count == 1
    db.close()


# -------------------------------------------------------------------------
# Test 10: Legitimate manual attendance by authorized staff continues to work
# -------------------------------------------------------------------------
def test_legitimate_manual_attendance_by_staff(staff_headers, student2_headers):
    # Legitimate staff marks attendance via POST /attendance/
    now = datetime.utcnow()
    payload = {
        "student_id": 2,
        "subject_code": "CS301",
        "date": now.isoformat(),
        "status": "Present",
        "session_name": "Manual Lecture Roll Call",
        "remarks": "Marked by authorized staff in office",
    }
    response = client.post("/attendance/", json=payload, headers=staff_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == 2
    assert data["status"] == "Present"

    # Students cannot call manual staff endpoint
    student_resp = client.post("/attendance/", json=payload, headers=student2_headers)
    assert student_resp.status_code == 403

    # Verify manual record in database
    db = TestingSessionLocal()
    rec = db.query(Attendance).filter(
        Attendance.student_id == 2,
        Attendance.subject_code == "CS301",
    ).first()
    assert rec is not None
    assert rec.status == "Present"
    db.close()
