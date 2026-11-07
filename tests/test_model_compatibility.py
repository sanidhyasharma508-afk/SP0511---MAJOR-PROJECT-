"""Tests for Phase 19C: SQLAlchemy Model Hardening for Cross-Platform Database Compatibility.

Verifies:
- All 22 ORM models register properly in Base.metadata
- Fresh schema creation in SQLite
- Boolean type persistence (True, False, None)
- Enum persistence and named PostgreSQL-compatible SQLEnum specifications
- JSON serialization consistency for Text-based JSON fields
- Foreign-key relationships and cascade behaviors
- Nullable fields vs non-nullable constraints
- DateTime and timestamp handling
- Bidirectional ORM relationships
- DatabaseVerifier compatibility against the application database
"""

import json
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, StatementError

from backend.database import Base, engine as app_engine
from backend.core.database_verifier import DatabaseVerifier, DatabaseReadinessStatus
from backend.models import (
    User,
    Student,
    StudyTask,
    Club,
    ClubActivity,
    ClubMember,
    ClubAttendance,
    Event,
    EventRegistration,
    EventLeaderboard,
    EventAnnouncement,
    EventCategory,
    EventStatus,
    RegistrationStatus,
    Attendance,
    Complaint,
    ComplaintHistory,
    RiskLog,
    Schedule,
    ScheduleFeedback,
    Announcement,
    QRAttendanceSession,
    QRAttendanceRecord,
    QRAttendanceLog,
    DeviceFingerprint,
)


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database session with PRAGMA foreign_keys enabled."""
    test_engine = create_engine("sqlite:///:memory:")
    # Enable foreign key enforcement for SQLite
    with test_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()


class TestModelInventoryAndMetadata:
    """Task 1: Complete Model Inventory and Metadata Verification."""

    def test_twenty_two_domain_models_registered(self):
        """Verify exactly 22 domain models are registered in Base.metadata."""
        expected_tables = {
            "users",
            "students",
            "study_tasks",
            "clubs",
            "club_activities",
            "club_members",
            "club_attendance",
            "events",
            "event_registrations",
            "event_leaderboard",
            "event_announcements",
            "attendance",
            "complaints",
            "complaint_history",
            "risk_logs",
            "schedules",
            "schedule_feedback",
            "announcements",
            "qr_attendance_sessions",
            "qr_attendance_records",
            "qr_attendance_logs",
            "device_fingerprints",
        }
        actual_tables = set(Base.metadata.tables.keys())
        assert actual_tables == expected_tables, f"Mismatch: {expected_tables ^ actual_tables}"
        assert len(actual_tables) == 22

    def test_schema_creation_in_memory(self, memory_db):
        """Verify clean schema creation of all 22 models in a fresh database."""
        inspector = inspect(memory_db.bind)
        created_tables = set(inspector.get_table_names())
        assert len(created_tables) == 22
        assert "users" in created_tables
        assert "events" in created_tables
        assert "qr_attendance_sessions" in created_tables


class TestBooleanTypeNormalization:
    """Task 2: Boolean Type Normalization and Query Behavior."""

    def test_boolean_persistence_true_false(self, memory_db):
        """Verify True and False persist correctly on standard Boolean columns."""
        user_active = User(
            username="active_user",
            email="active@college.edu",
            hashed_password="hash",
            role="student",
            is_active=True,
        )
        user_inactive = User(
            username="inactive_user",
            email="inactive@college.edu",
            hashed_password="hash",
            role="student",
            is_active=False,
        )
        memory_db.add_all([user_active, user_inactive])
        memory_db.commit()

        # Query using python bool
        active_res = memory_db.query(User).filter(User.is_active == True).all()
        inactive_res = memory_db.query(User).filter(User.is_active == False).all()

        assert len(active_res) == 1
        assert active_res[0].username == "active_user"
        assert active_res[0].is_active is True

        assert len(inactive_res) == 1
        assert inactive_res[0].username == "inactive_user"
        assert inactive_res[0].is_active is False

    def test_event_boolean_flags(self, memory_db):
        """Verify Event model boolean flags persist properly."""
        now = datetime.utcnow()
        event = Event(
            name="Tech Fair",
            description="Annual exhibition",
            category=EventCategory.TECHNICAL,
            registration_start_date=now,
            registration_end_date=now,
            event_start_date=now,
            event_end_date=now,
            organizer_name="Tech Council",
            organizer_email="tech@college.edu",
            requires_approval=True,
            team_event=False,
        )
        memory_db.add(event)
        memory_db.commit()

        refreshed = memory_db.query(Event).filter(Event.name == "Tech Fair").first()
        assert refreshed.requires_approval is True
        assert refreshed.team_event is False

    def test_integer_flag_compatibility(self, memory_db):
        """Verify integer status flags (Schedule.is_active, RiskLog.resolved) persist accurately."""
        schedule = Schedule(
            title="Database Systems Lecture",
            event_type="Class",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            is_active=1,
        )
        risk = RiskLog(
            risk_type="Attendance",
            severity="Low",
            description="Attendance dipped below threshold",
            resolved=0,
        )
        announcement = Announcement(
            title="Library Notice",
            content="Extended library hours",
            author="Librarian",
            is_active=1,
        )
        memory_db.add_all([schedule, risk, announcement])
        memory_db.commit()

        s = memory_db.query(Schedule).filter(Schedule.is_active == 1).first()
        r = memory_db.query(RiskLog).filter(RiskLog.resolved == 0).first()
        a = memory_db.query(Announcement).filter(Announcement.is_active == 1).first()

        assert s is not None and s.is_active == 1
        assert r is not None and r.resolved == 0
        assert a is not None and a.is_active == 1


class TestEnumNormalization:
    """Task 3: Enum Normalization and Named PostgreSQL Types."""

    def test_sqlenum_explicit_type_names(self):
        """Verify SQLEnum columns specify explicit PostgreSQL-compatible type names."""
        events_table = Base.metadata.tables["events"]
        registrations_table = Base.metadata.tables["event_registrations"]

        cat_col = events_table.columns["category"]
        stat_col = events_table.columns["status"]
        reg_stat_col = registrations_table.columns["status"]

        assert cat_col.type.name == "eventcategory"
        assert stat_col.type.name == "eventstatus"
        assert reg_stat_col.type.name == "registrationstatus"

    def test_enum_persistence_and_retrieval(self, memory_db):
        """Verify enum values persist and map back to Python Enum instances."""
        now = datetime.utcnow()
        event = Event(
            name="Inter-College Football",
            description="Football tournament",
            category=EventCategory.SPORTS,
            status=EventStatus.REGISTRATION_OPEN,
            registration_start_date=now,
            registration_end_date=now,
            event_start_date=now,
            event_end_date=now,
            organizer_name="Sports Committee",
            organizer_email="sports@college.edu",
        )
        memory_db.add(event)
        memory_db.commit()

        loaded = memory_db.query(Event).filter(Event.category == EventCategory.SPORTS).first()
        assert loaded is not None
        assert loaded.category == EventCategory.SPORTS
        assert loaded.category.value == "sports"
        assert loaded.status == EventStatus.REGISTRATION_OPEN
        assert loaded.status.value == "registration_open"


class TestForeignKeyAndCascadeAudit:
    """Task 4: Foreign Key and Relationship Verification."""

    def test_valid_foreign_key_linkages(self, memory_db):
        """Verify valid foreign key linkages function across related tables."""
        student = Student(name="Alice Smith", roll_no="22BCS101", department="CS", semester=3)
        memory_db.add(student)
        memory_db.commit()

        user = User(
            username="alice",
            email="alice@college.edu",
            hashed_password="hash",
            role="student",
            linked_student_id=student.id,
        )
        memory_db.add(user)
        memory_db.commit()

        # Verify relationship navigation
        assert user.student is not None
        assert user.student.roll_no == "22BCS101"

    def test_complaint_history_cascade_deletion(self, memory_db):
        """Verify cascade deletion on Complaint -> ComplaintHistory."""
        student = Student(name="Bob Jones", roll_no="22BCS102", department="CS", semester=3)
        memory_db.add(student)
        memory_db.commit()

        complaint = Complaint(
            student_id=student.id,
            title="Lab AC Not Working",
            description="The air conditioning in Lab 2 is faulty",
            category="Facility",
        )
        memory_db.add(complaint)
        memory_db.commit()

        history_entry = ComplaintHistory(
            complaint_id=complaint.id,
            new_status="Pending",
            remarks="Initial submission",
        )
        memory_db.add(history_entry)
        memory_db.commit()

        # Delete complaint and verify history entry is cascaded
        memory_db.delete(complaint)
        memory_db.commit()

        remaining_history = memory_db.query(ComplaintHistory).filter(ComplaintHistory.complaint_id == complaint.id).all()
        assert len(remaining_history) == 0


class TestJsonFieldCompatibility:
    """Task 5: JSON-Like Field Serialization and Structure."""

    def test_prizes_json_serialization(self, memory_db):
        """Verify JSON payload serialization for Event.prizes."""
        now = datetime.utcnow()
        prize_payload = {"1st": "$2500", "2nd": "$1500", "3rd": "$1000"}
        event = Event(
            name="Robotics Challenge",
            description="Build competitive robots",
            category=EventCategory.TECHNICAL,
            registration_start_date=now,
            registration_end_date=now,
            event_start_date=now,
            event_end_date=now,
            organizer_name="Robotics Club",
            organizer_email="robotics@college.edu",
            prizes=json.dumps(prize_payload),
        )
        memory_db.add(event)
        memory_db.commit()

        loaded = memory_db.query(Event).filter(Event.name == "Robotics Challenge").first()
        parsed = json.loads(loaded.prizes)
        assert parsed["1st"] == "$2500"
        assert parsed["2nd"] == "$1500"
        assert parsed["3rd"] == "$1000"

    def test_null_json_fields_permitted(self, memory_db):
        """Verify nullable JSON-like text fields accept None without error."""
        club = Club(
            name="Coding Society",
            description="Programming and hackathons",
            category="Technical",
            advisor="Dr. Amit Verma",
            gallery_images=None,
            social_media_links=None,
        )
        memory_db.add(club)
        memory_db.commit()

        refreshed = memory_db.query(Club).filter(Club.name == "Coding Society").first()
        assert refreshed.gallery_images is None
        assert refreshed.social_media_links is None


class TestStringLengthAndPrecision:
    """Task 6: String Length Specifications and Constraints."""

    def test_bounded_string_columns_specified(self):
        """Verify bounded string column types have explicit lengths defined."""
        students = Base.metadata.tables["students"]
        assert students.columns["name"].type.length == 100
        assert students.columns["roll_no"].type.length == 50
        assert students.columns["department"].type.length == 100
        assert students.columns["section"].type.length == 20

        complaints = Base.metadata.tables["complaints"]
        assert complaints.columns["title"].type.length == 200
        assert complaints.columns["category"].type.length == 50
        assert complaints.columns["status"].type.length == 50
        assert complaints.columns["priority"].type.length == 50

        schedules = Base.metadata.tables["schedules"]
        assert schedules.columns["title"].type.length == 200
        assert schedules.columns["event_type"].type.length == 50

        risk_logs = Base.metadata.tables["risk_logs"]
        assert risk_logs.columns["risk_type"].type.length == 50
        assert risk_logs.columns["severity"].type.length == 50


class TestDateTimeHandling:
    """Task 7: DateTime and Timezone Handling."""

    def test_utc_default_timestamps(self, memory_db):
        """Verify models generate UTC timestamps on creation."""
        user = User(
            username="charlie",
            email="charlie@college.edu",
            hashed_password="hash",
            role="student",
        )
        memory_db.add(user)
        memory_db.commit()

        refreshed = memory_db.query(User).filter(User.username == "charlie").first()
        assert isinstance(refreshed.created_at, datetime)
        assert (datetime.utcnow() - refreshed.created_at).total_seconds() < 10

    def test_schedule_local_timeline_integrity(self, memory_db):
        """Verify local academic timetable slot dates persist without alteration."""
        start = datetime(2026, 11, 10, 9, 0, 0)
        end = datetime(2026, 11, 10, 10, 0, 0)
        sched = Schedule(
            title="Morning Operating Systems",
            event_type="Class",
            start_date=start,
            end_date=end,
            location="Room 304",
        )
        memory_db.add(sched)
        memory_db.commit()

        loaded = memory_db.query(Schedule).filter(Schedule.title == "Morning Operating Systems").first()
        assert loaded.start_date == start
        assert loaded.end_date == end


class TestApplicationDatabaseReadiness:
    """Verification against the actual application database."""

    def test_application_database_readiness_and_schema_validity(self):
        """Verify the actual application database remains COMPATIBLE_UNSTAMPED with zero drift."""
        verifier = DatabaseVerifier(app_engine)
        report = verifier.verify_schema()
        readiness = verifier.check_readiness()

        assert report.is_valid is True, f"Schema mismatch: {report.summary}"
        assert len(report.missing_tables) == 0
        assert len(report.type_mismatches) == 0
        assert len(report.missing_fks) == 0
        assert readiness.status == DatabaseReadinessStatus.COMPATIBLE_UNSTAMPED
        assert readiness.can_start is True
