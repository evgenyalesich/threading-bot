from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position import Position
from app.repositories.base_repository import BaseRepository


class PositionRepository(BaseRepository[Position]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Position)

    async def list_open(self) -> list[Position]:
        stmt = select(Position).where(Position.status == "open")
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
