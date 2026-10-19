from fastapi import APIRouter, Depends

from app.schema.models import GoogleCredential, Token, UserRead, UserRoleUpdate
from app.service.user_services import CurrentUserDep, UserServiceDep
from app.service.mail_services import due_reminders_dependency

router = APIRouter(
    prefix="/user",
    tags=["User"],
    dependencies=[Depends(due_reminders_dependency)],
)

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
        year_of_passing=user.year_of_passing,
    )

@router.get("/", response_model=list[UserRead])
async def list_users(user: CurrentUserDep, service: UserServiceDep):
    return await service.list_users(user)

@router.patch("/{user_id}/role", response_model=UserRead)
async def update_user_role(user_id: int, payload: UserRoleUpdate, user: CurrentUserDep, service: UserServiceDep):
    return await service.update_user_role(user, user_id, payload.role, payload.year_of_passing)
