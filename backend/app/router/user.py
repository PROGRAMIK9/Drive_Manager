from fastapi import APIRouter

router = APIRouter(prefix="/user", tags = ["User"])

@router.post("/register")
async def sign_up():
    pass

@router.post("/login")
async def sign_in():
    pass

@router.get("/token")
async def get_token():
    pass