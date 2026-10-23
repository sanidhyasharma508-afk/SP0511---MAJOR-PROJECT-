from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any


class AttendanceCreate(BaseModel):
    student_id: int
    status: str = Field(..., description="Present, Absent, Late, Excused")
    subject_code: Optional[str] = None
    session_name: Optional[str] = None
    date: Optional[datetime] = None
    remarks: Optional[str] = None


class AttendanceUpdate(BaseModel):
    status: Optional[str] = None
    remarks: Optional[str] = None
    subject_code: Optional[str] = None
    session_name: Optional[str] = None


class AttendanceOut(BaseModel):
    id: int
    student_id: int
    status: str
    subject_code: Optional[str] = None
    faculty_id: Optional[str] = None
    session_name: Optional[str] = None
    date: datetime
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AttendanceSummary(BaseModel):
    student_id: int
    total_records: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    attendance_percentage: float
    by_subject: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)
