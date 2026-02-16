from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from backend.database import Base


class RiskLog(Base):
    __tablename__ = "risk_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=True)  # Can be null for general logs
    risk_type = Column(String, nullable=False)  # Academic, Behavioral, Health, Attendance, Other
    severity = Column(String, default="Medium", nullable=False)  # Low, Medium, High, Critical
    description = Column(Text, nullable=False)
    action_taken = Column(Text, nullable=True)
    resolved = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
