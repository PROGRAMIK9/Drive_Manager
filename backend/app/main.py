from fastapi import FastAPI
from contextlib import asynccontextmanager

from .router.company import router as Company
from .router.user import router as User

from .database.database import create_db_and_tables

@asynccontextmanager
async def lifespan(app:FastAPI):
    print("🔍 Testing database connection...")
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def get_root():
    return {"Detail":"It works"}

@app.get("/api/health")
async def health_check():
    return {"detail": "Health Check Successful"}

app.include_router(User)
app.include_router(Company)

