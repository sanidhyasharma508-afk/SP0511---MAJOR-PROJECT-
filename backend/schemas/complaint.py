from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class ComplaintCreate(BaseModel):
    student_id: int
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    category: str = Field(..., description="Academic, Conduct, Health, Other")
    priority: Optional[str] = Field(default="Normal", description="Low, Normal, High, Urgent")


class ComplaintOut(ComplaintCreate):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ComplaintUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
