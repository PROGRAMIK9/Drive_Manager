from datetime import datetime
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
