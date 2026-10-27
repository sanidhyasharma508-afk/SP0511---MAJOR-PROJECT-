"""
Academic Risk Evaluation Engine
Deterministic, transparent decision-support system for campus automation.
Combines unified attendance (general + QR deduplicated), personal study tasks,
and official advisory risk logs.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.models.student import Student
from backend.models.attendance import Attendance
from backend.models.qr_attendance import QRAttendanceRecord, QRAttendanceSession
from backend.models.study_task import StudyTask
from backend.models.risk import RiskLog
from backend.models.user import User
from backend.schemas.risk import (
    AcademicRiskEvaluation,
    AcademicRiskFacts,
    SubjectAttendanceRisk,
)

RISK_DISCLAIMER = (
    "This academic risk assessment is an automated deterministic decision-support indicator "
    "based on verified attendance logs, personal study tasks, and advisory records. "
    "It is not an automated academic penalty, definitive judgment, or scientifically validated predictive AI."
)


def get_unified_student_attendance(student: Student, db: Session) -> Dict[str, Any]:
    """
    Fetch and unify attendance records from both general Attendance and QR Attendance.
    Deduplicates records representing the same session based on (date, subject_code).
    """
    # 1. Fetch general attendance records
    general_records = db.query(Attendance).filter(Attendance.student_id == student.id).all()

    # 2. Fetch QR attendance records matching student id or roll number
    qr_query = db.query(QRAttendanceRecord).join(
        QRAttendanceSession, QRAttendanceRecord.session_id == QRAttendanceSession.id
    )
    qr_records = qr_query.filter(
        or_(
            QRAttendanceRecord.student_id == str(student.id),
            QRAttendanceRecord.roll_number == student.roll_no,
        )
    ).all()

    # Unified sessions map: key -> dict(date, subject, status, source)
    # Session key: (date_string, normalized_subject_code)
    unified_sessions: Dict[str, Dict[str, Any]] = {}

    for gen in general_records:
        date_str = gen.date.strftime("%Y-%m-%d") if gen.date else datetime.utcnow().strftime("%Y-%m-%d")
        sub_code = (gen.subject_code or "GENERAL").strip().upper()
        key = f"{date_str}::{sub_code}"
        
        is_present = (gen.status or "").strip().lower() in ("present", "late")
        if key not in unified_sessions:
            unified_sessions[key] = {
                "date": date_str,
                "subject_code": sub_code,
                "is_present": is_present,
                "sources": ["general"],
            }
        else:
            if is_present:
                unified_sessions[key]["is_present"] = True
            unified_sessions[key]["sources"].append("general")

    for qr in qr_records:
        session_obj = qr.session
        if session_obj and session_obj.lecture_date:
            date_str = session_obj.lecture_date.strftime("%Y-%m-%d")
        elif qr.marked_at:
            date_str = qr.marked_at.strftime("%Y-%m-%d")
        else:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        sub_code = (
            (session_obj.subject_code if session_obj and session_obj.subject_code else "GENERAL")
            .strip()
            .upper()
        )
        key = f"{date_str}::{sub_code}"

        is_present = (qr.attendance_status or "").strip().lower() in ("present", "late")
        if key not in unified_sessions:
            unified_sessions[key] = {
                "date": date_str,
                "subject_code": sub_code,
                "is_present": is_present,
                "sources": ["qr"],
            }
        else:
            if is_present:
                unified_sessions[key]["is_present"] = True
            unified_sessions[key]["sources"].append("qr")

    total_sessions = len(unified_sessions)
    attended_sessions = sum(1 for s in unified_sessions.values() if s["is_present"])
    absent_sessions = total_sessions - attended_sessions

    overall_percentage = (
        round((attended_sessions / total_sessions) * 100, 2)
        if total_sessions > 0
        else None
    )

    # Subject-level grouping
    subject_map: Dict[str, Dict[str, int]] = {}
    for sess in unified_sessions.values():
        sub = sess["subject_code"]
        if sub not in subject_map:
            subject_map[sub] = {"total": 0, "attended": 0}
        subject_map[sub]["total"] += 1
        if sess["is_present"]:
            subject_map[sub]["attended"] += 1

    subjects_list: List[Dict[str, Any]] = []
    for sub, counts in sorted(subject_map.items()):
        pct = round((counts["attended"] / counts["total"]) * 100, 2) if counts["total"] > 0 else 0.0
        subjects_list.append({
            "subject_code": sub,
            "attended": counts["attended"],
            "total": counts["total"],
            "percentage": pct,
        })

    # Sort sessions by date for trend
    sorted_sessions = sorted(unified_sessions.values(), key=lambda x: x["date"])

    return {
        "total_sessions": total_sessions,
        "attended_sessions": attended_sessions,
        "absent_sessions": absent_sessions,
        "overall_percentage": overall_percentage,
        "subjects": subjects_list,
        "sessions": sorted_sessions,
    }


def get_student_study_task_metrics(student: Student, db: Session) -> Dict[str, Any]:
    """
    Fetch personal study tasks for the student (via linked User account or roll number).
    """
    linked_user = db.query(User).filter(
        or_(
            User.linked_student_id == student.id,
            User.username == student.roll_no,
        )
    ).first()

    if not linked_user:
        return {
            "total_tasks": 0,
            "completed_tasks": 0,
            "pending_tasks": 0,
            "overdue_tasks": 0,
            "study_hours": 0.0,
            "tasks": [],
        }

    tasks = db.query(StudyTask).filter(StudyTask.user_id == linked_user.id).all()
    now = datetime.utcnow()

    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.is_completed)
    pending_tasks = total_tasks - completed_tasks
    overdue_tasks = sum(
        1 for t in tasks
        if not t.is_completed and t.due_date and t.due_date < now
    )

    # Calculate actual study hours logged
    total_seconds_spent = 0
    for t in tasks:
        dur = (getattr(t, "duration_minutes", 0) or 0) * 60
        rem = t.remaining_seconds if t.remaining_seconds is not None else dur
        spent = max(0, dur - rem)
        total_seconds_spent += spent

    study_hours = round(total_seconds_spent / 3600.0, 1)

    task_summaries = [
        {
            "id": t.id,
            "title": t.title,
            "is_completed": t.is_completed,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "duration_minutes": getattr(t, "duration_minutes", 0) or 0,
            "is_overdue": bool(not t.is_completed and t.due_date and t.due_date < now),
        }
        for t in sorted(tasks, key=lambda x: x.due_date or datetime.max)[:10]
    ]

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
        "study_hours": study_hours,
        "tasks": task_summaries,
    }


def get_student_advisory_logs(student_id: int, db: Session) -> List[RiskLog]:
    """
    Fetch active (unresolved) advisory risk logs for the student.
    """
    return db.query(RiskLog).filter(
        RiskLog.student_id == student_id,
        RiskLog.resolved == 0
    ).all()


def calculate_student_academic_risk(student_id: int, db: Session) -> AcademicRiskEvaluation:
    """
    Deterministic academic risk evaluation.
    
    Scoring Model (0 to 100):
      1. Overall Attendance (up to 40 pts):
         - < 60%: +40 pts
         - 60% - 74.9%: +25 pts
         - 75% - 84.9%: +10 pts
         - >= 85%: 0 pts
      2. Subject-Level Deficit (up to 15 pts):
         - +5 pts for each subject below 75% (capped at 15 pts)
      3. Task Engagement (up to 20 pts):
         - Overdue tasks: +5 pts per overdue task (capped at 15 pts)
         - Low completion rate (< 50% when >= 3 tasks): +5 pts
      4. Active Advisory Risk Logs (up to 25 pts):
         - Critical: +20 pts
         - High: +15 pts
         - Medium: +10 pts
         - Low: +5 pts
         (capped at 25 pts)
    
    Risk Levels:
      - 0 to 29: LOW
      - 30 to 59: MEDIUM
      - 60 to 100: HIGH
      - No data: INSUFFICIENT_DATA (score = None)
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError(f"Student with id {student_id} not found")

    att_data = get_unified_student_attendance(student, db)
    task_data = get_student_study_task_metrics(student, db)
    risk_logs = get_student_advisory_logs(student_id, db)

    total_sessions = att_data["total_sessions"]
    attended_sessions = att_data["attended_sessions"]
    overall_pct = att_data["overall_percentage"]

    # Subject evaluations
    subject_evals: List[SubjectAttendanceRisk] = []
    subjects_below_threshold: List[str] = []
    for s in att_data["subjects"]:
        is_below = s["percentage"] < 75.0
        if is_below:
            subjects_below_threshold.append(s["subject_code"])
        subject_evals.append(
            SubjectAttendanceRisk(
                subject_code=s["subject_code"],
                attended_sessions=s["attended"],
                total_sessions=s["total"],
                attendance_percentage=s["percentage"],
                is_below_threshold=is_below,
            )
        )

    facts = AcademicRiskFacts(
        total_sessions=total_sessions,
        attended_sessions=attended_sessions,
        attendance_percentage=overall_pct,
        subjects_evaluated=subject_evals,
        subjects_below_threshold=subjects_below_threshold,
        total_study_tasks=task_data["total_tasks"],
        overdue_study_tasks=task_data["overdue_tasks"],
        completed_study_tasks=task_data["completed_tasks"],
        active_advisory_logs_count=len(risk_logs),
        marks_recorded=False,
        marks_note="No marks or examination grade records exist in the current campus database.",
    )

    # Check for insufficient data
    if total_sessions == 0 and task_data["total_tasks"] == 0 and len(risk_logs) == 0:
        return AcademicRiskEvaluation(
            student_id=student.id,
            student_name=student.name,
            roll_no=student.roll_no,
            department=student.department,
            semester=student.semester,
            risk_level="INSUFFICIENT_DATA",
            risk_score=None,
            data_sufficiency="INSUFFICIENT_DATA",
            observed_facts=facts,
            contributing_reasons=[
                "No class attendance records, personal study tasks, or advisory logs exist for this student in the database."
            ],
            recommendations=[
                "Ensure student is attending scheduled classes and marking attendance.",
                "Create personal study tasks to organize academic milestones.",
            ],
            disclaimer=RISK_DISCLAIMER,
            evaluated_at=datetime.utcnow(),
        )

    score = 0
    reasons: List[str] = []
    recommendations: List[str] = []

    # 1. Attendance scoring
    if total_sessions > 0 and overall_pct is not None:
        if overall_pct < 60.0:
            score += 40
            reasons.append(f"Critically low overall attendance: {overall_pct}% (minimum requirement: 75.0%).")
            recommendations.append("Immediately attend upcoming lectures and consult your academic advisor.")
        elif overall_pct < 75.0:
            score += 25
            reasons.append(f"Overall attendance is below the institutional 75% threshold at {overall_pct}%.")
            recommendations.append("Increase daily lecture attendance to reach the mandatory 75% cutoff before exams.")
        elif overall_pct < 85.0:
            score += 10
            reasons.append(f"Overall attendance is borderline ({overall_pct}%).")
            recommendations.append("Maintain consistent participation to stay safely above the 75% threshold.")
        else:
            reasons.append(f"Overall attendance is in good standing at {overall_pct}%.")
            recommendations.append("Keep up your strong class attendance record.")

        # Subject-level deficit
        if subjects_below_threshold:
            deficit_points = min(15, len(subjects_below_threshold) * 5)
            score += deficit_points
            sub_str = ", ".join(subjects_below_threshold)
            reasons.append(f"Attendance is below 75% in {len(subjects_below_threshold)} subject(s): {sub_str}.")
            recommendations.append(f"Focus on attending subsequent classes in: {sub_str}.")
    else:
        reasons.append("No class attendance records found; attendance risk cannot be evaluated.")
        recommendations.append("Verify student enrollment in scheduled timetable classes.")

    # 2. Study task engagement
    if task_data["overdue_tasks"] > 0:
        task_points = min(15, task_data["overdue_tasks"] * 5)
        score += task_points
        reasons.append(f"{task_data['overdue_tasks']} personal study task(s) are currently overdue.")
        recommendations.append("Review and complete pending study tasks to stay on track with coursework.")

    if task_data["total_tasks"] >= 3:
        completion_rate = task_data["completed_tasks"] / task_data["total_tasks"]
        if completion_rate < 0.5:
            score += 5
            reasons.append(
                f"Study task completion rate is low ({task_data['completed_tasks']}/{task_data['total_tasks']})."
            )
            recommendations.append("Break large study tasks into smaller, manageable daily sessions.")

    # 3. Advisory risk logs
    if risk_logs:
        log_points = 0
        for log in risk_logs:
            sev = (log.severity or "Medium").capitalize()
            if sev == "Critical":
                log_points += 20
                reasons.append(f"Active Critical advisory log: {log.description}")
            elif sev == "High":
                log_points += 15
                reasons.append(f"Active High advisory log: {log.description}")
            elif sev == "Medium":
                log_points += 10
                reasons.append(f"Active Medium advisory log: {log.description}")
            else:
                log_points += 5
                reasons.append(f"Active Low advisory log: {log.description}")
        score += min(25, log_points)
        recommendations.append("Schedule an advisory session with faculty staff regarding open risk notes.")

    # Explicit note regarding marks
    reasons.append("Note: Examination marks/grades are not recorded in the database and are excluded from calculation.")

    final_score = min(100, max(0, score))
    if final_score >= 60:
        risk_level = "HIGH"
    elif final_score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    data_sufficiency = "SUFFICIENT" if total_sessions > 0 else "PARTIAL"

    return AcademicRiskEvaluation(
        student_id=student.id,
        student_name=student.name,
        roll_no=student.roll_no,
        department=student.department,
        semester=student.semester,
        risk_level=risk_level,
        risk_score=final_score,
        data_sufficiency=data_sufficiency,
        observed_facts=facts,
        contributing_reasons=reasons,
        recommendations=recommendations,
        disclaimer=RISK_DISCLAIMER,
        evaluated_at=datetime.utcnow(),
    )


def check_faculty_student_scope(faculty_user: User, student: Student, db: Session) -> bool:
    """
    Verify whether a faculty user has authorized academic scope for a student.
    Scope includes:
      - Admin or Staff: full institutional scope.
      - Faculty who conducted an Attendance or QR session attended by the student.
      - Faculty whose department matches the student's department.
    """
    role = (faculty_user.role or "").lower()
    if role in ("admin", "staff"):
        return True

    # Check department match if faculty has student profile or department
    # Let's check if faculty has attendance records for this student
    has_att = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        or_(
            Attendance.faculty_id == str(faculty_user.id),
            Attendance.faculty_id == faculty_user.username,
        )
    ).first()
    if has_att:
        return True

    # Check QR attendance sessions created by this faculty
    has_qr = db.query(QRAttendanceRecord).join(
        QRAttendanceSession, QRAttendanceRecord.session_id == QRAttendanceSession.id
    ).filter(
        or_(
            QRAttendanceRecord.student_id == str(student.id),
            QRAttendanceRecord.roll_number == student.roll_no,
        ),
        or_(
            QRAttendanceSession.faculty_id == str(faculty_user.id),
            QRAttendanceSession.faculty_id == faculty_user.username,
            QRAttendanceSession.faculty_email == faculty_user.email,
        )
    ).first()
    if has_qr:
        return True

    # Check if faculty's linked student or profile matches department
    if faculty_user.linked_student_id:
        fac_student = db.query(Student).filter(Student.id == faculty_user.linked_student_id).first()
        if fac_student and fac_student.department.strip().lower() == student.department.strip().lower():
            return True

    return False
