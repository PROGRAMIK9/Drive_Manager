from typing import Annotated, AsyncGenerator
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app.database.database import SessionDep, get_async_session
from app.schema.models import CompanyCreate, CompanyRead, CompanyUpdate
from app.schema.database import Company, EventReminder, Interested, Process, Role, User
from app.service.mail_services import queue_event_reminder
from app.service.user_services import CurrentUserDep

class CompanyService:
    def __init__(self, session: SessionDep, user: CurrentUserDep, background_tasks: BackgroundTasks):
        self.session = session
        self.user = user
        self.background_tasks = background_tasks

    def _require_spc_role(self) -> None:
        if self.user.role.value != "SPC":
            raise HTTPException(
                status_code=403,
                detail="Only users with the SPC role can manage companies",
            )

    async def add(self, company_create: CompanyCreate)->CompanyRead:
        self._require_spc_role()
        if company_create.year_of_passing not in (2027, 2028):
            raise HTTPException(status_code=422, detail="Year of passing must be 2027 or 2028")
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
        await queue_event_reminder(self.session, company.id, company.date)
        return company

    async def update(self, company_id: int, company_details: CompanyUpdate)-> CompanyRead:
        self._require_spc_role()
        if company_details.year_of_passing is not None and company_details.year_of_passing not in (2027, 2028):
            raise HTTPException(status_code=422, detail="Year of passing must be 2027 or 2028")
        company = await self.session.get(Company, company_id)
        if not company: 
            raise HTTPException(status_code= 422, detail = "Company not found. Please add the company details first")
        company_data = company_details.model_dump(exclude_none = True, exclude_unset = True)
        company.sqlmodel_update(company_data)
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        await queue_event_reminder(self.session, company.id, company.date)
        return company

    async def toggle_interest(self, company_id: int):
        company = await self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company does not exist yet")
        if company.process == Process.send_mail and self.user.role != Role.spc:
            raise HTTPException(status_code=404, detail="Company does not exist yet")
        event_at = company.date.replace(tzinfo=ZoneInfo("Asia/Kolkata")) if company.date.tzinfo is None else company.date
        if event_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="Interest is closed because this event has already started")

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
            return interest

        interest.interested = not interest.interested
        await self.session.commit()
        await self.session.refresh(interest)
        return interest

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

    async def get_interest_summary(self):
        self._require_spc_role()
        rows = (await self.session.execute(
            select(Company, User)
            .outerjoin(
                Interested,
                (Interested.company_id == Company.id)
                & Interested.interested.is_(True),
            )
            .outerjoin(User, User.id == Interested.user_id)
            .order_by(Company.name, User.name)
        )).all()
        summary: dict[int, dict] = {}
        for company, user in rows:
            entry = summary.setdefault(company.id, {
                "company_id": company.id,
                "company_name": company.name,
                "process": company.process.value,
                "location": company.location,
                "date": company.date,
                "interested_users": [],
            })
            if user is None:
                continue
            entry["interested_users"].append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
            })
        return list(summary.values())

    async def delete(self, company_id: int):
        self._require_spc_role()
        company = await self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company does not exist yet")
        await self.session.execute(
            delete(Interested).where(Interested.company_id == company_id)
        )
        await self.session.execute(
            delete(EventReminder).where(EventReminder.company_id == company_id)
        )
        await self.session.delete(company)
        await self.session.commit()

    async def get_all(self):
        query = select(Company, Interested.interested).outerjoin(
            Interested,
            (Interested.company_id == Company.id)
            & (Interested.user_id == self.user.id),
        )
        if self.user.role != Role.spc:
            query = query.where(Company.process != Process.send_mail)
        if self.user.role != Role.spc:
            query = query.where(Company.year_of_passing == (self.user.year_of_passing or 2027))
        rows = (await self.session.execute(query)).all()
        if not rows:
            return []
        return [
            CompanyRead(**company.model_dump(), interested=bool(interested))
            for company, interested in rows
        ]

    async def get_one(self, company_id: int):
        company = await self.session.get(Company, company_id)
        if not company or (company.process == Process.send_mail and self.user.role != Role.spc):
            raise HTTPException(status_code= 422, detail = "Company details were not added")
        return company

async def get_company_service(
    user: CurrentUserDep,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
)->AsyncGenerator[CompanyService, None]:
    service = CompanyService(session, user, background_tasks)
    yield service


CompanyServiceDep = Annotated[CompanyService, Depends(get_company_service)]
