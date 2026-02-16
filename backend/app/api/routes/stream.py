from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_session_manager
from app.core.settings import Settings
from app.repositories.candle_repository import CandleRepository
from app.repositories.symbol_mapping_repository import SymbolMappingRepository
from app.services.market_stream_service import MarketStreamService
from app.services.symbol_resolver_service import SymbolResolverService


router = APIRouter()
settings = Settings()


@router.websocket("/stream")
async def stream_market(
    websocket: WebSocket,
    symbol: str,
    timeframe: str,
    market: str = "spot",
    binance_symbol: str | None = None,
    data_env: str = "real",
) -> None:
    await websocket.accept()
    market = market.lower()
    symbol = symbol.upper()
    session_manager = get_session_manager()

    session_factory = session_manager.session_factory()
    async with session_factory() as session:
        mapping_repo = SymbolMappingRepository(session)
        resolver = SymbolResolverService(mapping_repo)
        resolved = binance_symbol
        if not resolved:
            resolved = await resolver.resolve(symbol, market)
        if not resolved:
            resolved = symbol
        binance_symbol = resolved

        candle_repo = CandleRepository(session)
        effective_settings = settings.model_copy(update={"binance_testnet": data_env.lower() == "testnet"})
        stream_service = MarketStreamService(effective_settings)

        try:
            async for payload in stream_service.stream_klines(binance_symbol, timeframe, market):
                candle = stream_service.parse_kline(payload)
                if candle is None:
                    continue

                await websocket.send_json(
                    {
                        "type": "kline",
                        "symbol": symbol,
                        "binance_symbol": binance_symbol,
                        "timeframe": timeframe,
                        "data": {
                            **candle,
                            "open_time": candle["open_time"].isoformat(),
                        },
                    }
                )

                if candle["is_final"]:
                    await candle_repo.upsert_many(
                        [
                            {
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "open_time": candle["open_time"],
                                "open": candle["open"],
                                "high": candle["high"],
                                "low": candle["low"],
                                "close": candle["close"],
                                "volume": candle["volume"],
                                "source": "binance",
                            }
                        ]
                    )
        except WebSocketDisconnect:
            return
        except Exception as exc:
            await websocket.send_json({"type": "error", "message": f"Stream error: {exc}"})
            return
