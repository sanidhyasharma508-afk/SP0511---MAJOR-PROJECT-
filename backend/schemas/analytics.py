from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class DailyAttendanceData(BaseModel):
    date: str
    attendance_rate: float
    present: int
    total: int


class AttendanceTrendResponse(BaseModel):
    student_id: int
    period_days: int
    daily_data: List[DailyAttendanceData]
    moving_average: List[float]
    trend_slope: float
    trend_direction: str  # improving, declining, stable
    model_config = ConfigDict(from_attributes=True)


class WeeklyComplaintData(BaseModel):
    week: str
    total: int
    urgent: int
    high: int
    medium: int
    low: int


class ComplaintTrendResponse(BaseModel):
    period_days: int
    total_complaints: int
    weekly_data: List[WeeklyComplaintData]
    moving_average: List[float]
    trend_slope: float
    trend_direction: str  # increasing, decreasing, stable
    model_config = ConfigDict(from_attributes=True)


class AnomalyAlert(BaseModel):
    type: str  # attendance_drop, complaint_spike
    severity: str
    description: str
    timestamp: datetime
    student_id: Optional[int] = None


class HeatmapCell(BaseModel):
    day_of_week: str
    hour: int
    count: int
    intensity: float  # 0-1


class ComplaintHeatmapResponse(BaseModel):
    period_days: int
    total_complaints: int
    heatmap: List[HeatmapCell]
    top_categories: Dict[str, int]
    top_times: List[Dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)


class RiskDistributionItem(BaseModel):
    risk_type: str
    count: int
    percentage: float
    severity_breakdown: Dict[str, int]


class RiskDistributionResponse(BaseModel):
    total_risks: int
    unresolved_risks: int
    resolved_risks: int
    risk_distribution: List[RiskDistributionItem]
    severity_distribution: Dict[str, int]
    top_affected_students: List[Dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)


class AnalyticsAnomalies(BaseModel):
    recent_anomalies: List[AnomalyAlert]
    attendance_anomaly_count: int
    complaint_spike_count: int
    model_config = ConfigDict(from_attributes=True)
