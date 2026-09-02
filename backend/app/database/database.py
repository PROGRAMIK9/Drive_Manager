from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel
from sqlalchemy.orm import sessionmaker

from ..config.config import settings
from ..schema.database import Company, User, Interested

engine = create_async_engine(settings.POSTGRES_URL, echo = True)


async def create_db_and_tables():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all) 
    except Exception as e:
        print("DB ADRESS ERROR", e)

async def get_async_session():
    async_session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit = False
    )
    async with async_session() as session:
        yield session

SessionDep = Annotated[AsyncSession,Depends(get_async_session)]