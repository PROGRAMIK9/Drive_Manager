from enum import Enum
from datetime import datetime
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

class Interested(SQLModel, table = True):
    user_id: int = Field(foreign_key = "user.id", primary_key = True) 
    company_id: int = Field(foreign_key = "company.id", primary_key = True)
    interested: bool
    user: User = Relationship(back_populates="interetsed_companies")
    company: Company = Relationship(back_populates="interested_users")
