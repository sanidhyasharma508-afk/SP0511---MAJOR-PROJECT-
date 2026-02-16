from sqlalchemy import Column, Integer, String
from backend.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    roll_no = Column(String, unique=True, nullable=False)
    department = Column(String, nullable=False)
    semester = Column(Integer)
    section = Column(String, default="_")
