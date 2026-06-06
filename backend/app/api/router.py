from fastapi import APIRouter

from app.api.routes.analysis import router as analysis_router
from app.api.routes.account import router as account_router
from app.api.routes.auth import router as auth_router
from app.api.routes.automation import router as automation_router
from app.api.routes.health import router as health_router
from app.api.routes.market import router as market_router
from app.api.routes.orders import router as orders_router
from app.api.routes.signals import router as signals_router
from app.api.routes.symbols import router as symbols_router
from app.api.routes.stream import router as stream_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(account_router, prefix="/account", tags=["account"])
api_router.include_router(automation_router, prefix="/automation", tags=["automation"])
api_router.include_router(market_router, prefix="/market", tags=["market"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
api_router.include_router(signals_router, prefix="/signals", tags=["signals"])
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
api_router.include_router(symbols_router, prefix="/symbols", tags=["symbols"])
api_router.include_router(stream_router, tags=["stream"])
