from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=False)  # Academic, Conduct, Health, Other, Facility, Mess, Schedule
    status = Column(String, default="Pending", nullable=False)  # Pending, Under Review, In Progress, Resolved, Closed, Rejected
    priority = Column(String, default="Normal", nullable=False)  # Low, Normal, High, Urgent
    resolution_notes = Column(Text, nullable=True)
    assigned_to = Column(Integer, nullable=True)  # Staff User ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    history = relationship("ComplaintHistory", back_populates="complaint", cascade="all, delete-orphan", order_by="ComplaintHistory.created_at.desc()")


class ComplaintHistory(Base):
    __tablename__ = "complaint_history"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    changed_by_user_id = Column(Integer, nullable=True)
    changed_by_name = Column(String(100), nullable=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    complaint = relationship("Complaint", back_populates="history")

    @property
    def action(self):
        if self.old_status:
            return f"status_change: {self.old_status} -> {self.new_status}"
        return "created"

    @property
    def status(self):
        return self.new_status
