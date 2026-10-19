from datetime import datetime, timedelta, timezone
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_async_session
from app.helper.utils import decode_jwt, encode_jwt
from app.schema.database import Company, Interested, Role, User
from app.schema.models import Token, UserRead
from app.config.config import google_auth_settings, token_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/google", auto_error=False)
logger = logging.getLogger(__name__)
class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def login_with_google(self, credential: str) -> Token:
        try:
            from google.auth.transport.urllib3 import Request
            import urllib3
            from google.oauth2 import id_token

            claims = id_token.verify_oauth2_token(
                credential,
                Request(urllib3.PoolManager()),
                google_auth_settings.GOOGLE_CLIENT_ID,
            )
        except Exception as error:
            logger.exception("Google credential verification failed")
            raise HTTPException(status_code=401, detail="Google sign-in could not be verified") from error

        email = str(claims.get("email", "")).strip().lower()
        domain = google_auth_settings.RVCE_EMAIL_DOMAIN.strip().lower().lstrip("@").rstrip(".")
        if not claims.get("email_verified") or not domain or email.rsplit("@", 1)[-1] != domain:
            raise HTTPException(status_code=403, detail="Sign in with a verified RVCE email account")

        google_sub = claims.get("sub")
        if not google_sub:
            raise HTTPException(status_code=401, detail="Google account identity is missing")

        user = await self.session.scalar(select(User).where(User.google_sub == google_sub))
        if user is not None and user.email.lower() != email:
            raise HTTPException(status_code=409, detail="Google account email changed; contact an SPC")
        if user is None:
            user = await self.session.scalar(select(User).where(User.email == email))
            if user is not None and user.google_sub is not None:
                raise HTTPException(status_code=409, detail="This email is linked to a different Google account")
            role = Role.spc if email in google_auth_settings.spc_emails else Role.student
            user = User(
                name=str(claims.get("name") or email.split("@", 1)[0]),
                email=email,
                google_sub=google_sub,
                role=role,
                is_verified=True,
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            # Maintain interest rows for companies already on the board.
            companies = (await self.session.scalars(select(Company))).all()
            known_company_ids = set((await self.session.scalars(
                select(Interested.company_id).where(Interested.user_id == user.id)
            )).all())
            self.session.add_all(
                Interested(company_id=company.id, user_id=user.id, interested=False)
                for company in companies
                if company.id not in known_company_ids
            )
            await self.session.commit()
        else:
            # SPC assignments made by an existing SPC persist across logins; the email
            # allowlist bootstraps the first three SPC accounts for a fresh deployment.
            if email in google_auth_settings.spc_emails and user.role != Role.spc:
                user.role = Role.spc
                await self.session.commit()

        return self._issue_token(user)

    def _issue_token(self, user: User) -> Token:
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

    async def list_users(self, current_user: User) -> list[UserRead]:
        self._require_spc(current_user)
        users = (await self.session.scalars(select(User).order_by(User.name, User.email))).all()
        return [UserRead(id=u.id, name=u.name, email=u.email, role=u.role.value, year_of_passing=u.year_of_passing) for u in users]

    async def update_user_role(self, current_user: User, user_id: int, role_name: str, year_of_passing: int | None = None) -> UserRead:
        self._require_spc(current_user)
        try:
            role = Role(role_name.strip().upper())
        except (AttributeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Role must be SPC or STUDENT") from error
        user = await self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.role = role
        user.year_of_passing = year_of_passing
        await self.session.commit()
        await self.session.refresh(user)
        return UserRead(id=user.id, name=user.name, email=user.email, role=user.role.value, year_of_passing=user.year_of_passing)

    @staticmethod
    def _require_spc(current_user: User) -> None:
        if current_user.role != Role.spc:
            raise HTTPException(status_code=403, detail="Only SPC users can manage users")

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
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await service.get_current_user(token)

CurrentUserDep = Annotated[User, Depends(get_current_user)]


