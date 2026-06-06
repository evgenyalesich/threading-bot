from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.settings import Settings
from app.services.news_service import NewsService


router = APIRouter()
settings = Settings()


@router.get("/latest")
async def latest_news(
    limit: int = Query(default=30, ge=1, le=120),
    force: bool = Query(default=False),
) -> dict:
    service = NewsService(settings)
    events = await service.latest(limit=limit, force=force)
    return {
        "enabled": settings.news_enabled,
        "feeds": settings.news_feed_list(),
        "items": [event.as_dict() for event in events],
    }


@router.get("/context")
async def news_context(
    symbol: str = Query(default="BTCUSDT"),
    market: str = Query(default="futures"),
) -> dict:
    service = NewsService(settings)
    return await service.context(symbol=symbol, market=market)
