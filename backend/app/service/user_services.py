from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_async_session
from app.helper.utils import decode_jwt, encode_jwt
from app.schema.database import Company, Interested, Role, User
from app.schema.models import RegistrationResponse, Token, UserCreate
from app.config.config import mail_settings, token_settings
from app.service.mail_services import queue_verification_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/token")
password_hash = PasswordHash.recommended()

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register(self, user_details: UserCreate) -> RegistrationResponse:
        existing_user = await self.session.scalar(
            select(User).where(User.email == user_details.email)
        )
        if existing_user:
            raise HTTPException(status_code=409, detail="Email is already registered")

        try:
            role = Role(user_details.role.upper())
        except (AttributeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Role must be SPC or STUDENT") from error

        user = User(
            name=user_details.name,
            email=user_details.email,
            role=role,
            hashed_password=password_hash.hash(user_details.password),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        companies = (await self.session.scalars(select(Company))).all()
        self.session.add_all(
            Interested(company_id=company.id, user_id=user.id, interested=False)
            for company in companies
        )
        await self.session.commit()
        verification_token = encode_jwt({
            "sub": str(user.id),
            "purpose": "email_verification",
            "exp": datetime.now(timezone.utc) + timedelta(
                minutes=mail_settings.VERIFICATION_TOKEN_EXPIRE_MINUTES
            ),
        })
        queue_verification_email(
            recipient=user.email,
            recipient_name=user.name,
            verification_url=f"{mail_settings.VERIFICATION_URL}?token={verification_token}",
        )
        return RegistrationResponse(
            message="Registration successful. Check your email to verify your account.",
            email=user.email,
        )

    async def login(self, form_data: OAuth2PasswordRequestForm) -> Token:
        user = await self.session.scalar(
            select(User).where(User.email == form_data.username)
        )
        if not user or not password_hash.verify(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_verified:
            raise HTTPException(status_code=403, detail="Please verify your email before logging in")

        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=token_settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        access_token = encode_jwt(
            {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
                "exp": expires_at,
            }
        )
        return Token(access_token=access_token)

    async def verify_email(self, token: str) -> dict:
        try:
            payload = decode_jwt(token)
            if payload.get("purpose") != "email_verification":
                raise ValueError("Invalid verification token")
            user_id = int(payload["sub"])
        except Exception as error:
            raise HTTPException(status_code=400, detail="Invalid or expired verification link") from error
        user = await self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_verified = True
        await self.session.commit()
        return {"message": "Email verified successfully. You can now log in."}

    async def get_current_user(self, token: str) -> User:
        credentials_error = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = decode_jwt(token)
            user_id = int(payload["sub"])
        except Exception as error:
            raise credentials_error from error

        user = await self.session.get(User, user_id)
        if not user:
            raise credentials_error
        return user

async def get_user_service(
    session: AsyncSession = Depends(get_async_session),
) -> UserService:
    return UserService(session)

UserServiceDep = Annotated[UserService, Depends(get_user_service)]

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    service: UserServiceDep,
) -> User:
    return await service.get_current_user(token)

CurrentUserDep = Annotated[User, Depends(get_current_user)]


