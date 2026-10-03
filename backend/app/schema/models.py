from datetime import datetime, timezone
from pydantic import EmailStr
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field

class UserBase(SQLModel):
    name: str
    email:EmailStr
    role:str

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int

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
    considered: bool = False

class CompanyCreate(CompanyBase):
    pass

class CompanyRead(CompanyBase):
    id:int
    interested:bool = False

class CompanyUpdate(CompanyBase):
    pass