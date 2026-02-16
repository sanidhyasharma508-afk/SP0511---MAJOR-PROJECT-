from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.attendance import AttendanceCreate, AttendanceOut
from backend.models.attendance import Attendance
from backend.core.event_bus import EventType, event_bus, Event
from datetime import datetime

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def record_attendance(attendance: AttendanceCreate, db: Session = Depends(get_db)):
    """Record attendance for a student"""
    if attendance.status not in ["Present", "Absent", "Late", "Excused"]:
        raise HTTPException(status_code=400, detail="Invalid attendance status")

    new_attendance = Attendance(
        student_id=attendance.student_id, status=attendance.status, remarks=attendance.remarks
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


@router.get("/", response_model=list[AttendanceOut])
def get_all_attendance(db: Session = Depends(get_db)):
    """Get all attendance records"""
    return db.query(Attendance).all()


@router.get("/student/{student_id}", response_model=list[AttendanceOut])
def get_student_attendance(student_id: int, db: Session = Depends(get_db)):
    """Get attendance records for a specific student"""
    records = db.query(Attendance).filter(Attendance.student_id == student_id).all()
    if not records:
        raise HTTPException(status_code=404, detail="No attendance records found")
    return records


@router.get("/{attendance_id}", response_model=AttendanceOut)
def get_attendance(attendance_id: int, db: Session = Depends(get_db)):
    """Get a specific attendance record"""
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return record


@router.put("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: int, attendance: AttendanceCreate, db: Session = Depends(get_db)
):
    """Update an attendance record"""
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    record.status = attendance.status
    record.remarks = attendance.remarks
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(attendance_id: int, db: Session = Depends(get_db)):
    """Delete an attendance record"""
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    db.delete(record)
    db.commit()
    return None
