from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.schema.models import Token, UserCreate, UserRead
from app.service.user_services import UserServiceDep

router = APIRouter(prefix="/user", tags = ["User"])

@router.post("/register")
async def sign_up(user_details: UserCreate, service: UserServiceDep) -> UserRead:
    return await service.register(user_details)

@router.post("/login")
async def sign_in(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserServiceDep = None,
) -> Token:
    return await service.login(form_data)

@router.post("/token")
async def get_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserServiceDep = None,
) -> Token:
    return await service.login(form_data)