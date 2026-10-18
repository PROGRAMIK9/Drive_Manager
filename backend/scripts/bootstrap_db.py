"""Initialize a brand-new database and then keep it migrated with Alembic."""
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlmodel import SQLModel

from app.database.database import engine
from app.schema import database as _models  # noqa: F401 - registers SQLModel tables


ROOT = Path(__file__).resolve().parents[1]


async def initialize_empty_database() -> bool:
    async with engine.begin() as connection:
        table_names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        if "alembic_version" in table_names:
            return False
        if table_names:
            raise RuntimeError(
                "Database contains tables but has no Alembic revision. "
                "Refusing to stamp an unverified existing database."
            )
        await connection.run_sync(SQLModel.metadata.create_all)
        return True


def main() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    initialized = asyncio.run(initialize_empty_database())
    if initialized:
        command.stamp(config, "head")
    else:
        command.upgrade(config, "head")


if __name__ == "__main__":
    main()
