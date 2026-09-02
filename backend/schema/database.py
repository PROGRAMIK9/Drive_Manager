from enum import Enum
from datetime import datetime
from sqlmodel import Field, SQLModel


class Process(Enum):
    online_assesment = "online_assesment"
    interview = "interview"
    ppt = "ppt"

    
class Company(SQLModel, table = True):
    id: int = Field(default = None, primary_key = True)
    name: str
    process: Process
    location: str
    date: datetime
    considered: bool

class User(SQLModel, table = True):
    id: int = Field(default = None, primary_key = True)
    name: str
    email: str
    hashed_password: str
    role: str

class Interested(SQLModel, table = True):
    id: int = Field(default = None, primary_key = True)
    user_id: int = Field(foreign_key = "user.id") 
    company_id: int = Field(foreign_key = "company.id")
    interested: bool