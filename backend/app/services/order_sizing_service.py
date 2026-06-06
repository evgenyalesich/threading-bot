from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_UP

from app.services.binance_market_service import BinanceMarketService


@dataclass
class SizingResult:
    quantity: float | None
    price: float | None = None
    error: str | None = None


class OrderSizingService:
    def __init__(self, market_service: BinanceMarketService) -> None:
        self._market_service = market_service

    async def size_order(
        self,
        symbol: str,
        market: str,
        quote_amount: float,
        price: float | None,
        leverage: int | None = None,
    ) -> SizingResult:
        if quote_amount <= 0:
            return SizingResult(quantity=None, price=price, error="quote_amount_invalid")
        if not price or price <= 0:
            return SizingResult(quantity=None, price=price, error="price_required")

        pairs = await self._market_service.list_pairs(market)
        pair = next((item for item in pairs if item.get("symbol") == symbol), None)
        if not pair:
            return SizingResult(quantity=None, price=price, error="symbol_not_found")

        step_size = float(pair.get("step_size") or 0)
        min_qty = float(pair.get("min_qty") or 0)
        max_qty = float(pair.get("max_qty") or 0)
        min_notional = float(pair.get("min_notional") or 0)

        # Spot quote amount is the notional. For futures it represents allocated
        # margin, so leverage expands it into the Binance position notional.
        safe_leverage = max(int(leverage or 1), 1) if market == "futures" else 1
        notional_amount = quote_amount * safe_leverage

        # Every symbol has its own minQty/minNotional. In auto-sizing mode,
        # raise the position to the smallest exchange-valid size instead of
        # rejecting an otherwise valid signal.
        minimum_notional = max(min_notional, min_qty * price)
        target_notional = max(notional_amount, minimum_notional)
        raw_qty = target_notional / price
        sized_qty = raw_qty

        if step_size > 0:
            sized_qty = self._ceil_to_step(raw_qty, step_size)

        if min_qty and sized_qty < min_qty:
            sized_qty = self._ceil_to_step(min_qty, step_size) if step_size > 0 else min_qty
        if max_qty and sized_qty > max_qty:
            return SizingResult(quantity=None, price=price, error="max_qty")
        if min_notional and sized_qty * price < min_notional:
            sized_qty = self._ceil_to_step(min_notional / price, step_size) if step_size > 0 else min_notional / price
        if sized_qty <= 0:
            return SizingResult(quantity=None, price=price, error="qty_too_small")
        tick_size = float(pair.get("tick_size") or 0)
        normalized_price = self._floor_to_step(float(price), tick_size) if tick_size > 0 else float(price)
        return SizingResult(quantity=sized_qty, price=normalized_price, error=None)

    async def normalize_order(
        self,
        symbol: str,
        market: str,
        quantity: float | None,
        price: float | None,
    ) -> SizingResult:
        pairs = await self._market_service.list_pairs(market)
        pair = next((item for item in pairs if item.get("symbol") == symbol), None)
        if not pair:
            return SizingResult(quantity=quantity, price=price, error="symbol_not_found")
        step_size = float(pair.get("step_size") or 0)
        tick_size = float(pair.get("tick_size") or 0)
        min_qty = float(pair.get("min_qty") or 0)
        qty = float(quantity) if quantity is not None else None
        px = float(price) if price is not None else None
        if qty is not None and step_size > 0:
            qty = self._floor_to_step(qty, step_size)
        if px is not None and tick_size > 0:
            px = self._floor_to_step(px, tick_size)
        if qty is not None and min_qty and qty < min_qty:
            return SizingResult(quantity=None, price=px, error="min_qty")
        return SizingResult(quantity=qty, price=px, error=None)

    def _floor_to_step(self, value: float, step: float) -> float:
        step_dec = Decimal(str(step))
        value_dec = Decimal(str(value))
        if step_dec == 0:
            return float(value_dec)
        units = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
        sized = units * step_dec
        return float(sized)

    def _ceil_to_step(self, value: float, step: float) -> float:
        step_dec = Decimal(str(step))
        value_dec = Decimal(str(value))
        if step_dec == 0:
            return float(value_dec)
        units = (value_dec / step_dec).to_integral_value(rounding=ROUND_UP)
        return float(units * step_dec)
