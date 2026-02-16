from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class AttendanceCreate(BaseModel):
    student_id: int
    status: str = Field(..., description="Present, Absent, Late, Excused")
    remarks: Optional[str] = None


class AttendanceOut(AttendanceCreate):
    id: int
    date: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
