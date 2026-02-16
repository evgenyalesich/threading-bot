from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Candle
from app.repositories.base_repository import BaseRepository


class CandleRepository(BaseRepository[Candle]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Candle)

    async def latest(self, symbol: str, timeframe: str, limit: int = 500) -> list[Candle]:
        stmt = (
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.open_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return list(reversed(rows))

    async def before(
        self,
        symbol: str,
        timeframe: str,
        before: datetime,
        limit: int = 500,
    ) -> list[Candle]:
        stmt = (
            select(Candle)
            .where(
                Candle.symbol == symbol,
                Candle.timeframe == timeframe,
                Candle.open_time < before,
            )
            .order_by(Candle.open_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return list(reversed(rows))

    async def upsert_many(self, records: list[dict]) -> int:
        if not records:
            return 0
        total = 0
        batch_size = 1000
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            stmt = insert(Candle).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "open_time"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "source": stmt.excluded.source,
                },
            )
            result = await self._session.execute(stmt)
            await self._session.commit()
            total += result.rowcount or 0
        return total
