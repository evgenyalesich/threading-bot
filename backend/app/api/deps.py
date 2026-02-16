from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.session_manager import DatabaseSessionManager


settings = Settings()
_session_manager = DatabaseSessionManager(settings)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = _session_manager.session_factory()
    async with session_factory() as session:
        yield session


def get_session_manager() -> DatabaseSessionManager:
    return _session_manager
