from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List


class ComplaintCreate(BaseModel):
    student_id: Optional[int] = None
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    category: str = Field(..., description="Academic, Conduct, Health, Other")
    priority: Optional[str] = Field(default="Normal", description="Low, Normal, High, Urgent")


class ComplaintOut(BaseModel):
    id: int
    student_id: int
    title: str
    description: str
    category: str
    priority: str
    status: str
    resolution_notes: Optional[str] = None
    assigned_to: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ComplaintUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    resolution_notes: Optional[str] = None
    assigned_to: Optional[int] = None


class ComplaintHistoryOut(BaseModel):
    id: int
    complaint_id: int
    changed_by_user_id: Optional[int] = None
    changed_by_name: Optional[str] = None
    old_status: Optional[str] = None
    new_status: str
    status: Optional[str] = None
    remarks: Optional[str] = None
    action: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    model_config = ConfigDict(from_attributes=True)
