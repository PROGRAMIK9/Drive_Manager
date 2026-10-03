from fastapi import APIRouter
from app.service.company_services import CompanyServiceDep
from app.schema.models import CompanyCreate, CompanyUpdate, CompanyRead, UserRead
router = APIRouter(prefix="/company", tags = ["Company"])

@router.post("/", response_model = CompanyRead)
async def add_company(service: CompanyServiceDep, company_details: CompanyCreate):
    company = await service.add(company_create = company_details)
    return company
    

@router.patch("/{company_id}", response_model = CompanyRead)
async def update_company(company_id: int, company_details: CompanyUpdate,service: CompanyServiceDep):
    company = await service.update(company_id, company_details)
    return company

@router.delete("/{company_id}")
async def delete_company(company_id: int, service: CompanyServiceDep):
    await service.delete(company_id)
    return {"message": "Company deleted successfully"}

@router.patch("/interested/{company_id}")
async def toggle_interest(company_id: int, service: CompanyServiceDep):
    await service.toggle_interest(company_id)
    return {"message": "Company interest toggled successfully"}

@router.get("/saved", response_model=list[CompanyRead])
async def get_saved(service: CompanyServiceDep):
    return await service.get_saved()

@router.get("/{company_id}/interested-users", response_model=list[UserRead])
async def get_interested_users(company_id: int, service: CompanyServiceDep):
    return await service.get_interested_users(company_id)

@router.get("/{company_id}")
async def get_company(company_id:int, service: CompanyServiceDep):
    company = await service.get_one(company_id)
    return company

@router.get("/")
async def get_all(service: CompanyServiceDep):
    companies = await service.get_all()
    return companies
    
