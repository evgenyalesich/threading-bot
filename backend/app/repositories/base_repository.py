from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def get(self, entity_id: int) -> ModelT | None:
        result = await self._session.execute(
            select(self._model).where(self._model.id == entity_id)
        )
        return result.scalars().first()

    async def list(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self._session.execute(select(self._model).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def update(self, entity: ModelT, data: dict) -> ModelT:
        for key, value in data.items():
            setattr(entity, key, value)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self._session.delete(entity)
        await self._session.commit()
