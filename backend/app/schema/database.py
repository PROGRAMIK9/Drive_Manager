from enum import Enum
from datetime import datetime, timezone
from typing import Any
import sqlalchemy as sa
from sqlmodel import Column, Field, Relationship, SQLModel


class Process(Enum):
    online_assesment = "online_assesment"
    interview = "interview"
    ppt = "ppt"
    group_discussion = "group_discussion"
    pen_paper_test = "pen_paper_test"
    technical_assessment = "technical_assessment"
    send_mail = "send_mail"

class Role(Enum):
    spc = "SPC"
    student = "STUDENT"    

    
class Company(SQLModel, table = True):
    id: int = Field(default = None, primary_key = True)
    name: str
    process: Process
    location: str
    date: datetime
    year_of_passing: int = Field(default=2027)
    considered: bool
    interested_users: list["Interested"] = Relationship(
        back_populates="company"
    )
    reminder: "EventReminder" = Relationship(back_populates="company")


class EventReminder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", unique=True, index=True)
    scheduled_at: datetime = Field(sa_type=sa.DateTime(timezone=True), index=True)
    day_before_scheduled_at: datetime = Field(default=None, sa_type=sa.DateTime(timezone=True), index=True)
    sent_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    claimed_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True), index=True)
    day_before_sent_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    day_before_claimed_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True), index=True)
    company: Company = Relationship(back_populates="reminder")


class User(SQLModel, table = True):
    id: int = Field(default = None, primary_key = True)
    name: str
    email: str
    hashed_password: str | None = None
    google_sub: str | None = Field(default=None, unique=True, index=True)
    role: Role = Field(sa_column=Column("role", sa.Enum(Role)))
    is_verified: bool = Field(default=False, nullable=False)
    year_of_passing: int | None = Field(default=None)
    interetsed_companies: list["Interested"] = Relationship(
        back_populates="user"
    )


class PendingRegistration(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    hashed_password: str
    role: Role = Field(sa_column=Column("role", sa.Enum(Role)))


class GmailIntegration(SQLModel, table=True):
    """Persist the status of the single official placement inbox connection."""
    id: int | None = Field(default=None, primary_key=True)
    provider: str = Field(default="gmail", max_length=32)
    email_address: str = Field(index=True, max_length=320)
    encrypted_refresh_token: str | None = Field(default=None)
    connected: bool = Field(default=False, nullable=False)
    last_history_id: str | None = Field(default=None, max_length=128)
    watch_expiration: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    last_sync_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    last_error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=sa.DateTime(timezone=True), nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=sa.DateTime(timezone=True), nullable=False)


class GmailOAuthState(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    state_hash: str = Field(unique=True, index=True, max_length=64)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=sa.DateTime(timezone=True), nullable=False)


class GmailNotification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pubsub_message_id: str = Field(unique=True, index=True, max_length=255)
    email_address: str = Field(index=True, max_length=320)
    history_id: str = Field(max_length=128)
    received_at: datetime = Field(default_factory=datetime.utcnow, sa_type=sa.DateTime(timezone=True), nullable=False)
    processing_status: str = Field(default="RECEIVED", max_length=32, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    processing_started_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    next_attempt_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=sa.DateTime(timezone=True), nullable=False)
    last_error: str | None = Field(default=None)


class ProcessedEmail(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    gmail_message_id: str = Field(unique=True, index=True, max_length=255)
    gmail_thread_id: str | None = Field(default=None, index=True, max_length=255)
    sender: str | None = Field(default=None, max_length=320)
    subject: str | None = Field(default=None)
    received_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    classification: str = Field(default="UNCERTAIN", max_length=40)
    processing_status: str = Field(default="RECEIVED", max_length=40, index=True)
    processing_error: str | None = Field(default=None)
    extracted_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(sa.JSON, nullable=False))
    source_link: str | None = Field(default=None)
    content_hash: str | None = Field(default=None, index=True, max_length=64)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=sa.DateTime(timezone=True), nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=sa.DateTime(timezone=True), nullable=False)


class PendingPlacementOpportunity(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_name: str = Field(index=True, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None)
    opportunity_type: str | None = Field(default=None, max_length=80)
    eligible_courses: list[str] = Field(default_factory=list, sa_column=Column(sa.JSON, nullable=False))
    eligible_branches: list[str] = Field(default_factory=list, sa_column=Column(sa.JSON, nullable=False))
    eligible_batches: list[int] = Field(default_factory=list, sa_column=Column(sa.JSON, nullable=False))
    minimum_cgpa: float | None = Field(default=None)
    backlog_allowed: bool | None = Field(default=None)
    maximum_backlogs: int | None = Field(default=None)
    location: str | None = Field(default=None, max_length=255)
    compensation: str | None = Field(default=None, max_length=255)
    internship_duration: str | None = Field(default=None, max_length=255)
    application_deadline: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    department_submission_date: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    assessment_date: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    group_discussion_date: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    interview_date: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    interview_dates: list[str] = Field(default_factory=list, sa_column=Column(sa.JSON, nullable=False))
    application_link: str | None = Field(default=None)
    eligibility_status: str = Field(default="UNCLEAR", max_length=24, index=True)
    ai_confidence: float | None = Field(default=None)
    missing_information: list[str] = Field(default_factory=list, sa_column=Column(sa.JSON, nullable=False))
    source_email_id: int | None = Field(default=None, foreign_key="processedemail.id", index=True)
    review_status: str = Field(default="PENDING", max_length=24, index=True)
    reviewed_by: int | None = Field(default=None, foreign_key="user.id")
    reviewed_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    rejection_reason: str | None = Field(default=None)
    published_company_id: int | None = Field(default=None, foreign_key="company.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=sa.DateTime(timezone=True), nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=sa.DateTime(timezone=True), nullable=False)

    source_email: ProcessedEmail | None = Relationship()
    reviewer: User | None = Relationship()
    published_company: Company | None = Relationship()

class Interested(SQLModel, table = True):
    user_id: int = Field(foreign_key = "user.id", primary_key = True) 
    company_id: int = Field(foreign_key = "company.id", primary_key = True)
    interested: bool
    user: User = Relationship(back_populates="interetsed_companies")
    company: Company = Relationship(back_populates="interested_users")
