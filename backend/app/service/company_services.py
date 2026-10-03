from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.database import SessionDep, get_async_session
from app.schema.models import CompanyCreate, CompanyRead, CompanyUpdate
from app.schema.database import Company, Interested, User
from app.service.mail_services import queue_event_reminder, queue_interest_notification
from app.service.user_services import CurrentUserDep

class CompanyService:
    def __init__(self, session: SessionDep, user: CurrentUserDep):
        self.session = session
        self.user = user

    def _require_spc_role(self) -> None:
        if self.user.role.value != "SPC":
            raise HTTPException(
                status_code=403,
                detail="Only users with the SPC role can add or update companies",
            )

    async def add(self, company_create: CompanyCreate)->CompanyRead:
        self._require_spc_role()
        company = Company(
            **company_create.model_dump()
        )
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)

        users = (await self.session.scalars(select(User))).all()
        self.session.add_all(
            Interested(
                company_id=company.id,
                user_id=existing_user.id,
                interested=False,
            )
            for existing_user in users
        )
        await self.session.commit()
        queue_event_reminder(company.id, company.date)
        return company

    async def update(self, company_id: int, company_details: CompanyUpdate)-> CompanyRead:
        self._require_spc_role()
        company = await self.session.get(Company, company_id)
        if not company: 
            raise HTTPException(status_code= 422, detail = "Company not found. Please add the company details first")
        company_data = company_details.model_dump(exclude_none = True, exclude_unset = True)
        company.sqlmodel_update(company_data)
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        queue_event_reminder(company.id, company.date)
        return company

    async def toggle_interest(self, company_id: int):
        company = await self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company does not exist yet")

        interest = await self.session.scalar(
            select(Interested).where(
                Interested.company_id == company_id,
                Interested.user_id == self.user.id,
            )
        )
        if not interest:
            interest = Interested(
                company_id=company_id,
                user_id=self.user.id,
                interested=True,
            )
            self.session.add(interest)
            await self.session.commit()
            await self.session.refresh(interest)
            queue_interest_notification(
                recipient=self.user.email,
                recipient_name=self.user.name,
                company_name=company.name,
                company_location=company.location,
                company_date=company.date,
            )
            return interest

        interest.interested = not interest.interested
        await self.session.commit()
        await self.session.refresh(interest)
        if interest.interested:
            queue_interest_notification(
                recipient=self.user.email,
                recipient_name=self.user.name,
                company_name=company.name,
                company_location=company.location,
                company_date=company.date,
            )
        return interest

    async def get_saved(self):
        return (
            await self.session.scalars(
                select(Company)
                .join(Interested, Interested.company_id == Company.id)
                .where(
                    Interested.user_id == self.user.id,
                    Interested.interested.is_(True),
                )
            )
        ).all()

    async def get_interested_users(self, company_id: int):
        self._require_spc_role()
        company = await self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company does not exist yet")
        return (
            await self.session.scalars(
                select(User)
                .join(Interested, Interested.user_id == User.id)
                .where(
                    Interested.company_id == company_id,
                    Interested.interested.is_(True),
                )
            )
        ).all()

    async def delete(self, company_id: int):
        company = await self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code= 404, detail = "Company does not exist yet")
        await self.session.delete(company)
        await self.session.commit()

    async def get_all(self):
        rows = (
            await self.session.execute(
                select(Company, Interested.interested)
                .outerjoin(
                    Interested,
                    (Interested.company_id == Company.id)
                    & (Interested.user_id == self.user.id),
                )
            )
        ).all()
        if not rows:
            raise HTTPException(status_code= 422, detail = "Company details were not added")
        return [
            CompanyRead(**company.model_dump(), interested=bool(interested))
            for company, interested in rows
        ]

    async def get_one(self, company_id: int):
        company = await self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code= 422, detail = "Company details were not added")
        return company

async def get_company_service(
    user: CurrentUserDep,
    session: AsyncSession = Depends(get_async_session),
)->AsyncGenerator[CompanyService, None]:
    service = CompanyService(session, user)
    yield service


CompanyServiceDep = Annotated[CompanyService, Depends(get_company_service)]