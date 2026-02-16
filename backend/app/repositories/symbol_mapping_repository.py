from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.symbol_mapping import SymbolMapping
from app.repositories.base_repository import BaseRepository


class SymbolMappingRepository(BaseRepository[SymbolMapping]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SymbolMapping)

    async def get_by_yfinance(self, yfinance_symbol: str, market: str) -> SymbolMapping | None:
        stmt = select(SymbolMapping).where(
            SymbolMapping.yfinance_symbol == yfinance_symbol,
            SymbolMapping.market == market,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_all(self, market: str | None = None) -> list[SymbolMapping]:
        stmt = select(SymbolMapping)
        if market:
            stmt = stmt.where(SymbolMapping.market == market)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
