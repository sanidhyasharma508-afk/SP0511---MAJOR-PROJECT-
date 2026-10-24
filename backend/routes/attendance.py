from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime
from typing import List, Optional, Dict, Any

from backend.database import get_db
from backend.schemas.attendance import (
    AttendanceCreate, AttendanceUpdate, AttendanceOut, AttendanceSummary
)
from backend.models.attendance import Attendance
from backend.models.student import Student
from backend.core.event_bus import EventType, event_bus, Event
from backend.core.rbac import get_current_user, require_staff, require_admin, require_faculty
from backend.core.auth import TokenData

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def record_attendance(
    attendance: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """
    Record attendance for a student (Staff/Faculty/Admin required).
    Associates the recording faculty and prevents duplicate attendance for the same student/subject/date.
    """
    if attendance.status not in ["Present", "Absent", "Late", "Excused"]:
        raise HTTPException(status_code=400, detail="Invalid attendance status")

    # Verify student exists
    student = db.query(Student).filter(Student.id == attendance.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    target_date = attendance.date or datetime.utcnow()
    start_of_day = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    end_of_day = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)

    # Check duplicate
    dup_query = db.query(Attendance).filter(
        Attendance.student_id == attendance.student_id,
        Attendance.date >= start_of_day,
        Attendance.date <= end_of_day
    )
    if attendance.subject_code:
        dup_query = dup_query.filter(Attendance.subject_code == attendance.subject_code)
    
    existing = dup_query.first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Attendance already recorded for student {attendance.student_id} on {target_date.date().isoformat()}"
        )

    new_attendance = Attendance(
        student_id=attendance.student_id,
        subject_code=attendance.subject_code,
        faculty_id=str(current_user.user_id),
        session_name=attendance.session_name,
        date=target_date,
        status=attendance.status,
        remarks=attendance.remarks,
    )
    db.add(new_attendance)
    db.commit()
    db.refresh(new_attendance)

    # Publish event to trigger agents
    event = Event(
        EventType.ATTENDANCE_MARKED,
        {
            "student_id": attendance.student_id,
            "status": attendance.status,
            "attendance_id": new_attendance.id,
        },
    )
    event_bus.publish(event)

    return new_attendance


@router.get("/", response_model=List[AttendanceOut])
def get_all_attendance(
    subject_code: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    date_str: Optional[str] = Query(None, alias="date"),
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """
    Get attendance records with optional filtering (Staff/Faculty/Admin only).
    Faculty can view records they created or general records.
    """
    query = db.query(Attendance)

    if current_user.role.lower() in ["staff", "faculty"]:
        query = query.filter(
            or_(
                Attendance.faculty_id == str(current_user.user_id),
                Attendance.faculty_id == None
            )
        )

    if subject_code:
        query = query.filter(Attendance.subject_code == subject_code)
    if status_filter:
        query = query.filter(Attendance.status == status_filter)
    if student_id:
        query = query.filter(Attendance.student_id == student_id)
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
            end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
            query = query.filter(Attendance.date >= start, Attendance.date <= end)
        except ValueError:
            pass

    return query.order_by(Attendance.date.desc()).all()


def resolve_student_id(current_user: TokenData, db: Session) -> Optional[int]:
    """
    Safely resolve the authenticated user's linked student ID.
    Checks linked_student_id on TokenData first, then looks up by roll number (current_user.sub).
    Never treats current_user.user_id as Student.id.
    """
    if current_user.linked_student_id is not None:
        st = db.query(Student).filter(Student.id == current_user.linked_student_id).first()
        if st:
            return st.id
    if current_user.sub:
        st = db.query(Student).filter(Student.roll_no == current_user.sub).first()
        if st:
            return st.id
    return None


@router.get("/student/{student_id}", response_model=List[AttendanceOut])
def get_student_attendance(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get attendance records for a specific student.
    Enforces ownership: students can only view their own attendance.
    """
    if current_user.role.lower() == "student":
        resolved_student_id = resolve_student_id(current_user, db)
        if resolved_student_id is None or resolved_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own attendance records",
            )

    records = db.query(Attendance).filter(Attendance.student_id == student_id).order_by(Attendance.date.desc()).all()
    return records


@router.get("/student/{student_id}/summary", response_model=AttendanceSummary)
def get_student_attendance_summary(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get aggregate attendance percentage and breakdown for a student.
    Enforces ownership: students can only view their own summary.
    """
    if current_user.role.lower() == "student":
        resolved_student_id = resolve_student_id(current_user, db)
        if resolved_student_id is None or resolved_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own attendance summary",
            )

    # Check student exists
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    records = db.query(Attendance).filter(Attendance.student_id == student_id).all()
    total = len(records)
    present = sum(1 for r in records if r.status == "Present")
    absent = sum(1 for r in records if r.status == "Absent")
    late = sum(1 for r in records if r.status == "Late")
    excused = sum(1 for r in records if r.status == "Excused")
    pct = round((present + late) / total * 100, 2) if total > 0 else 100.0

    by_subject: Dict[str, Any] = {}
    for r in records:
        subj = r.subject_code or "General"
        if subj not in by_subject:
            by_subject[subj] = {"total": 0, "present": 0, "absent": 0, "late": 0, "excused": 0}
        by_subject[subj]["total"] += 1
        st = r.status.lower()
        if st in by_subject[subj]:
            by_subject[subj][st] += 1

    for subj, data in by_subject.items():
        data["percentage"] = round((data["present"] + data["late"]) / data["total"] * 100, 2) if data["total"] > 0 else 100.0

    return AttendanceSummary(
        student_id=student_id,
        total_records=total,
        present_count=present,
        absent_count=absent,
        late_count=late,
        excused_count=excused,
        attendance_percentage=pct,
        by_subject=by_subject
    )


@router.get("/{attendance_id}", response_model=AttendanceOut)
def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Get a specific attendance record"""
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    if current_user.role.lower() == "student":
        resolved_student_id = resolve_student_id(current_user, db)
        if resolved_student_id is None or resolved_student_id != record.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own attendance records",
            )

    return record


@router.put("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: int,
    attendance: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """
    Update an attendance record (Staff/Admin required).
    Faculty can only edit records they recorded; Admins can edit any.
    """
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    if current_user.role.lower() in ["staff", "faculty"]:
        if record.faculty_id and record.faculty_id != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit attendance records you recorded"
            )

    if attendance.status:
        if attendance.status not in ["Present", "Absent", "Late", "Excused"]:
            raise HTTPException(status_code=400, detail="Invalid attendance status")
        record.status = attendance.status
    if attendance.remarks is not None:
        record.remarks = attendance.remarks
    if attendance.subject_code is not None:
        record.subject_code = attendance.subject_code
    if attendance.session_name is not None:
        record.session_name = attendance.session_name

    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
):
    """Delete an attendance record (Admin required)"""
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    db.delete(record)
    db.commit()
    return None
