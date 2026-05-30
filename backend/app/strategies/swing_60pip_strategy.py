from __future__ import annotations

import pandas as pd

from app.services.indicator_service import IndicatorService
from app.strategies.three_screens_strategy import ThreeScreensStrategy
from app.strategies.strategy_filters import StrategyFilters


class Swing60PipStrategy(ThreeScreensStrategy):
    """Longer-hold profile on top of Three Screens.

    Goals:
    - fewer entries,
    - wider stop,
    - farther multi-target exits,
    - later breakeven shift.
    """

    name = "swing_60pip"

    def __init__(
        self,
        indicator_service: IndicatorService,
        trend_timeframe: str = "4h",
        h1_timeframe: str = "1h",
        filters: StrategyFilters | None = None,
    ) -> None:
        super().__init__(
            indicator_service=indicator_service,
            trend_timeframe=trend_timeframe,
            h1_timeframe=h1_timeframe,
            filters=filters,
        )

    def _evaluate(self, data: pd.DataFrame, context: dict | None = None) -> tuple[dict | None, dict]:
        payload, debug = super()._evaluate(data, context)
        if not payload:
            return None, debug

        meta = payload.get("meta") or {}
        plan = dict(meta.get("trade_plan") or {})
        entry = float(plan.get("entry") or payload.get("entry_price") or 0.0)
        stop = float(plan.get("stop_loss") or payload.get("stop_loss") or 0.0)
        if entry <= 0 or stop <= 0:
            return payload, debug

        side = payload.get("signal_type", "long")
        risk = abs(entry - stop)
        if risk <= 0:
            return payload, debug
        atr = float((payload.get("meta") or {}).get("screen2", {}).get("atr") or 0.0)
        atr_avg = float((payload.get("meta") or {}).get("screen2", {}).get("atr_avg") or atr)
        if atr_avg > 0 and atr > atr_avg * 2.2:
            debug["reasons"].append("volatility_spike_skip")
            return None, debug
        if entry > 0 and risk / entry < 0.0015:
            debug["reasons"].append("risk_too_tight")
            return None, debug

        # Wider swing targets: partial at 1R, runners to 2.5R and 4R.
        if side == "long":
            take_levels = [entry + 1.0 * risk, entry + 2.5 * risk, entry + 4.0 * risk]
        else:
            take_levels = [entry - 1.0 * risk, entry - 2.5 * risk, entry - 4.0 * risk]

        plan["take_levels"] = take_levels
        plan["take_profit"] = take_levels[-1]
        plan["breakeven_at"] = take_levels[0]
        plan["reward_risk"] = 4.0
        plan["profile"] = "swing_60pip"

        meta["trade_plan"] = plan
        payload["meta"] = meta
        payload["take_profit"] = take_levels[-1]
        # Slight confidence uplift for higher-TF swing profile.
        payload["confidence"] = min(float(payload.get("confidence", 0.0)) + 0.05, 1.0)
        payload["rationale"] = f"{payload.get('rationale', '')}, profile=swing_60pip"

        debug["profile"] = "swing_60pip"
        debug["swing_take_levels"] = take_levels
        return payload, debug
