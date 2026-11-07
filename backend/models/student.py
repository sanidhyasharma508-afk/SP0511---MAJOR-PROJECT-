from sqlalchemy import Column, Integer, String
from backend.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    roll_no = Column(String(50), unique=True, nullable=False)
    department = Column(String(100), nullable=False)
    semester = Column(Integer)
    section = Column(String(20), default="_")
