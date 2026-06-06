from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.repositories.base_repository import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Order)

    async def list_recent(self, limit: int = 50) -> list[Order]:
        stmt = select(Order).order_by(Order.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self, limit: int = 20) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.status.notin_(["closed", "filled", "cancelled", "rejected"]))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
