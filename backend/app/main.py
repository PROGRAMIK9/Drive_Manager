from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
import asyncio
from fastapi.middleware.cors import CORSMiddleware

from .router.company import router as Company
from .router.user import router as User
from .router.placement_review import router as PlacementReview
from .router.gmail_integration import router as GmailIntegration
from .config.config import app_settings
from .service.mail_services import due_reminders_dependency
from .service.gmail_automation import gmail_automation_loop

@asynccontextmanager
async def lifespan(app:FastAPI):
    automation_task = asyncio.create_task(gmail_automation_loop(), name="gmail-automation")
    try:
        yield
    finally:
        automation_task.cancel()
        try:
            await automation_task
        except asyncio.CancelledError:
            pass

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

@app.get("/api/health", dependencies=[Depends(due_reminders_dependency)])
async def health_check():
    return {"detail": "Health Check Successful"}

app.include_router(User)
app.include_router(Company)
app.include_router(PlacementReview)
app.include_router(GmailIntegration)

