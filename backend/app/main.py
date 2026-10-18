from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from .router.company import router as Company
from .router.user import router as User
from .config.config import app_settings

@asynccontextmanager
async def lifespan(app:FastAPI):
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def get_root():
    return {"Detail":"It works"}

@app.get("/api/health")
async def health_check():
    return {"detail": "Health Check Successful"}

app.include_router(User)
app.include_router(Company)

