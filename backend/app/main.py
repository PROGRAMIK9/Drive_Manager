from fastapi import FastAPI
from contextlib import asynccontextmanager

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