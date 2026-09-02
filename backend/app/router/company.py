from fastapi import APIRouter
from app.service.company_services import CompanyServiceDep
from app.schema.models import CompanyCreate, CompanyUpdate, CompanyRead
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
async def delete_company(company_id: int):
    pass

@router.patch("/interested/{company_id}")
async def toggle_interest(company_id: int):
    pass


@router.get("/{company_id}")
async def get_company(company_id:int):
    pass

@router.get("/")
async def get_all():
    pass
