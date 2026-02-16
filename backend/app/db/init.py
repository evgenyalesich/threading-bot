from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base
from app import models  # noqa: F401


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
