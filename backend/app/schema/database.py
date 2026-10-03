from enum import Enum
from datetime import datetime
from pyclbr import Class
from sqlalchemy import DateTime
import sqlalchemy as sa
from sqlmodel import Column, Field, Relationship, SQLModel


class Process(Enum):
    online_assesment = "online_assesment"
    interview = "interview"
    ppt = "ppt"

class Role(Enum):
    spc = "SPC"
    student = "STUDENT"    

    
class Company(SQLModel, table = True):
    id: int = Field(default = None, primary_key = True)
    name: str
    process: Process
    location: str
    date: datetime
    considered: bool
    interested_users: list["Interested"] = Relationship(
        back_populates="company"
    )


class User(SQLModel, table = True):
    id: int = Field(default = None, primary_key = True)
    name: str
    email: str
    hashed_password: str
    role: Role = Field(sa_column=Column("role", sa.Enum(Role)))
    interetsed_companies: list["Interested"] = Relationship(
        back_populates="user"
    )

class Interested(SQLModel, table = True):
    user_id: int = Field(foreign_key = "user.id", primary_key = True) 
    company_id: int = Field(foreign_key = "company.id", primary_key = True)
    interested: bool
    user: User = Relationship(back_populates="interetsed_companies")
    company: Company = Relationship(back_populates="interested_users")