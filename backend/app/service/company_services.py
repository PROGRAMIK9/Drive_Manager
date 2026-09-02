from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import SessionDep, get_async_session
from app.schema.models import CompanyCreate, CompanyRead, CompanyUpdate
from app.schema.database import Company

class CompanyService:
    def __init__(self, session: SessionDep):
        self.session = session

    async def add(self, company_create: CompanyCreate)->CompanyRead:
        company = Company(
            **company_create.model_dump()
        )
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def update(self, company_id: int, company_details: CompanyUpdate)-> CompanyRead:
        company = await self.session.get(Company, company_id)
        if not company: 
            raise HTTPException(status_code= 422, detail = "Company details were not added")
        company_data = company_details.model_dump(exclude_none = True, exclude_unset = True)
        company.sqlmodel_update(company_data)
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def interest(self):
        pass

    async def delete(self):
        pass

    async def get_all(self):
        pass

    async def get_one(self):
        pass

async def get_company_service(
        session: AsyncSession = Depends(get_async_session)
)->AsyncGenerator[CompanyService, None]:
    service = CompanyService(session)
    yield service


CompanyServiceDep = Annotated[CompanyService, Depends(get_company_service)]