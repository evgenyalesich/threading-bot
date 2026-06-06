from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.models.order import Order
from app.models.signal import Signal
from app.repositories.order_repository import OrderRepository
from app.repositories.symbol_mapping_repository import SymbolMappingRepository
from app.schemas.order_create import OrderCreate
from app.exchanges.binance_exchange import BinanceExchange
from app.services.binance_credentials import resolve_api_credentials
from app.services.binance_market_service import BinanceMarketService
from app.services.execution_service import ExecutionService
from app.services.order_sizing_service import OrderSizingService
from app.services.symbol_resolver_service import SymbolResolverService


@dataclass(slots=True)
class SignalExecutionConfig:
    symbol: str
    timeframe: str
    market: str = "spot"
    trade_env: str = "testnet"
    order_type: str = "MARKET"
    quantity: float = 0.001
    quote_amount: float | None = None
    auto_quantity: bool = False
    attach_orders: bool = True
    auto_breakeven: bool = True
    leverage: int | None = None


@dataclass(slots=True)
class SignalExecutionResult:
    status: str
    order: Order | None = None
    error: str | None = None


class SignalExecutionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute(
        self,
        session: AsyncSession,
        signal: Signal,
        config: SignalExecutionConfig,
    ) -> SignalExecutionResult:
        market = config.market.lower()
        trade_env = config.trade_env.lower()
        trade_settings = self._settings.model_copy(update={"binance_testnet": trade_env == "testnet"})

        if market == "spot" and signal.signal_type == "short":
            return SignalExecutionResult(status="spot_short_not_supported", error="spot_short_not_supported")

        mapping_repo = SymbolMappingRepository(session)
        resolver = SymbolResolverService(mapping_repo)
        resolved_symbol = await resolver.resolve(config.symbol.upper(), market)
        if not resolved_symbol:
            return SignalExecutionResult(status="symbol_not_mapped", error="symbol_not_mapped")

        quantity = config.quantity if config.quantity > 0 else self._settings.default_order_quantity
        sizing_service = OrderSizingService(BinanceMarketService(trade_settings))
        if config.auto_quantity or config.quote_amount is not None:
            if config.quote_amount is None:
                return SignalExecutionResult(status="order_sizing_error", error="quote_amount_required")
            sizing = await sizing_service.size_order(
                resolved_symbol,
                market,
                config.quote_amount,
                signal.entry_price,
                leverage=config.leverage,
            )
            if sizing.error:
                return SignalExecutionResult(status="order_sizing_error", error=sizing.error)
            quantity = sizing.quantity or quantity
            normalized_price = sizing.price or signal.entry_price
        else:
            normalized = await sizing_service.normalize_order(
                resolved_symbol,
                market,
                quantity,
                signal.entry_price,
            )
            if normalized.error:
                return SignalExecutionResult(status="order_sizing_error", error=normalized.error)
            quantity = normalized.quantity or quantity
            normalized_price = normalized.price or signal.entry_price

        order_repo = OrderRepository(session)
        exchange = None
        api_key, api_secret, _ = resolve_api_credentials(self._settings, trade_env, market)
        if api_key and api_secret:
            exchange = BinanceExchange(trade_settings)
        execution_service = ExecutionService(order_repo, exchange)
        trade_plan = signal.meta.get("trade_plan") if signal.meta else None
        effective_order_type = (
            str(trade_plan.get("entry_order_type"))
            if trade_plan and trade_plan.get("entry_order_type")
            else config.order_type
        )
        if market != "futures" and effective_order_type.upper() == "STOP_MARKET":
            effective_order_type = "MARKET"
        order_create = OrderCreate(
            exchange="binance",
            market=market,
            symbol=resolved_symbol,
            side="BUY" if signal.signal_type == "long" else "SELL",
            order_type=effective_order_type,
            quantity=quantity,
            trade_env=config.trade_env,
            quote_amount=config.quote_amount,
            auto_quantity=config.auto_quantity,
            timeframe=config.timeframe,
            signal_id=signal.id,
            price=normalized_price,
            leverage=config.leverage,
            stop_loss=(trade_plan.get("stop_loss") if trade_plan else signal.stop_loss),
            take_profit=(trade_plan.get("take_profit") if trade_plan else signal.take_profit),
            take_levels=(trade_plan.get("take_levels") if trade_plan else None),
            breakeven_at=(trade_plan.get("breakeven_at") if trade_plan else None),
            auto_breakeven=config.auto_breakeven,
            attach_orders=config.attach_orders,
        )
        order = await execution_service.place_order(order_create, market=market)
        status = "order_submitted" if order.status == "submitted" else "order_stored"
        return SignalExecutionResult(status=status, order=order)
