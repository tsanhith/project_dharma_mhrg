import uuid
from sqlalchemy import Column, String, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from database.db import Base
import enum

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    SCRAPED = "SCRAPED"
    TAILORING = "TAILORING"
    READY = "READY"
    APPLIED = "APPLIED"
    ERROR = "ERROR"
    REJECTED = "REJECTED"
    INTERVIEW = "INTERVIEW"
    ASSESSMENT = "ASSESSMENT"

class JobPipeline(Base):
    __tablename__ = "job_pipeline"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, unique=True, nullable=False, index=True)
    company = Column(String, nullable=True)
    title = Column(String, nullable=True)
    raw_jd_text = Column(Text, nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    error_message = Column(Text, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, default="John Doe")
    email = Column(String, default="john.doe@email.com")
    phone = Column(String, default="(555) 123-4567")
    location = Column(String, default="San Francisco, CA")
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    base_skills = Column(Text, nullable=True)
    base_resume_text = Column(Text, nullable=True)

