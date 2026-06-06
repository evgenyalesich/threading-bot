from __future__ import annotations

from app.services.indicator_service import IndicatorService
from app.strategies.strategy_filters import StrategyFilters
from app.strategies.three_screens_strategy import ThreeScreensStrategy


class ThreeScreensLiquidityStrategy(ThreeScreensStrategy):
    """Three Screens with live order-book confirmation.

    The base signal is mentor-style Three Screens:
    H1 EMA26 trend, M15 oscillator pullback, stop-entry above/below the signal candle.
    When live order-book data is provided in context["order_book"], liquidity pressure
    adjusts confidence and can invalidate trades with bad spread or strong opposite walls.
    """

    name = "three_screens_liquidity"
    requires_order_book = True

    def __init__(
        self,
        indicator_service: IndicatorService,
        trend_timeframe: str = "1h",
        h1_timeframe: str = "15m",
        filters: StrategyFilters | None = None,
    ) -> None:
        super().__init__(
            indicator_service=indicator_service,
            trend_timeframe=trend_timeframe,
            h1_timeframe=h1_timeframe,
            filters=filters,
        )

    def _evaluate(self, data, context: dict | None = None):
        payload, debug = super()._evaluate(data, context)
        if not payload:
            return payload, debug

        ctx = context or {}
        order_book = ctx.get("order_book") or {}
        liquidity = self._score_liquidity(payload["signal_type"], order_book)
        debug["liquidity"] = liquidity

        meta = payload.setdefault("meta", {})
        meta["strategy"] = self.name
        meta["setup_state"] = "ready_to_trigger"
        meta["liquidity"] = liquidity

        # Historical backtests usually do not have archived DOM data. Do not fake it.
        if not liquidity["available"]:
            payload["confidence"] = min(float(payload["confidence"]), 0.82)
            payload["rationale"] = f"{payload.get('rationale', '')}; DOM=not_available"
            return payload, debug

        if liquidity["spread_bad"]:
            debug["reasons"].append("spread_too_wide")
            return None, debug

        if liquidity["opposite_pressure"]:
            debug["reasons"].append("liquidity_against_trade")
            return None, debug

        confidence = float(payload["confidence"])
        confidence += liquidity["confidence_delta"]
        confidence = max(0.0, min(confidence, 0.96))
        if confidence < self._filters.min_confidence:
            debug["reasons"].append("confidence_below_min_after_liquidity")
            return None, debug

        payload["confidence"] = confidence
        payload["rationale"] = (
            f"{payload.get('rationale', '')}; "
            f"DOM={liquidity['pressure']}, imbalance={liquidity['imbalance']:.2f}, "
            f"spread={liquidity['spread_pct']:.4f}%"
        )
        return payload, debug

    def _score_liquidity(self, side: str, order_book: dict) -> dict:
        bid_notional = float(order_book.get("bid_notional") or 0.0)
        ask_notional = float(order_book.get("ask_notional") or 0.0)
        imbalance = float(order_book.get("imbalance") or 0.0)
        spread_pct = float(order_book.get("spread_pct") or 0.0)
        pressure = str(order_book.get("pressure") or "unknown")
        available = bid_notional > 0 and ask_notional > 0
        aligned = (side == "long" and imbalance > 0.08) or (side == "short" and imbalance < -0.08)
        opposite = (side == "long" and imbalance < -0.28) or (side == "short" and imbalance > 0.28)
        neutral = not aligned and not opposite
        confidence_delta = 0.0
        if aligned:
            confidence_delta += 0.08
        elif neutral:
            confidence_delta += 0.02
        if abs(imbalance) > 0.45 and aligned:
            confidence_delta += 0.04
        spread_bad = available and spread_pct > 0.08
        return {
            "available": available,
            "pressure": pressure,
            "bid_notional": bid_notional,
            "ask_notional": ask_notional,
            "imbalance": imbalance,
            "spread_pct": spread_pct,
            "aligned": aligned,
            "opposite_pressure": opposite,
            "spread_bad": spread_bad,
            "confidence_delta": confidence_delta,
        }
