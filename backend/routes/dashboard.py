"""
Dashboard API Routes
Exposes aggregated data for frontend consumption with strict authentication,
faculty scoping, and student self-isolation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta
from typing import List, Optional

from backend.database import get_db
from backend.models.risk import RiskLog
from backend.models.complaint import Complaint
from backend.models.schedule import Schedule
from backend.models.attendance import Attendance
from backend.models.student import Student
from backend.models.user import User
from backend.models.events import EventRegistration, Event
from backend.models.club import ClubMember
from backend.core.rbac import get_current_user, require_staff, require_admin, require_faculty
from backend.core.auth import TokenData
from backend.core.academic_risk import (
    get_unified_student_attendance,
    get_student_study_task_metrics,
    calculate_student_academic_risk,
    check_faculty_student_scope,
)
from backend.schemas.dashboard import (
    RiskStudentSummary,
    ComplaintPrioritySummary,
    ScheduleConflictSummary,
    StudentDashboardResponse,
    StudentProfileSummary,
    StudentAttendanceSummary,
    SubjectAttendanceDetail,
    StudentAcademicsSummary,
    StudentStudyTasksSummary,
    StudentCampusInvolvement,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# --- Student Consolidated Dashboard ---

@router.get("/student/me", response_model=StudentDashboardResponse)
def get_my_student_dashboard(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get consolidated dashboard metrics for the authenticated student.
    Aggregates profile, unified attendance, study tasks, academic risk, and campus involvement.
    Does NOT invent grades or marks; returns explicit empty/not-recorded states.
    """
    student = None
    if current_user.linked_student_id is not None:
        student = db.query(Student).filter(Student.id == current_user.linked_student_id).first()
    if not student and current_user.sub:
        student = db.query(Student).filter(Student.roll_no == current_user.sub).first()
    if not student and current_user.user_id:
        student = db.query(Student).filter(Student.id == current_user.user_id).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student record linked to the authenticated user account.",
        )

    # 1. Profile
    profile = StudentProfileSummary(
        id=student.id,
        name=student.name,
        roll_no=student.roll_no,
        department=student.department,
        semester=student.semester,
        section=student.section,
    )

    # 2. Unified Attendance (general + QR deduplicated)
    att_data = get_unified_student_attendance(student, db)
    subject_details = [
        SubjectAttendanceDetail(
            subject_code=s["subject_code"],
            attended_classes=s["attended"],
            total_classes=s["total"],
            percentage=s["percentage"],
            status="Good" if s["percentage"] >= 75.0 else "At Risk",
        )
        for s in att_data["subjects"]
    ]

    attendance_summary = StudentAttendanceSummary(
        overall_percentage=att_data["overall_percentage"],
        total_sessions=att_data["total_sessions"],
        attended_sessions=att_data["attended_sessions"],
        absent_sessions=att_data["absent_sessions"],
        subjects=subject_details,
        trend=att_data["sessions"][-10:],  # last 10 sessions
    )

    # 3. Academics (grades/marks explicit handling)
    academics = StudentAcademicsSummary(
        grades_available=False,
        cgpa=None,
        note="No marks or examination grade records exist in the current campus database.",
    )

    # 4. Personal Study Tasks
    task_metrics = get_student_study_task_metrics(student, db)
    study_tasks = StudentStudyTasksSummary(
        total_tasks=task_metrics["total_tasks"],
        completed_tasks=task_metrics["completed_tasks"],
        pending_tasks=task_metrics["pending_tasks"],
        overdue_tasks=task_metrics["overdue_tasks"],
        study_hours=task_metrics["study_hours"],
        recent_tasks=task_metrics["tasks"],
    )

    # 5. Academic Risk Evaluation
    academic_risk = calculate_student_academic_risk(student.id, db)

    # 6. Campus Involvement
    events_registered = (
        db.query(EventRegistration)
        .filter(
            or_(
                EventRegistration.student_id == str(student.id),
                EventRegistration.roll_number == student.roll_no,
            )
        )
        .count()
    )

    clubs_joined = (
        db.query(ClubMember)
        .filter(ClubMember.student_id == student.id, ClubMember.is_active == True)
        .count()
    )

    upcoming_events_objs = (
        db.query(Event)
        .filter(Event.event_start_date >= datetime.utcnow())
        .order_by(Event.event_start_date.asc())
        .limit(5)
        .all()
    )
    upcoming_events = [
        {
            "id": ev.id,
            "name": ev.name,
            "category": ev.category.value if hasattr(ev.category, "value") else str(ev.category),
            "start_date": ev.event_start_date.isoformat() if ev.event_start_date else None,
            "venue": ev.venue,
        }
        for ev in upcoming_events_objs
    ]

    campus_involvement = StudentCampusInvolvement(
        events_registered_count=events_registered,
        clubs_joined_count=clubs_joined,
        upcoming_events=upcoming_events,
    )

    return StudentDashboardResponse(
        student=profile,
        attendance=attendance_summary,
        academics=academics,
        study_tasks=study_tasks,
        academic_risk=academic_risk,
        campus_involvement=campus_involvement,
    )


# --- Faculty & Administrative Dashboard Endpoints ---

@router.get("/risks/students", response_model=List[RiskStudentSummary])
def get_students_at_risk(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get students with active risk flags.
    - Faculty: Scoped strictly to students within their authorized academic scope.
    - Staff / Admin: Authorized full institutional scope.
    - Students: Rejected (403).
    """
    try:
        faculty_user = db.query(User).filter(User.id == current_user.user_id).first()
        is_faculty_only = (current_user.role or "").lower() == "faculty"

        # Get all unresolved risks grouped by student
        unresolved_risks = db.query(RiskLog).filter(RiskLog.resolved == 0).all()

        student_risks = {}
        for risk in unresolved_risks:
            if risk.student_id:
                if risk.student_id not in student_risks:
                    student_risks[risk.student_id] = []
                student_risks[risk.student_id].append(risk)

        summaries = []
        for student_id, risks in student_risks.items():
            student = db.query(Student).filter(Student.id == student_id).first()
            if not student:
                continue

            # Check faculty scope
            if is_faculty_only and faculty_user:
                if not check_faculty_student_scope(faculty_user, student, db):
                    continue

            severity_counts = {
                "High": sum(1 for r in risks if r.severity in ("High", "Critical")),
                "Medium": sum(1 for r in risks if r.severity == "Medium"),
                "Low": sum(1 for r in risks if r.severity == "Low"),
            }

            latest = max(risks, key=lambda x: x.created_at or datetime.min)

            summaries.append(
                RiskStudentSummary(
                    student_id=student_id,
                    student_name=student.name,
                    risk_count=len(risks),
                    risk_levels=severity_counts,
                    latest_risk=latest.description,
                    last_risk_date=latest.created_at or datetime.utcnow(),
                )
            )

        summaries.sort(key=lambda x: x.risk_count, reverse=True)
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching risks: {str(e)}")


@router.get("/attendance/low-attendance")
def get_low_attendance_students(
    threshold: float = 0.75,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get students with unified attendance below threshold.
    - Faculty: Scoped strictly to students within their authorized academic scope.
    - Staff / Admin: Full institutional scope.
    - Students: Rejected (403).
    Unifies general attendance and QR attendance records to avoid under- or over-counting.
    """
    try:
        faculty_user = db.query(User).filter(User.id == current_user.user_id).first()
        is_faculty_only = (current_user.role or "").lower() == "faculty"

        students = db.query(Student).all()
        low_attendance = []

        for student in students:
            if is_faculty_only and faculty_user:
                if not check_faculty_student_scope(faculty_user, student, db):
                    continue

            att_data = get_unified_student_attendance(student, db)
            pct = att_data["overall_percentage"]

            # If student has attendance records and overall percentage is below threshold
            if pct is not None and (pct / 100.0) < threshold:
                low_attendance.append(
                    {
                        "student_id": student.id,
                        "student_name": student.name,
                        "roll_no": student.roll_no,
                        "attendance_percentage": pct,
                        "total_classes": att_data["total_sessions"],
                        "classes_attended": att_data["attended_sessions"],
                        "department": student.department,
                    }
                )

        low_attendance.sort(key=lambda x: x["attendance_percentage"])
        return low_attendance
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching low attendance: {str(e)}")


@router.get("/complaints/priority", response_model=ComplaintPrioritySummary)
def get_complaints_by_priority(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get complaint summary by priority and status (Faculty/Staff/Admin required).
    """
    try:
        all_complaints = db.query(Complaint).all()

        summary = ComplaintPrioritySummary(
            total=len(all_complaints),
            critical=sum(1 for c in all_complaints if c.priority == "Urgent"),
            high=sum(1 for c in all_complaints if c.priority == "High"),
            medium=sum(1 for c in all_complaints if c.priority == "Normal"),
            low=sum(1 for c in all_complaints if c.priority == "Low"),
            pending=sum(1 for c in all_complaints if c.status == "Pending"),
            resolved=sum(1 for c in all_complaints if c.status == "Resolved"),
        )

        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching complaints: {str(e)}")


@router.get("/schedule/conflicts", response_model=ScheduleConflictSummary)
def get_schedule_conflicts(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get schedule conflict summary (Faculty/Staff/Admin required).
    """
    try:
        conflicts = (
            db.query(RiskLog)
            .filter(
                RiskLog.risk_type == "Academic", RiskLog.resolved == 0, RiskLog.student_id == None
            )
            .all()
        )

        conflict_count = len(conflicts)
        affected_schedules = set()
        critical_conflicts = []

        for conflict in conflicts:
            critical_conflicts.append(
                {
                    "conflict_id": conflict.id,
                    "description": conflict.description,
                    "severity": conflict.severity,
                    "created_at": conflict.created_at,
                }
            )
            if conflict.severity == "High":
                affected_schedules.add(conflict.id)

        summary = ScheduleConflictSummary(
            total_conflicts=conflict_count,
            affected_schedules=len(affected_schedules),
            critical_conflicts=critical_conflicts[:10],
        )

        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching conflicts: {str(e)}")


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get high-level dashboard aggregate statistics.
    Requires authentication. Does not expose individual user credentials or private data.
    """
    try:
        students_total = db.query(Student).count()
        students_at_risk = (
            db.query(RiskLog).filter(RiskLog.resolved == 0).distinct(RiskLog.student_id).count()
        )
        complaints_pending = db.query(Complaint).filter(Complaint.status == "Pending").count()
        schedules_active = db.query(Schedule).filter(Schedule.is_active == 1).count()

        return {
            "total_students": students_total,
            "students_at_risk": students_at_risk,
            "pending_complaints": complaints_pending,
            "active_schedules": schedules_active,
            "timestamp": datetime.utcnow(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching summary: {str(e)}")
