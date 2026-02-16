from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class Club(Base):
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False)  # Technical, Cultural, Sports, etc.
    
    # Enhanced club information
    detailed_description = Column(Text, nullable=True)  # Rich text description
    mission_statement = Column(Text, nullable=True)
    vision_statement = Column(Text, nullable=True)
    
    # Media and branding
    logo_url = Column(String(500), nullable=True)  # Club logo/icon
    banner_image = Column(String(500), nullable=True)  # Header banner
    cover_image = Column(String(500), nullable=True)  # Cover photo
    gallery_images = Column(Text, nullable=True)  # JSON array of image URLs
    social_media_links = Column(Text, nullable=True)  # JSON object with social links
    
    # Contact and administration
    advisor = Column(String, nullable=False)  # Faculty advisor name
    advisor_email = Column(String(200), nullable=True)
    president = Column(String, nullable=True)  # Student president name
    president_email = Column(String(200), nullable=True)
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    
    # Membership and statistics
    member_count = Column(Integer, default=0)
    total_events = Column(Integer, default=0)
    founding_year = Column(Integer, nullable=True)
    
    # Settings
    is_active = Column(Boolean, default=True)
    accepting_members = Column(Boolean, default=True)
    membership_fee = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    activities = relationship("ClubActivity", back_populates="club", cascade="all, delete-orphan")
    members = relationship("ClubMember", back_populates="club", cascade="all, delete-orphan")


class ClubActivity(Base):
    __tablename__ = "club_activities"

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    activity_type = Column(String, nullable=False)  # Event, Workshop, Competition, Meeting, etc.
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    location = Column(String, nullable=True)
    expected_participants = Column(Integer, default=0)
    actual_participants = Column(Integer, default=0)
    status = Column(String, default="Planned")  # Planned, Ongoing, Completed, Cancelled
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    club = relationship("Club", back_populates="activities")


class ClubMember(Base):
    __tablename__ = "club_members"

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    position = Column(String, nullable=True)  # President, Vice-President, Treasurer, Member, etc.
    join_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    club = relationship("Club", back_populates="members")


class ClubAttendance(Base):
    __tablename__ = "club_attendance"

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    student_name = Column(String, nullable=False)
    roll_number = Column(String, nullable=True)
    section = Column(String, nullable=True)
    status = Column(String, nullable=False)  # Present / Absent
    attendance_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship back to club (optional)
    # club = relationship("Club", back_populates="attendance")