from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from backend.schemas.risk import AcademicRiskEvaluation


class RiskStudentSummary(BaseModel):
    student_id: int
    student_name: str
    risk_count: int
    risk_levels: Dict[str, int]
    latest_risk: str
    last_risk_date: datetime


class ComplaintPrioritySummary(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    low: int
    pending: int
    resolved: int


class ScheduleConflictSummary(BaseModel):
    total_conflicts: int
    affected_schedules: int
    critical_conflicts: List[Dict[str, Any]]


class LowAttendanceStudent(BaseModel):
    student_id: int
    student_name: str
    attendance_percentage: float
    total_classes: int
    classes_attended: int
    department: str


class StudentProfileSummary(BaseModel):
    id: int
    name: str
    roll_no: str
    department: str
    semester: int
    section: Optional[str] = None


class SubjectAttendanceDetail(BaseModel):
    subject_code: str
    attended_classes: int
    total_classes: int
    percentage: float
    status: str  # e.g., "Good", "Low"


class StudentAttendanceSummary(BaseModel):
    overall_percentage: Optional[float] = None
    total_sessions: int
    attended_sessions: int
    absent_sessions: int
    subjects: List[SubjectAttendanceDetail] = []
    trend: List[Dict[str, Any]] = []


class StudentAcademicsSummary(BaseModel):
    grades_available: bool = False
    cgpa: Optional[float] = None
    note: str = "No marks or examination grade records exist in the current campus database."


class StudentStudyTasksSummary(BaseModel):
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    study_hours: float
    recent_tasks: List[Dict[str, Any]] = []


class StudentCampusInvolvement(BaseModel):
    events_registered_count: int
    clubs_joined_count: int
    upcoming_events: List[Dict[str, Any]] = []


class StudentDashboardResponse(BaseModel):
    student: StudentProfileSummary
    attendance: StudentAttendanceSummary
    academics: StudentAcademicsSummary
    study_tasks: StudentStudyTasksSummary
    academic_risk: AcademicRiskEvaluation
    campus_involvement: StudentCampusInvolvement
