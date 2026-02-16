from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any


class StudentInfo(BaseModel):
    id: int
    name: str
    roll_no: str
    department: Optional[str] = None


class AttendanceMetrics(BaseModel):
    attendance_rate: float
    recent_week_rate: float
    total_records: int
    present: int
    absent: int
    late: int
    period_days: int


class AttendanceAnalysis(BaseModel):
    trend: str  # declining, stable, improving
    severity: str  # Critical, High, Medium, Low
    related_complaints: int
    risk_level: str  # High, Medium, Low


class RetrievedContextInfo(BaseModel):
    document_count: int
    sources: List[str]


class AttendanceExplanationResponse(BaseModel):
    student: StudentInfo
    metrics: AttendanceMetrics
    analysis: AttendanceAnalysis
    reasoning: str
    actions: List[str]
    retrieved_context: RetrievedContextInfo
    timestamp: str

    model_config = ConfigDict(from_attributes=True)


class PeriodMetrics(BaseModel):
    days: int
    total_complaints: int
    by_category: Dict[str, int]
    by_priority: Dict[str, int]


class ComplaintSpikePeriod(BaseModel):
    days: int
    total_complaints: int


class ComplaintMetrics(BaseModel):
    recent_period: PeriodMetrics
    previous_period: ComplaintSpikePeriod
    spike_percentage: float


class ComplaintAnalysis(BaseModel):
    trend: str  # increasing, stable, decreasing
    severity: str  # Critical, High, Medium, Low
    top_category: Optional[str]
    top_priority: Optional[str]


class ComplaintSpikeExplanationResponse(BaseModel):
    metrics: ComplaintMetrics
    analysis: ComplaintAnalysis
    reasoning: str
    actions: List[str]
    retrieved_context: RetrievedContextInfo
    timestamp: str

    model_config = ConfigDict(from_attributes=True)


class RiskInfo(BaseModel):
    id: int
    type: str
    severity: str
    description: str
    created_at: str


class RiskContext(BaseModel):
    related_complaints: int
    recent_absences: int
    days_since_risk: int


class RiskAnalysis(BaseModel):
    risk_active: bool
    action_taken: str
    risk_score: int  # 0-100


class RiskExplanationResponse(BaseModel):
    risk: RiskInfo
    student: Optional[StudentInfo]
    context: RiskContext
    analysis: RiskAnalysis
    reasoning: str
    interventions: List[str]
    retrieved_context: RetrievedContextInfo
    timestamp: str

    model_config = ConfigDict(from_attributes=True)


class AIInsightRequest(BaseModel):
    student_id: Optional[int] = None
    risk_id: Optional[int] = None
    complaint_id: Optional[int] = None
    days: int = 30


class KnowledgeBaseDocument(BaseModel):
    id: int
    type: str  # policy, pattern, strategy
    title: str
    content: str
    category: str
    relevance_score: Optional[float] = None


class RAGContextResponse(BaseModel):
    query: str
    context_type: str
    retrieved_documents: List[KnowledgeBaseDocument]
    document_count: int
    timestamp: str

    model_config = ConfigDict(from_attributes=True)


class AIHealthCheckResponse(BaseModel):
    status: str
    rag_pipeline: bool
    agents: List[str]
    knowledge_base_size: int
    timestamp: str


class NaturalLanguageQueryRequest(BaseModel):
    query: str
    context: Optional[str] = None  # "attendance", "complaint", "risk", or None for general
    include_sources: bool = True


class NaturalLanguageQueryResponse(BaseModel):
    query: str
    answer: str
    confidence: str  # High, Medium, Low
    reasoning: Optional[str] = None
    sources: List[str]
    timestamp: str

    model_config = ConfigDict(from_attributes=True)
