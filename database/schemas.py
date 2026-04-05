from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from database.models import JobStatus

class JobCreate(BaseModel):
    url: str
    company: Optional[str] = None
    title: str

class JobResponse(BaseModel):
    id: str
    url: str
    company: Optional[str] = None
    title: str
    raw_jd_text: Optional[str] = None
    status: JobStatus
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class AgentState(BaseModel):
    job_id: str
    status: JobStatus
    error_message: Optional[str] = None

class UserProfileCreate(BaseModel):
    name: str = "John Doe"
    email: str = "john.doe@email.com"
    phone: str = "(555) 123-4567"
    location: str = "San Francisco, CA"
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    base_skills: Optional[str] = None
    base_resume_text: Optional[str] = None

class UserProfileResponse(UserProfileCreate):
    id: str

    class Config:
        from_attributes = True
