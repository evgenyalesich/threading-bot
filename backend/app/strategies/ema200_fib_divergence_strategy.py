from __future__ import annotations

import pandas as pd

from app.services.chart_pattern_service import ChartPatternService
from app.services.divergence_service import DivergenceService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.fibonacci_service import FibonacciService
from app.services.indicator_service import IndicatorService
from app.services.pattern_service import PatternService
from app.services.risk_service import RiskService
from app.services.support_resistance_service import SupportResistanceService
from app.services.trade_plan_service import TradePlanService
from app.strategies.base_strategy import BaseStrategy
from app.strategies.strategy_filters import StrategyFilters


class Ema200FibDivergenceStrategy(BaseStrategy):
    name = "ema200_fib_divergence"

    def __init__(
        self,
        indicator_service: IndicatorService,
        pattern_service: PatternService,
        chart_pattern_service: ChartPatternService,
        divergence_service: DivergenceService,
        support_resistance_service: SupportResistanceService,
        fibonacci_service: FibonacciService,
        elliott_wave_service: ElliottWaveService,
        risk_service: RiskService,
        trade_plan_service: TradePlanService,
        filters: StrategyFilters | None = None,
    ) -> None:
        self._indicator_service = indicator_service
        self._pattern_service = pattern_service
        self._chart_pattern_service = chart_pattern_service
        self._divergence_service = divergence_service
        self._support_resistance_service = support_resistance_service
        self._fibonacci_service = fibonacci_service
        self._elliott_wave_service = elliott_wave_service
        self._risk_service = risk_service
        self._trade_plan_service = trade_plan_service
        self._filters = filters or StrategyFilters()

    def evaluate(self, data: pd.DataFrame) -> dict | None:
        payload, _debug = self._evaluate(data)
        return payload

    def explain(self, data: pd.DataFrame) -> dict:
        _payload, debug = self._evaluate(data)
        return debug

    def _evaluate(self, data: pd.DataFrame) -> tuple[dict | None, dict]:
        debug: dict = {"reasons": []}
        debug["bars"] = len(data)
        debug["min_bars"] = 210

        if len(data) < 210:
            debug["reasons"].append("insufficient_bars")
            return None, debug

        close = data["close"].astype(float)
        ema200 = self._indicator_service.ema(close, 200)
        rsi = self._indicator_service.rsi(close)
        divergence = self._divergence_service.detect(data, rsi)
        candle_hits = self._pattern_service.scan_latest(data)
        support_resistance = self._support_resistance_service.levels(data)
        fib_levels = self._fibonacci_service.levels(data)
        elliott_pivots = self._elliott_wave_service.analyze(data)
        chart_pattern = self._chart_pattern_service.best_pattern(data)

        last_close = float(close.iloc[-1])
        trend_bias = 1 if last_close > float(ema200.iloc[-1]) else -1

        pattern_bias = 0
        candle_bias = 0
        candle_strength = 0.0
        if candle_hits:
            bullish = [hit for hit in candle_hits if hit["signal"] > 0]
            bearish = [hit for hit in candle_hits if hit["signal"] < 0]
            if len(bullish) > len(bearish):
                candle_bias = 1
            elif len(bearish) > len(bullish):
                candle_bias = -1
            candle_strength = min(max(len(bullish), len(bearish)) / 5.0, 1.0)

        if chart_pattern and chart_pattern.get("direction") in {"long", "short"}:
            pattern_bias = 1 if chart_pattern["direction"] == "long" else -1

        divergence_bias = 1 if divergence.get("bullish") else -1 if divergence.get("bearish") else 0

        score = trend_bias + pattern_bias + divergence_bias + candle_bias
        signal_strength = abs(pattern_bias) + abs(divergence_bias) + abs(candle_bias)

        debug.update(
            {
                "last_close": last_close,
                "trend_bias": trend_bias,
                "pattern_bias": pattern_bias,
                "divergence_bias": divergence_bias,
                "candle_bias": candle_bias,
                "score": score,
                "signal_strength": signal_strength,
                "filters": {
                    "min_confidence": self._filters.min_confidence,
                    "min_confirmations": self._filters.min_confirmations,
                    "require_pattern": self._filters.require_pattern,
                    "require_divergence": self._filters.require_divergence,
                    "require_candle": self._filters.require_candle,
                    "require_volume_confirm": self._filters.require_volume_confirm,
                },
            }
        )

        if signal_strength == 0:
            debug["reasons"].append("no_signal_components")
            return None, debug

        if pattern_bias != 0:
            side = "long" if pattern_bias > 0 else "short"
        elif score >= 1:
            side = "long"
        elif score <= -1:
            side = "short"
        else:
            side = "long" if divergence_bias > 0 or candle_bias > 0 else "short"

        direction_sign = 1 if side == "long" else -1
        confirmations = 0
        if pattern_bias == direction_sign:
            confirmations += 2
        if divergence_bias == direction_sign:
            confirmations += 1
        if candle_bias == direction_sign:
            confirmations += 1

        debug.update({"side": side, "confirmations": confirmations})

        if trend_bias != direction_sign:
            debug["reasons"].append("trend_mismatch_ema200")
            return None, debug
        if confirmations < self._filters.min_confirmations:
            debug["reasons"].append("confirmations_below_min")
            return None, debug

        volume = data["volume"].astype(float)
        volume_confirm = bool(volume.iloc[-1] > volume.rolling(window=20).mean().iloc[-1] * 1.2)
        pattern_conf = float(chart_pattern.get("confidence", 0)) if chart_pattern else 0.0

        confidence = min(
            1.0,
            0.25 * (1 if trend_bias == (1 if side == "long" else -1) else 0)
            + 0.2 * (1 if divergence_bias == (1 if side == "long" else -1) else 0)
            + 0.2 * candle_strength
            + 0.25 * pattern_conf
            + 0.1 * (1 if volume_confirm else 0),
        )
        probability = confidence

        debug.update(
            {
                "confidence": confidence,
                "volume_confirm": volume_confirm,
                "pattern_confidence": pattern_conf,
            }
        )

        if confidence < self._filters.min_confidence:
            debug["reasons"].append("confidence_below_min")
            return None, debug
        if self._filters.require_volume_confirm and not volume_confirm:
            debug["reasons"].append("volume_confirm_required")
            return None, debug
        if self._filters.require_pattern and pattern_bias != direction_sign:
            debug["reasons"].append("pattern_required")
            return None, debug
        if self._filters.require_divergence and divergence_bias != direction_sign:
            debug["reasons"].append("divergence_required")
            return None, debug
        if self._filters.require_candle and candle_bias != direction_sign:
            debug["reasons"].append("candle_required")
            return None, debug

        level_pool = [float(level) for level in support_resistance] + [float(level) for level in fib_levels.values()]
        if chart_pattern and isinstance(chart_pattern.get("target"), (int, float)):
            level_pool.append(float(chart_pattern["target"]))
        trade_plan = self._trade_plan_service.build(
            entry=last_close,
            side=side,
            support_levels=level_pool,
            resistance_levels=level_pool,
            stop_hint=chart_pattern.get("stop_level") if chart_pattern else None,
        )

        risk_levels = self._risk_service.levels(last_close, side, reward_risk=3.0)

        rationale = (
            f"trend={trend_bias}, candles={candle_bias}, pattern={pattern_bias}, "
            f"divergence={divergence_bias}, volume_confirm={int(volume_confirm)}, "
            f"sr_levels={len(support_resistance)}, fib_levels={len(fib_levels)}, "
            f"elliott_pivots={len(elliott_pivots)}"
        )

        payload = {
            "signal_type": side,
            "confidence": confidence,
            "entry_price": last_close,
            "stop_loss": trade_plan.stop_loss,
            "take_profit": trade_plan.take_profit,
            "rationale": rationale,
            "meta": {
                "chart_pattern": chart_pattern,
                "candles": {
                    "bullish": [hit["name"] for hit in candle_hits if hit["signal"] > 0],
                    "bearish": [hit["name"] for hit in candle_hits if hit["signal"] < 0],
                    "score": candle_bias,
                },
                "trade_plan": {
                    "entry": trade_plan.entry,
                    "stop_loss": trade_plan.stop_loss,
                    "take_profit": trade_plan.take_profit,
                    "take_levels": trade_plan.take_levels,
                    "breakeven_at": trade_plan.breakeven_at,
                    "reward_risk": trade_plan.reward_risk,
                    "stop_type": trade_plan.stop_type,
                },
                "risk_levels": risk_levels,
                "probability": probability,
            },
        }

        return payload, debug

