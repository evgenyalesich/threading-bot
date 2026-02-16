from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.repositories.base_repository import BaseRepository


class SignalRepository(BaseRepository[Signal]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Signal)

    async def list_recent(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int = 50,
    ) -> list[Signal]:
        stmt = select(Signal)
        if symbol:
            stmt = stmt.where(Signal.symbol == symbol)
        if timeframe:
            stmt = stmt.where(Signal.timeframe == timeframe)
        stmt = stmt.order_by(Signal.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_times(self, symbol: str, timeframe: str) -> list:
        stmt = select(Signal.created_at).where(
            Signal.symbol == symbol,
            Signal.timeframe == timeframe,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
