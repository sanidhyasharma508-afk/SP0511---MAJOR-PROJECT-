"""
Dashboard API Routes
Exposes aggregated data for frontend consumption
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.risk import RiskLog
from backend.models.complaint import Complaint
from backend.models.schedule import Schedule
from backend.models.attendance import Attendance
from backend.models.student import Student
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class RiskStudentSummary(BaseModel):
    student_id: int
    student_name: str
    risk_count: int
    risk_levels: dict  # {High: count, Medium: count, Low: count}
    latest_risk: str
    last_risk_date: datetime


class ComplaintPrioritySummary(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    low: int
    pending: int
    resolved: int


class ScheduleConflictSummary(BaseModel):
    total_conflicts: int
    affected_schedules: int
    critical_conflicts: List[dict]


@router.get("/risks/students", response_model=List[RiskStudentSummary])
def get_students_at_risk(db: Session = Depends(get_db)):
    """
    Get all students with active risk flags
    Aggregates risk data for dashboard display
    """
    try:
        # Get all unresolved risks grouped by student
        unresolved_risks = db.query(RiskLog).filter(RiskLog.resolved == 0).all()

        student_risks = {}
        for risk in unresolved_risks:
            if risk.student_id:
                if risk.student_id not in student_risks:
                    student_risks[risk.student_id] = []
                student_risks[risk.student_id].append(risk)

        # Build summary
        summaries = []
        for student_id, risks in student_risks.items():
            student = db.query(Student).filter(Student.id == student_id).first()
            if not student:
                continue

            # Count by severity
            severity_counts = {
                "High": sum(1 for r in risks if r.severity == "High"),
                "Medium": sum(1 for r in risks if r.severity == "Medium"),
                "Low": sum(1 for r in risks if r.severity == "Low"),
            }

            # Get latest risk
            latest = max(risks, key=lambda x: x.created_at)

            summaries.append(
                RiskStudentSummary(
                    student_id=student_id,
                    student_name=student.name,
                    risk_count=len(risks),
                    risk_levels=severity_counts,
                    latest_risk=latest.description,
                    last_risk_date=latest.created_at,
                )
            )

        # Sort by risk count (descending)
        summaries.sort(key=lambda x: x.risk_count, reverse=True)
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching risks: {str(e)}")


@router.get("/complaints/priority", response_model=ComplaintPrioritySummary)
def get_complaints_by_priority(db: Session = Depends(get_db)):
    """
    Get complaint summary by priority and status
    Dashboard widget data
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
def get_schedule_conflicts(db: Session = Depends(get_db)):
    """
    Get schedule conflict summary
    Lists all detected conflicts
    """
    try:
        # Get all conflict risk logs
        conflicts = (
            db.query(RiskLog)
            .filter(
                RiskLog.risk_type == "Academic", RiskLog.resolved == 0, RiskLog.student_id == None
            )
            .all()
        )

        conflict_count = len(conflicts)

        # Get affected schedules (parse from risk descriptions)
        affected_schedules = set()
        critical_conflicts = []

        for conflict in conflicts:
            # Extract schedule info from description
            critical_conflicts.append(
                {
                    "conflict_id": conflict.id,
                    "description": conflict.description,
                    "severity": conflict.severity,
                    "created_at": conflict.created_at,
                }
            )
            if conflict.severity == "High":
                # Count unique schedules mentioned (approximation)
                affected_schedules.add(conflict.id)

        summary = ScheduleConflictSummary(
            total_conflicts=conflict_count,
            affected_schedules=len(affected_schedules),
            critical_conflicts=critical_conflicts[:10],  # Top 10 recent conflicts
        )

        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching conflicts: {str(e)}")


@router.get("/attendance/low-attendance")
def get_low_attendance_students(threshold: float = 0.75, db: Session = Depends(get_db)):
    """
    Get students with attendance below threshold
    Useful for dean/admin dashboard
    """
    try:
        LOOKBACK_DAYS = 30
        cutoff_date = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)

        students = db.query(Student).all()
        low_attendance = []

        for student in students:
            records = (
                db.query(Attendance)
                .filter(Attendance.student_id == student.id, Attendance.date >= cutoff_date)
                .all()
            )

            if records:
                present_count = sum(1 for r in records if r.status == "Present")
                ratio = present_count / len(records)

                if ratio < threshold:
                    low_attendance.append(
                        {
                            "student_id": student.id,
                            "student_name": student.name,
                            "attendance_percentage": round(ratio * 100, 2),
                            "total_classes": len(records),
                            "classes_attended": present_count,
                            "department": student.department,
                        }
                    )

        # Sort by attendance percentage
        low_attendance.sort(key=lambda x: x["attendance_percentage"])
        return low_attendance
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching attendance: {str(e)}")


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Get overall dashboard summary statistics
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
