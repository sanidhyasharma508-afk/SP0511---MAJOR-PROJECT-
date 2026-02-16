from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class ScheduleCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    event_type: str = Field(..., description="Class, Exam, Event, Holiday")
    start_date: datetime
    end_date: datetime
    location: Optional[str] = None
    audience: Optional[str] = None


class ScheduleOut(ScheduleCreate):
    id: int
    is_active: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    audience: Optional[str] = None
    is_active: Optional[int] = None
