from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    avatar = Column(Text, nullable=True)
    role = Column(String(20), nullable=False, default="student")  # admin, staff, student, faculty
    is_active = Column(Boolean, default=True, nullable=False)
    linked_student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Optional relationship to Student entity
    student = relationship("Student", backref="user_account", foreign_keys=[linked_student_id])
