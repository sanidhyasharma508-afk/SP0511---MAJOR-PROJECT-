from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class StudyTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: Optional[str] = Field(None, description="Detailed task notes or description")
    duration_minutes: Optional[int] = Field(0, ge=0, description="Duration in minutes")
    remaining_seconds: Optional[int] = Field(0, ge=0, description="Remaining time in seconds")
    is_completed: Optional[bool] = Field(False, description="Completion status")
    due_date: Optional[datetime] = Field(None, description="Optional task deadline or due date")


class StudyTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    remaining_seconds: Optional[int] = Field(None, ge=0)
    is_completed: Optional[bool] = None
    due_date: Optional[datetime] = None


class StudyTaskOut(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    duration_minutes: int = 0
    remaining_seconds: int = 0
    is_completed: bool = False
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
