from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.deps import get_session_manager
from app.api.router import api_router
from app.core.settings import Settings
from app.db.init import init_db
from app.services.automation_runtime import get_automation_runtime
from app.services.ui_auth_service import get_ui_auth_service


settings = Settings()


class UiAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        service = get_ui_auth_service()
        path = request.url.path
        if (
            not service.enabled()
            or not path.startswith(settings.api_prefix)
            or path.startswith(f"{settings.api_prefix}/auth")
            or path == f"{settings.api_prefix}/health"
        ):
            return await call_next(request)
        if service.verify_session_token(request.cookies.get("tb_session")):
            return await call_next(request)
        return JSONResponse({"detail": "ui_auth_required"}, status_code=401)


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = get_session_manager()
    if settings.db_auto_create:
        await init_db(session_manager.engine)
    automation_runtime = get_automation_runtime()
    automation_runtime.start()
    yield
    await automation_runtime.shutdown()
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
    app.add_middleware(UiAuthMiddleware)
    app.include_router(api_router, prefix=settings.api_prefix)

    static_dir = os.getenv("STATIC_DIR")
    if static_dir and Path(static_dir).exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
