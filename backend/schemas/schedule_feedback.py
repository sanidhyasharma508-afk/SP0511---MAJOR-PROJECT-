from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ScheduleFeedbackCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    roll_number: str = Field(..., min_length=1, max_length=50)
    issue_type: str = Field(..., min_length=1)
    preferred_timing: Optional[str] = None
    additional_comments: Optional[str] = None


class ScheduleFeedbackOut(BaseModel):
    id: int
    name: str
    roll_number: str
    issue_type: str
    preferred_timing: Optional[str]
    additional_comments: Optional[str]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScheduleFeedbackUpdate(BaseModel):
    status: Optional[str] = None
    resolved_at: Optional[datetime] = None


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1, max_length=100)
    priority: str = Field(default="normal")
    target_audience: str = Field(default="all")
    expires_at: Optional[datetime] = None


class AnnouncementOut(BaseModel):
    id: int
    title: str
    content: str
    author: str
    priority: str
    target_audience: str
    is_active: int
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    priority: Optional[str] = None
    is_active: Optional[int] = None
    expires_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    message: str
    whatsapp_message: str
    telegram_message: str
    email_subject: str
    email_body: str
