from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List


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


# Academic Risk Evaluation Schemas (Task 7)
class SubjectAttendanceRisk(BaseModel):
    subject_code: str
    attended_sessions: int
    total_sessions: int
    attendance_percentage: float
    is_below_threshold: bool


class AcademicRiskFacts(BaseModel):
    total_sessions: int
    attended_sessions: int
    attendance_percentage: Optional[float] = None
    subjects_evaluated: List[SubjectAttendanceRisk] = []
    subjects_below_threshold: List[str] = []
    total_study_tasks: int = 0
    overdue_study_tasks: int = 0
    completed_study_tasks: int = 0
    active_advisory_logs_count: int = 0
    marks_recorded: bool = False
    marks_note: str = "No marks or examination grade records exist in the current campus database."


class AcademicRiskEvaluation(BaseModel):
    student_id: int
    student_name: str
    roll_no: str
    department: str
    semester: int
    risk_level: str  # LOW, MEDIUM, HIGH, INSUFFICIENT_DATA
    risk_score: Optional[int] = None  # 0 - 100, or null if INSUFFICIENT_DATA
    data_sufficiency: str  # SUFFICIENT, PARTIAL, INSUFFICIENT_DATA
    observed_facts: AcademicRiskFacts
    contributing_reasons: List[str]
    recommendations: List[str]
    disclaimer: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)

