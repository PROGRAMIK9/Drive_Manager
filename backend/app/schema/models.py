from datetime import datetime
from typing import Literal
from pydantic import EmailStr
from sqlmodel import SQLModel, Field
from pydantic import field_validator

class UserBase(SQLModel):
    name: str
    email:EmailStr
    role:str

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    year_of_passing: int | None = None


class UserRoleUpdate(SQLModel):
    role: str
    year_of_passing: int | None = None

    @field_validator("year_of_passing")
    @classmethod
    def validate_year(cls, value: int | None) -> int | None:
        if value is not None and value not in (2027, 2028):
            raise ValueError("Year of passing must be 2027 or 2028")
        return value


class GoogleCredential(SQLModel):
    credential: str

class RegistrationResponse(SQLModel):
    message: str
    email: EmailStr

class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"

class CompanyBase(SQLModel):
    name:str
    process:str
    location:str
    date: datetime
    year_of_passing: int = 2027
    considered: bool = False

    @field_validator("year_of_passing")
    @classmethod
    def validate_year(cls, value: int) -> int:
        if value not in (2027, 2028):
            raise ValueError("Year of passing must be 2027 or 2028")
        return value

class CompanyCreate(CompanyBase):
    pass

class CompanyRead(CompanyBase):
    id:int
    interested:bool = False

class CompanyUpdate(CompanyBase):
    year_of_passing: int | None = None

    @field_validator("year_of_passing")
    @classmethod
    def validate_optional_year(cls, value: int | None) -> int | None:
        if value is not None and value not in (2027, 2028):
            raise ValueError("Year of passing must be 2027 or 2028")
        return value


EligibilityStatus = Literal["ELIGIBLE", "NOT_ELIGIBLE", "UNCLEAR"]


class PossibleDuplicate(SQLModel):
    record_type: Literal["PENDING", "PUBLISHED"]
    record_id: int
    company_name: str
    process: str
    event_date: datetime


class PendingOpportunityRead(SQLModel):
    id: int
    company_name: str
    job_title: str | None = None
    description: str | None = None
    opportunity_type: str | None = None
    eligible_courses: list[str]
    eligible_branches: list[str]
    eligible_batches: list[int]
    minimum_cgpa: float | None = None
    backlog_allowed: bool | None = None
    maximum_backlogs: int | None = None
    location: str | None = None
    compensation: str | None = None
    internship_duration: str | None = None
    application_deadline: datetime | None = None
    department_submission_date: datetime | None = None
    assessment_date: datetime | None = None
    group_discussion_date: datetime | None = None
    interview_date: datetime | None = None
    interview_dates: list[str] = Field(default_factory=list)
    possible_duplicates: list[PossibleDuplicate] = Field(default_factory=list)
    application_link: str | None = None
    eligibility_status: EligibilityStatus
    ai_confidence: float | None = None
    missing_information: list[str]
    source_email_id: int | None = None
    source_subject: str | None = None
    source_sender: str | None = None
    source_link: str | None = None
    review_status: str
    rejection_reason: str | None = None
    published_company_id: int | None = None
    created_at: datetime


class PendingOpportunityUpdate(SQLModel):
    company_name: str | None = None
    job_title: str | None = None
    description: str | None = None
    opportunity_type: str | None = None
    eligible_courses: list[str] | None = None
    eligible_branches: list[str] | None = None
    eligible_batches: list[int] | None = None
    minimum_cgpa: float | None = None
    backlog_allowed: bool | None = None
    maximum_backlogs: int | None = None
    location: str | None = None
    compensation: str | None = None
    internship_duration: str | None = None
    application_deadline: datetime | None = None
    department_submission_date: datetime | None = None
    assessment_date: datetime | None = None
    group_discussion_date: datetime | None = None
    interview_date: datetime | None = None
    interview_dates: list[str] | None = None
    application_link: str | None = None


class OpportunityReject(SQLModel):
    reason: str


class GmailStatusRead(SQLModel):
    connected: bool
    email_address: str | None = None
    last_sync_at: datetime | None = None
    watch_expiration: datetime | None = None
    last_error: str | None = None
