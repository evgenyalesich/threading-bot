from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.repositories.base_repository import BaseRepository


class TradeRepository(BaseRepository[Trade]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Trade)

    async def list_recent(self, limit: int = 50) -> list[Trade]:
        stmt = select(Trade).order_by(Trade.opened_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
