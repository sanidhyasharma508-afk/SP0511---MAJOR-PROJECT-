from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Student full name")
    roll_no: str = Field(..., min_length=1, max_length=20, description="Unique roll number")
    department: str = Field(..., min_length=1, max_length=50, description="Department name")
    semester: int = Field(..., ge=1, le=8, description="Current semester (1-8)")
    section: str = Field(default="_", min_length=1, max_length=10, description="Class section")


class StudentOut(StudentCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class StudentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    roll_no: Optional[str] = Field(None, min_length=1, max_length=20)
    department: Optional[str] = Field(None, min_length=1, max_length=50)
    semester: Optional[int] = Field(None, ge=1, le=8)
    section: Optional[str] = Field(None, min_length=1, max_length=10)
