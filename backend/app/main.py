from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_session_manager
from app.api.router import api_router
from app.core.settings import Settings
from app.db.init import init_db


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = get_session_manager()
    if settings.db_auto_create:
        await init_db(session_manager.engine)
    yield
    await session_manager.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    static_dir = os.getenv("STATIC_DIR")
    if static_dir and Path(static_dir).exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
