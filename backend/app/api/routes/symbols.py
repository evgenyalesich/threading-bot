from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.symbol_mapping import SymbolMapping
from app.repositories.symbol_mapping_repository import SymbolMappingRepository
from app.schemas.symbol_mapping_create import SymbolMappingCreate
from app.schemas.symbol_mapping_read import SymbolMappingRead
from app.schemas.symbol_mapping_update import SymbolMappingUpdate
from app.services.symbol_resolver_service import SymbolResolverService


router = APIRouter()


@router.get("")
async def list_mappings(
    market: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[SymbolMappingRead]:
    repo = SymbolMappingRepository(session)
    normalized_market = market.lower() if market else None
    mappings = await repo.list_all(market=normalized_market)
    return [SymbolMappingRead.model_validate(item) for item in mappings]


@router.post("")
async def create_mapping(
    payload: SymbolMappingCreate,
    session: AsyncSession = Depends(get_db_session),
) -> SymbolMappingRead:
    repo = SymbolMappingRepository(session)
    data = payload.model_dump()
    data["yfinance_symbol"] = data["yfinance_symbol"].upper()
    data["binance_symbol"] = data["binance_symbol"].replace("-", "").upper()
    data["market"] = data["market"].lower()
    entity = SymbolMapping(**data)
    try:
        entity = await repo.add(entity)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Mapping already exists") from exc
    return SymbolMappingRead.model_validate(entity)


@router.put("/{mapping_id}")
async def update_mapping(
    mapping_id: int,
    payload: SymbolMappingUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SymbolMappingRead:
    repo = SymbolMappingRepository(session)
    mapping = await repo.get(mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    data = payload.model_dump(exclude_unset=True)
    if "binance_symbol" in data and data["binance_symbol"]:
        data["binance_symbol"] = data["binance_symbol"].replace("-", "").upper()
    if "market" in data and data["market"]:
        data["market"] = data["market"].lower()
    updated = await repo.update(mapping, data)
    return SymbolMappingRead.model_validate(updated)


@router.delete("/{mapping_id}")
async def delete_mapping(
    mapping_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = SymbolMappingRepository(session)
    mapping = await repo.get(mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await repo.delete(mapping)
    return {"status": "deleted"}


@router.get("/resolve")
async def resolve_mapping(
    symbol: str,
    market: str = "spot",
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = SymbolMappingRepository(session)
    resolver = SymbolResolverService(repo)
    resolved = await resolver.resolve(symbol, market.lower())
    if not resolved:
        return {"status": "not_found"}
    return {"status": "ok", "symbol": resolved}
