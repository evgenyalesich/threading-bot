from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.repositories.signal_repository import SignalRepository
from app.schemas.signal_read import SignalRead


router = APIRouter()


@router.get("")
async def list_signals(
    symbol: str | None = None,
    timeframe: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
) -> list[SignalRead]:
    signal_repo = SignalRepository(session)
    normalized_symbol = symbol.upper() if symbol else None
    signals = await signal_repo.list_recent(
        symbol=normalized_symbol,
        timeframe=timeframe,
        limit=limit,
    )
    return [SignalRead.model_validate(signal) for signal in signals]


@router.get("/{signal_id}")
async def get_signal(
    signal_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> SignalRead:
    signal_repo = SignalRepository(session)
    signal = await signal_repo.get(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return SignalRead.model_validate(signal)
