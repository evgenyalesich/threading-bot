from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import Settings


class DatabaseSessionManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine = create_async_engine(
            settings.database_url,
            future=True,
            echo=settings.debug,
        )
        self._sessionmaker = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._sessionmaker

    async def dispose(self) -> None:
        await self._engine.dispose()
