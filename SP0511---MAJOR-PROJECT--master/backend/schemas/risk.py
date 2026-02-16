from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class RiskLogCreate(BaseModel):
    student_id: Optional[int] = None
    risk_type: str = Field(..., description="Academic, Behavioral, Health, Attendance, Other")
    severity: str = Field(default="Medium", description="Low, Medium, High, Critical")
    description: str = Field(..., min_length=10)
    action_taken: Optional[str] = None


class RiskLogOut(RiskLogCreate):
    id: int
    resolved: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RiskLogUpdate(BaseModel):
    risk_type: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    action_taken: Optional[str] = None
    resolved: Optional[int] = None
