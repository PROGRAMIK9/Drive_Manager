from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    pass

app = FastAPI(title="Company Drives", lifespan = lifespan)
