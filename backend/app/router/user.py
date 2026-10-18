from fastapi import APIRouter

from app.schema.models import GoogleCredential, Token, UserRead, UserRoleUpdate
from app.service.user_services import CurrentUserDep, UserServiceDep

router = APIRouter(prefix="/user", tags = ["User"])

@router.post("/google", response_model=Token)
async def google_sign_in(payload: GoogleCredential, service: UserServiceDep):
    return await service.login_with_google(payload.credential)

@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUserDep):
    return UserRead(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.value,
    )

@router.get("/", response_model=list[UserRead])
async def list_users(user: CurrentUserDep, service: UserServiceDep):
    return await service.list_users(user)

@router.patch("/{user_id}/role", response_model=UserRead)
async def update_user_role(user_id: int, payload: UserRoleUpdate, user: CurrentUserDep, service: UserServiceDep):
    return await service.update_user_role(user, user_id, payload.role)
