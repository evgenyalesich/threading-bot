from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy_run import StrategyRun
from app.repositories.base_repository import BaseRepository


class StrategyRunRepository(BaseRepository[StrategyRun]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StrategyRun)

    async def list_recent(self, limit: int = 50) -> list[StrategyRun]:
        stmt = select(StrategyRun).order_by(StrategyRun.started_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
