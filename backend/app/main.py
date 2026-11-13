from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
import asyncio
from fastapi.middleware.cors import CORSMiddleware

from .router.company import router as Company
from .router.user import router as User
from .router.placement_review import router as PlacementReview
from .router.gmail_integration import router as GmailIntegration
from .router.placement_campaigns import router as PlacementCampaigns
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

api = FastAPI(lifespan=lifespan)

@api.get("/")
async def get_root():
    return {"Detail": "It works"}

@api.get("/api/health", dependencies=[Depends(due_reminders_dependency)])
async def health_check():
    return {"detail": "Health Check Successful"}

api.include_router(User)
api.include_router(Company)
api.include_router(PlacementReview)
api.include_router(GmailIntegration)
api.include_router(PlacementCampaigns)

# Wrap the complete FastAPI app so CORS headers are also added to unhandled
# server-error responses. This lets the browser surface the actual API error.
app = CORSMiddleware(
    app=api,
    allow_origins=app_settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

