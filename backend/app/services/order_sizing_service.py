from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from app.services.binance_market_service import BinanceMarketService


@dataclass
class SizingResult:
    quantity: float | None
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
    ) -> SizingResult:
        if quote_amount <= 0:
            return SizingResult(quantity=None, error="quote_amount_invalid")
        if not price or price <= 0:
            return SizingResult(quantity=None, error="price_required")

        pairs = await self._market_service.list_pairs(market)
        pair = next((item for item in pairs if item.get("symbol") == symbol), None)
        if not pair:
            return SizingResult(quantity=None, error="symbol_not_found")

        step_size = float(pair.get("step_size") or 0)
        min_qty = float(pair.get("min_qty") or 0)
        max_qty = float(pair.get("max_qty") or 0)
        min_notional = float(pair.get("min_notional") or 0)

        # If we size by quote amount, the most actionable user feedback is the
        # minimum quote they need. Check notional against quote first.
        if min_notional and quote_amount < min_notional:
            return SizingResult(quantity=None, error="min_notional")

        raw_qty = quote_amount / price
        sized_qty = raw_qty

        if step_size > 0:
            sized_qty = self._floor_to_step(raw_qty, step_size)

        if min_qty and sized_qty < min_qty:
            return SizingResult(quantity=None, error="min_qty")
        if max_qty and sized_qty > max_qty:
            sized_qty = max_qty
        if min_notional and sized_qty * price < min_notional:
            return SizingResult(quantity=None, error="min_notional")
        if sized_qty <= 0:
            return SizingResult(quantity=None, error="qty_too_small")

        return SizingResult(quantity=sized_qty, error=None)

    def _floor_to_step(self, value: float, step: float) -> float:
        step_dec = Decimal(str(step))
        value_dec = Decimal(str(value))
        if step_dec == 0:
            return float(value_dec)
        units = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
        sized = units * step_dec
        return float(sized)
