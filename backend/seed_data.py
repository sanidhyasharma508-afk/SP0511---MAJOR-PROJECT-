"""
Comprehensive Database Seeder for Campus Automation System
Seeds students, clubs, events, schedules, attendance, announcements,
complaints, risk logs, and QR attendance sessions.
"""

import sys
from pathlib import Path

# Ensure repository root is on sys.path when executed directly as a script
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from datetime import datetime, timedelta
import json
import uuid
import hashlib
from sqlalchemy.orm import Session

from backend.database import SessionLocal, engine, Base
from backend.models.user import User
from backend.models.student import Student
from backend.models.study_task import StudyTask
from backend.models.club import Club, ClubActivity, ClubMember, ClubAttendance
from backend.models.events import Event, EventCategory, EventStatus
from backend.models.schedule import Schedule
from backend.models.schedule_feedback import ScheduleFeedback, Announcement
from backend.models.attendance import Attendance
from backend.models.complaint import Complaint
from backend.models.risk import RiskLog
from backend.models.qr_attendance import QRAttendanceSession, QRAttendanceRecord


def ensure_schema():
    """Ensure all required columns and tables exist in SQLite database"""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(students)")).fetchall()
            cols = [r[1] for r in result]
            if "section" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE students ADD COLUMN section VARCHAR DEFAULT '_'"))
                conn.commit()
                print("[MIGRATION] Added missing 'section' column to students table.")
        except Exception as e:
            print(f"[MIGRATION WARNING students] {e}")

        try:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            cols = [r[1] for r in result]
            if "avatar" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar TEXT"))
                conn.commit()
                print("[MIGRATION] Added missing 'avatar' column to users table.")
        except Exception as e:
            print(f"[MIGRATION WARNING users] {e}")

        try:
            from sqlalchemy import text
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_qr_attendance_session_roll ON qr_attendance_records (session_id, roll_number)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_qr_attendance_session_student ON qr_attendance_records (session_id, student_id)"))
            conn.commit()
            print("[MIGRATION] Verified unique indexes on qr_attendance_records.")
        except Exception as e:
            print(f"[MIGRATION WARNING qr_attendance_records] {e}")

        # Clubs table migration
        try:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(clubs)")).fetchall()
            cols = [r[1] for r in result]
            if "created_by" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE clubs ADD COLUMN created_by INTEGER"))
                conn.commit()
                print("[MIGRATION] Added 'created_by' column to clubs table.")
        except Exception as e:
            print(f"[MIGRATION WARNING clubs] {e}")

        # Club members unique index migration
        try:
            from sqlalchemy import text
            conn.execute(text("DELETE FROM club_members WHERE id NOT IN (SELECT MIN(id) FROM club_members GROUP BY club_id, student_id)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_club_member_club_student ON club_members (club_id, student_id)"))
            conn.commit()
            print("[MIGRATION] Verified unique index on club_members (club_id, student_id).")
        except Exception as e:
            print(f"[MIGRATION WARNING club_members] {e}")

        # Event registrations unique index migration
        try:
            from sqlalchemy import text
            conn.execute(text("DELETE FROM event_registrations WHERE id NOT IN (SELECT MIN(id) FROM event_registrations GROUP BY event_id, student_id)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_event_reg_event_student ON event_registrations (event_id, student_id)"))
            conn.commit()
            print("[MIGRATION] Verified unique index on event_registrations (event_id, student_id).")
        except Exception as e:
            print(f"[MIGRATION WARNING event_registrations] {e}")

        # Complaints table migration
        try:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(complaints)")).fetchall()
            cols = [r[1] for r in result]
            if "resolution_notes" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN resolution_notes TEXT"))
            if "assigned_to" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN assigned_to INTEGER"))
            conn.commit()
            print("[MIGRATION] Verified resolution_notes and assigned_to columns in complaints table.")
        except Exception as e:
            print(f"[MIGRATION WARNING complaints] {e}")

        # Attendance table migration
        try:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(attendance)")).fetchall()
            cols = [r[1] for r in result]
            if "subject_code" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE attendance ADD COLUMN subject_code VARCHAR(50)"))
            if "faculty_id" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE attendance ADD COLUMN faculty_id VARCHAR(50)"))
            if "session_name" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE attendance ADD COLUMN session_name VARCHAR(100)"))
            conn.commit()
            print("[MIGRATION] Verified subject_code, faculty_id, session_name columns in attendance table.")
        except Exception as e:
            print(f"[MIGRATION WARNING attendance] {e}")


def seed_default_users(db: Session):
    """
    Seed initial development accounts only if running in development or testing.
    Disabled in production.
    Never overwrites existing accounts.
    """
    from backend.core.config import settings
    if settings.is_production:
        print("[AUTH NOTICE] Production mode detected. Automatic user seeding skipped.")
        return

    from backend.core.auth import hash_password
    from backend.models.user import User

    if db.query(User).count() == 0:
        print("[SEED] Provisioning initial development/testing accounts...")
        alex = db.query(Student).filter(Student.roll_no == "21BCS101").first()
        if not alex:
            alex = Student(
                name="Alex Johnson",
                roll_no="21BCS101",
                department="Computer Science Engineering",
                semester=4,
                section="A",
            )
            db.add(alex)
            db.commit()
            db.refresh(alex)
        dev_users = [
            User(
                username="admin",
                email="admin@campus.edu",
                hashed_password=hash_password("admin123"),
                full_name="Administrator",
                role="admin",
                is_active=True,
            ),
            User(
                username="staff1",
                email="staff1@campus.edu",
                hashed_password=hash_password("staff123"),
                full_name="Staff Member",
                role="staff",
                is_active=True,
            ),
            User(
                username="student1",
                email="student1@campus.edu",
                hashed_password=hash_password("student123"),
                full_name="Alex Johnson",
                role="student",
                linked_student_id=alex.id if alex else None,
                is_active=True,
            ),
            User(
                username="staff2",
                email="staff2@campus.edu",
                hashed_password=hash_password("staff123"),
                full_name="Second Faculty Member",
                role="staff",
                is_active=True,
            ),
        ]
        for u in dev_users:
            db.add(u)
        db.commit()
        print("[SUCCESS] Development accounts provisioned (admin, staff1, student1).")
    else:
        print("[INFO] User accounts already present in database.")


def seed_database():
    """Seed the database with rich campus data (Development only)"""
    from backend.core.config import settings
    if settings.is_production:
        print("[SEED NOTICE] Production mode detected. Automatic database seeding skipped.")
        return

    ensure_schema()
    db: Session = SessionLocal()

    try:
        # Check if already seeded
        if db.query(Student).filter(Student.roll_no == "21BCS101").first():
            print("[INFO] Database already contains student 21BCS101. Checking missing entities...")
        else:
            print("[SEED] Seeding students...")
            students = [
                Student(name="Alex Johnson", roll_no="21BCS101", department="Computer Science Engineering", semester=4, section="A"),
                Student(name="Riya Mehta", roll_no="21BCS102", department="Computer Science Engineering", semester=4, section="A"),
                Student(name="Vikram Singh", roll_no="21BCS103", department="Computer Science Engineering", semester=4, section="B"),
                Student(name="Meera Patel", roll_no="21BCS104", department="Electronics & Communication", semester=4, section="B"),
                Student(name="Sahil Verma", roll_no="21BCS105", department="Mechanical Engineering", semester=4, section="C"),
                Student(name="Priya Sharma", roll_no="21BCS106", department="Civil Engineering", semester=4, section="A"),
            ]
            for s in students:
                existing = db.query(Student).filter(Student.roll_no == s.roll_no).first()
                if not existing:
                    db.add(s)
            db.commit()

        # Seed Clubs
        if db.query(Club).count() == 0:
            print("[SEED] Seeding clubs...")
            clubs = [
                Club(
                    name="Coding Club",
                    description="Learn and master programming languages, algorithms, and open source with expert mentors.",
                    detailed_description="MBM University premier coding society. We host weekly algorithmic problem-solving sessions, open source contribution sprints, and full-stack project building.",
                    category="tech",
                    advisor="Dr. Amit Verma",
                    advisor_email="amit.verma@mbm.edu",
                    president="Alex Johnson",
                    president_email="alex@student.mbm.edu",
                    contact_email="codingclub@mbm.edu",
                    member_count=234,
                    total_events=12,
                    founding_year=2018,
                    is_active=True,
                    accepting_members=True
                ),
                Club(
                    name="Robotics Society",
                    description="Build, design, and compete with state-of-the-art robots and IoT hardware.",
                    detailed_description="From micro-controllers and ROS to heavy combat robotics, we train students on embedded electronics, CAD, and 3D prototyping.",
                    category="tech",
                    advisor="Dr. Neha Gupta",
                    advisor_email="neha.gupta@mbm.edu",
                    president="Rohan Das",
                    president_email="rohan@student.mbm.edu",
                    contact_email="robotics@mbm.edu",
                    member_count=156,
                    total_events=8,
                    founding_year=2019,
                    is_active=True,
                    accepting_members=True
                ),
                Club(
                    name="Music Club (Sargam)",
                    description="Express yourself through music, jam sessions, and performances on university stages.",
                    detailed_description="Sargam brings together classical vocalists, instrumentalists, and western bands for live concerts, acoustic jam sessions, and studio recordings.",
                    category="arts",
                    advisor="Prof. Rajesh Sen",
                    advisor_email="rajesh.sen@mbm.edu",
                    president="Ananya Roy",
                    president_email="ananya@student.mbm.edu",
                    contact_email="sargam@mbm.edu",
                    member_count=189,
                    total_events=15,
                    founding_year=2015,
                    is_active=True,
                    accepting_members=True
                ),
                Club(
                    name="Dance Club (Zenith)",
                    description="Energetic choreography team performing across university competitions and fests.",
                    detailed_description="Zenith specializes in hip-hop, classical fusion, contemporary, and Bollywood dance styles, competing at national inter-college fests.",
                    category="arts",
                    advisor="Dr. Sunita Rao",
                    advisor_email="sunita.rao@mbm.edu",
                    president="Varun Nair",
                    president_email="varun@student.mbm.edu",
                    contact_email="zenith@mbm.edu",
                    member_count=98,
                    total_events=6,
                    founding_year=2017,
                    is_active=True,
                    accepting_members=True
                ),
                Club(
                    name="Sports Federation",
                    description="Cricket, Football, Badminton, Athletics training and inter-college tournaments.",
                    detailed_description="The central sports body organizing annual intramural leagues, athletic championships, and varsity team training.",
                    category="sports",
                    advisor="Coach Ramesh Singh",
                    advisor_email="sports@mbm.edu",
                    president="Kabir Gill",
                    president_email="kabir@student.mbm.edu",
                    contact_email="sports@mbm.edu",
                    member_count=310,
                    total_events=20,
                    founding_year=2012,
                    is_active=True,
                    accepting_members=True
                ),
                Club(
                    name="Arts & Culture (Kalakriti)",
                    description="Fine arts, painting, sketching, design and cultural exhibitions.",
                    detailed_description="Kalakriti fosters creativity through canvas workshops, digital art bootcamps, and live gallery installations.",
                    category="arts",
                    advisor="Prof. Maya Joshi",
                    advisor_email="maya.joshi@mbm.edu",
                    president="Simran Kaur",
                    president_email="simran@student.mbm.edu",
                    contact_email="kalakriti@mbm.edu",
                    member_count=142,
                    total_events=10,
                    founding_year=2016,
                    is_active=True,
                    accepting_members=True
                ),
                Club(
                    name="Social Service League",
                    description="Community outreach, blood donation drives, and environmental sustainability initiatives.",
                    detailed_description="Dedicated to social impact through rural school tutoring, tree plantations, blood donation camps, and disaster relief.",
                    category="social",
                    advisor="Dr. K. K. Sharma",
                    advisor_email="kk.sharma@mbm.edu",
                    president="Aman Jain",
                    president_email="aman@student.mbm.edu",
                    contact_email="socialservice@mbm.edu",
                    member_count=215,
                    total_events=14,
                    founding_year=2014,
                    is_active=True,
                    accepting_members=True
                ),
            ]
            for c in clubs:
                db.add(c)
            db.commit()

        # Seed Club Members & Activities
        if db.query(ClubMember).count() == 0:
            print("[SEED] Seeding club members and activities...")
            first_club = db.query(Club).filter(Club.name == "Coding Club").first()
            alex = db.query(Student).filter(Student.roll_no == "21BCS101").first()
            if first_club and alex:
                db.add(ClubMember(club_id=first_club.id, student_id=alex.id, position="Lead Developer", is_active=True))
                db.add(ClubActivity(
                    club_id=first_club.id,
                    title="Hacktoberfest Open Source Meet",
                    description="Hands-on git workshop and contribution sprint",
                    activity_type="Workshop",
                    start_date=datetime.utcnow() + timedelta(days=2),
                    location="Lab 304",
                    expected_participants=50,
                    status="Planned"
                ))
                db.commit()

        # Seed Events
        if db.query(Event).count() == 0:
            print("[SEED] Seeding events...")
            now = datetime.utcnow()
            events = [
                Event(
                    name="Annual Hackathon 2026",
                    description="24-hour non-stop hackathon with themes in AI, Web3, and Smart Campus Automation. Prizes worth $5000!",
                    category=EventCategory.TECHNICAL,
                    organizer_name="Coding Club",
                    organizer_email="codingclub@mbm.edu",
                    venue="University Auditorium",
                    event_start_date=now + timedelta(days=5),
                    event_end_date=now + timedelta(days=6),
                    registration_start_date=now - timedelta(days=10),
                    registration_end_date=now + timedelta(days=4),
                    max_participants=200,
                    current_participants=84,
                    entry_fee=0.0,
                    status=EventStatus.REGISTRATION_OPEN,
                    prizes=json.dumps({"1st": "$2500", "2nd": "$1500", "3rd": "$1000"})
                ),
                Event(
                    name="Bot Wars: Combat Robotics",
                    description="Design, build, and combat with 15kg combat bots. Beginner workshops included.",
                    category=EventCategory.TECHNICAL,
                    organizer_name="Robotics Society",
                    organizer_email="robotics@mbm.edu",
                    venue="Mechanical Workshop Arena",
                    event_start_date=now + timedelta(days=12),
                    event_end_date=now + timedelta(days=13),
                    registration_start_date=now - timedelta(days=5),
                    registration_end_date=now + timedelta(days=10),
                    max_participants=60,
                    current_participants=32,
                    entry_fee=50.0,
                    status=EventStatus.REGISTRATION_OPEN
                ),
                Event(
                    name="Open Mic & Music Night",
                    description="Showcase vocal, acoustic, and band performances under the stars.",
                    category=EventCategory.CULTURAL,
                    organizer_name="Music Club (Sargam)",
                    organizer_email="sargam@mbm.edu",
                    venue="Open Air Amphitheatre",
                    event_start_date=now + timedelta(days=8),
                    event_end_date=now + timedelta(days=8, hours=4),
                    registration_start_date=now - timedelta(days=2),
                    registration_end_date=now + timedelta(days=7),
                    max_participants=100,
                    current_participants=45,
                    entry_fee=0.0,
                    status=EventStatus.REGISTRATION_OPEN
                ),
                Event(
                    name="Inter-College Football Championship",
                    description="16 teams competing for the university football trophy.",
                    category=EventCategory.SPORTS,
                    organizer_name="Sports Federation",
                    organizer_email="sports@mbm.edu",
                    venue="Main Football Ground",
                    event_start_date=now + timedelta(days=15),
                    event_end_date=now + timedelta(days=18),
                    registration_start_date=now - timedelta(days=1),
                    registration_end_date=now + timedelta(days=12),
                    max_participants=256,
                    current_participants=112,
                    entry_fee=100.0,
                    status=EventStatus.REGISTRATION_OPEN
                )
            ]
            for ev in events:
                db.add(ev)
            db.commit()

        # Seed Schedules (Classes, Exams, Holidays)
        if db.query(Schedule).count() == 0:
            print("[SEED] Seeding schedules...")
            now = datetime.utcnow()
            schedules = [
                Schedule(
                    title="Computer Networks (CS-302)",
                    description="Room 304 • Main Block • Faculty: Dr. Sharma",
                    event_type="Class",
                    start_date=now,
                    end_date=now + timedelta(hours=1),
                    location="Room 304, Main Block",
                    audience="CS Sem 4",
                    is_active=1
                ),
                Schedule(
                    title="Database Systems (CS-303)",
                    description="Room 202 • Science Block • Faculty: Prof. Verma",
                    event_type="Class",
                    start_date=now + timedelta(hours=2),
                    end_date=now + timedelta(hours=3),
                    location="Room 202, Science Block",
                    audience="CS Sem 4",
                    is_active=1
                ),
                Schedule(
                    title="Software Engineering Lab (CS-304L)",
                    description="Lab 2 • IT Block • Hands-on testing & git",
                    event_type="Class",
                    start_date=now + timedelta(hours=4),
                    end_date=now + timedelta(hours=6),
                    location="Lab 2, IT Block",
                    audience="CS Sem 4",
                    is_active=1
                ),
                Schedule(
                    title="Mid-Term: CS-302 Computer Networks Exam",
                    description="Mid-semester examination. Hall ticket mandatory.",
                    event_type="Exam",
                    start_date=now + timedelta(days=7),
                    end_date=now + timedelta(days=7, hours=3),
                    location="Exam Hall A",
                    audience="CS Sem 4",
                    is_active=1
                ),
                Schedule(
                    title="Mid-Term: MA-301 Engineering Mathematics Exam",
                    description="Mid-semester examination.",
                    event_type="Exam",
                    start_date=now + timedelta(days=10),
                    end_date=now + timedelta(days=10, hours=3),
                    location="Exam Hall B",
                    audience="CS Sem 4",
                    is_active=1
                ),
                Schedule(
                    title="Dussehra Holiday",
                    description="University holiday on account of Dussehra/Vijayadashami",
                    event_type="Holiday",
                    start_date=now + timedelta(days=14),
                    end_date=now + timedelta(days=15),
                    location="Campus Closed",
                    audience="All Students",
                    is_active=1
                )
            ]
            for sc in schedules:
                db.add(sc)
            db.commit()

        # Seed Announcements
        if db.query(Announcement).count() == 0:
            print("[SEED] Seeding announcements...")
            announcements = [
                Announcement(
                    title="Lab Session Rescheduled",
                    content="The Data Structures lab scheduled for tomorrow morning has been shifted to Friday 2:00 PM due to system maintenance.",
                    author="Dr. Amit Verma",
                    priority="high",
                    target_audience="CS 4th Semester",
                    expires_at=datetime.utcnow() + timedelta(days=7),
                    is_active=1
                ),
                Announcement(
                    title="Mid-Term Examination Datesheet Released",
                    content="The mid-semester examination will commence from next Monday. Please download your hall tickets from the student portal.",
                    author="Controller of Examinations",
                    priority="high",
                    target_audience="All Students",
                    expires_at=datetime.utcnow() + timedelta(days=20),
                    is_active=1
                ),
                Announcement(
                    title="Library Hours Extended for Exams",
                    content="Central Library reading rooms will remain open until 11:00 PM during exam weeks.",
                    author="Chief Librarian",
                    priority="normal",
                    target_audience="All Students",
                    expires_at=datetime.utcnow() + timedelta(days=30),
                    is_active=1
                )
            ]
            for a in announcements:
                db.add(a)
            db.commit()

        # Seed Attendance for Alex Johnson (student_id = 1)
        alex = db.query(Student).filter(Student.roll_no == "21BCS101").first()
        if alex and db.query(Attendance).filter(Attendance.student_id == alex.id).count() == 0:
            print("[SEED] Seeding attendance records for student 1...")
            base_date = datetime.utcnow() - timedelta(days=30)
            records = []
            for day in range(30):
                d = base_date + timedelta(days=day)
                if d.weekday() < 5:  # Monday to Friday
                    # Alex has 85.5% attendance (~4 absents, 2 late out of ~25 days)
                    if day in [5, 12, 19]:
                        records.append(Attendance(student_id=alex.id, date=d, status="Absent", remarks="Medical leave"))
                    elif day in [8, 22]:
                        records.append(Attendance(student_id=alex.id, date=d, status="Late", remarks="Late by 10 mins"))
                    else:
                        records.append(Attendance(student_id=alex.id, date=d, status="Present", remarks="Regular"))

            for rec in records:
                db.add(rec)
            db.commit()

        # Seed Complaints
        if db.query(Complaint).count() == 0:
            print("[SEED] Seeding complaints...")
            complaints = [
                Complaint(
                    student_id=alex.id if alex else 1,
                    title="Hostel Wi-Fi Connectivity in Block C",
                    description="Wi-Fi connectivity drops frequently between 8 PM and 11 PM in Block C 2nd floor.",
                    category="Other",
                    priority="Normal",
                    status="In Review"
                ),
                Complaint(
                    student_id=alex.id if alex else 1,
                    title="Mess Dinner Timing Conflict with Evening Lab",
                    description="Evening practical lab ends at 7:30 PM, leaving less time for mess dinner service.",
                    category="Academic",
                    priority="High",
                    status="Pending"
                )
            ]
            for cmp in complaints:
                db.add(cmp)
            db.commit()

        # Seed Risk Logs
        if db.query(RiskLog).count() == 0:
            print("[SEED] Seeding risk logs...")
            risks = [
                RiskLog(
                    student_id=alex.id if alex else 1,
                    risk_type="Attendance",
                    severity="Low",
                    description="Attendance in Humanities (HU-101) dropped below 50%. Total classes: 20, Attended: 9.",
                    action_taken="Email notification sent to student advisor",
                    resolved=0
                ),
                RiskLog(
                    student_id=alex.id if alex else 1,
                    risk_type="Academic",
                    severity="Medium",
                    description="Mathematics (MA-301) attendance is 68%, below minimum 75% examination eligibility.",
                    action_taken="Advising session recommended",
                    resolved=0
                )
            ]
            for r in risks:
                db.add(r)
            db.commit()

        # Seed an Active QR Attendance Session
        if db.query(QRAttendanceSession).filter(QRAttendanceSession.is_active == True).count() == 0:
            print("[SEED] Seeding active QR attendance session...")
            session_id = str(uuid.uuid4())
            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=15)
            qr_data = {
                "session_id": session_id,
                "faculty_id": "faculty_001",
                "subject": "CS-302",
                "timestamp": now.isoformat(),
                "expires": expires_at.isoformat()
            }
            qr_code_data = json.dumps(qr_data)
            qr_hash = hashlib.sha256(f"{session_id}faculty_001{now.timestamp()}CS-302".encode()).hexdigest()

            qr_session = QRAttendanceSession(
                session_id=session_id,
                faculty_id="faculty_001",
                faculty_name="Dr. Sharma",
                faculty_email="sharma@faculty.mbm.edu",
                subject_code="CS-302",
                subject_name="Computer Networks",
                branch="CS",
                semester="4",
                section="A",
                lecture_date=now,
                lecture_start_time=now,
                lecture_end_time=now + timedelta(minutes=50),
                lecture_duration_minutes=50,
                qr_code_data=qr_code_data,
                qr_code_hash=qr_hash,
                qr_expires_at=expires_at,
                qr_validity_minutes=15,
                center_latitude=26.2738,
                center_longitude=73.0366,
                geo_fence_radius_meters=100,
                location_name="Room 304, Main Block",
                total_students_expected=60,
                allow_screenshot_scan=True,
                require_device_verification=False,
                is_active=True
            )
            db.add(qr_session)
            db.commit()

            # Add a marked record
            if alex:
                rec = QRAttendanceRecord(
                    session_id=qr_session.id,
                    student_id=str(alex.id),
                    roll_number=alex.roll_no,
                    student_name=alex.name,
                    student_email="alex@student.mbm.edu",
                    branch="CS",
                    semester="4",
                    section="A",
                    marked_at=now,
                    attendance_status="present",
                    student_latitude=26.2738,
                    student_longitude=73.0366,
                    distance_from_center=5.2,
                    is_within_geofence=True,
                    device_id="demo_device_win",
                    device_model="Windows PC",
                    device_os="Windows",
                    is_late_entry=False,
                    late_by_minutes=0,
                    qr_validation_passed=True,
                    location_validation_passed=True,
                    device_validation_passed=True,
                    time_validation_passed=True,
                    remarks="Successfully validated"
                )
                db.add(rec)
                qr_session.total_students_present = 1
        # Seed Default Users (Development / Testing Only)
        seed_default_users(db)

        print("[SUCCESS] Database seeding complete!")

    except Exception as e:

        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
