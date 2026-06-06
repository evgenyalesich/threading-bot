from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.services.chart_pattern_service import ChartPatternService
from app.services.divergence_service import DivergenceService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.fibonacci_service import FibonacciService
from app.services.indicator_service import IndicatorService
from app.services.pattern_service import PatternService
from app.services.support_resistance_service import SupportResistanceService
from app.services.trade_plan_service import TradePlanService
from app.strategies.base_strategy import BaseStrategy
from app.strategies.strategy_filters import StrategyFilters


@dataclass
class _PatternPick:
    pattern: dict
    state: str
    breakout_distance: float


class AdaptivePatternConfluenceStrategy(BaseStrategy):
    """Pattern-first setup strategy with adaptive confirmation gates.

    The goal is to keep the original confluence idea, but make it less brittle:
    - a pattern can be confirmed or still forming (candidate),
    - EMA/Fib/SR/divergence help quality, but do not fully block good setups,
    - trade plans are still built from real chart structure.
    """

    name = "adaptive_pattern_confluence"
    is_mtf = True
    min_bars = 180
    trend_timeframe: str = "4h"
    h1_timeframe: str = "1h"

    def __init__(
        self,
        indicator_service: IndicatorService,
        pattern_service: PatternService,
        chart_pattern_service: ChartPatternService,
        divergence_service: DivergenceService,
        support_resistance_service: SupportResistanceService,
        fibonacci_service: FibonacciService,
        elliott_wave_service: ElliottWaveService,
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
        self._trade_plan_service = trade_plan_service
        self._filters = filters or StrategyFilters()

    def evaluate(self, data: pd.DataFrame, context: dict | None = None) -> dict | None:
        payload, _debug = self._evaluate(data, context)
        return payload

    def explain(self, data: pd.DataFrame, context: dict | None = None) -> dict:
        _payload, debug = self._evaluate(data, context)
        return debug

    def _evaluate(self, data: pd.DataFrame, context: dict | None = None) -> tuple[dict | None, dict]:
        debug: dict = {"reasons": []}
        ctx = context or {}
        timeframe = ctx.get("timeframe")
        debug["timeframe"] = timeframe
        debug["bars"] = len(data)
        debug["min_bars"] = self.min_bars

        trend_data: pd.DataFrame | None = (
            ctx.get("trend_data") if ctx.get("trend_data") is not None else ctx.get("h1_data")
        )
        if trend_data is None or len(trend_data) < 40:
            debug["reasons"].append("no_trend_data_or_insufficient")
            return None, debug
        if len(data) < self.min_bars:
            debug["reasons"].append("insufficient_entry_bars")
            return None, debug

        high = data["high"].astype(float)
        low = data["low"].astype(float)
        close = data["close"].astype(float)
        volume = data["volume"].astype(float)

        last_close = float(close.iloc[-1])
        entry_atr = float(self._indicator_service.atr(high, low, close, period=14).iloc[-1])
        trend_close = trend_data["close"].astype(float)
        trend_ema26 = self._indicator_service.ema(trend_close, 26)
        trend_ema200 = self._indicator_service.ema(trend_close, 200)
        trend_atr = self._indicator_service.atr(
            trend_data["high"].astype(float),
            trend_data["low"].astype(float),
            trend_close,
            period=14,
        )
        trend_ema26_now = float(trend_ema26.iloc[-1])
        trend_ema26_prev = float(trend_ema26.iloc[max(len(trend_ema26) - 4, 0)])
        trend_atr_now = float(trend_atr.iloc[-1])
        trend_bias = 1 if trend_ema26_now >= trend_ema26_prev else -1
        trend_strength = abs(trend_ema26_now - trend_ema26_prev) / max(trend_atr_now, 1e-9) if trend_atr_now > 0 else 0.0

        ema200_value = float(trend_ema200.iloc[-1]) if len(trend_ema200) >= 200 else float(trend_close.iloc[-1])
        if trend_bias == 1 and float(trend_close.iloc[-1]) < ema200_value:
            trend_bias = 0
        elif trend_bias == -1 and float(trend_close.iloc[-1]) > ema200_value:
            trend_bias = 0

        trend_confirm = trend_bias != 0 and trend_strength >= self._filters.min_trend_strength
        if not trend_confirm:
            debug.setdefault("warnings", []).append("trend_less_informative")

        stoch_k, stoch_d = self._indicator_service.stochastic(high, low, close, k_period=5, d_period=3, smooth_k=3)
        rsi = self._indicator_service.rsi(close, period=14)
        candle_hits = self._pattern_service.scan_latest(data)
        divergence = self._divergence_service.detect(data, rsi)
        support_resistance = self._support_resistance_service.levels(data)
        fib_levels = self._fibonacci_service.levels(data)
        elliott_pivots = self._elliott_wave_service.analyze(data)
        chart_patterns = self._chart_pattern_service.detect(data)

        pattern_pick = self._pick_pattern(data, chart_patterns)
        if pattern_pick:
            debug["pattern_state"] = pattern_pick.state
            debug["pattern_name"] = pattern_pick.pattern.get("name")
            debug["pattern_confidence"] = float(pattern_pick.pattern.get("confidence", 0))
            debug["pattern_breakout_distance"] = pattern_pick.breakout_distance
            if pattern_pick.state == "candidate" and not self._filters.allow_candidate_patterns:
                debug["reasons"].append("candidate_pattern_blocked")
                return None, debug

        pattern_bias = self._pattern_bias(pattern_pick.pattern) if pattern_pick else 0
        divergence_bias = 1 if divergence.get("bullish") else -1 if divergence.get("bearish") else 0
        candle_bias = self._candle_bias(candle_hits)

        side = self._choose_side(trend_bias, pattern_bias, divergence_bias, candle_bias)
        if side is None:
            debug["reasons"].append("no_signal_components")
            return None, debug
        direction_sign = 1 if side == "long" else -1

        if self._filters.require_trend_filter and trend_bias == 0:
            debug["reasons"].append("higher_timeframe_bias_missing")
            return None, debug
        if self._filters.require_trend_filter and trend_bias != direction_sign:
            debug["reasons"].append("higher_timeframe_mismatch")
            return None, debug

        breakout_align = 0
        if pattern_pick:
            breakout = float(pattern_pick.pattern.get("breakout") or 0.0)
            if breakout > 0:
                breakout_distance = abs(last_close - breakout) / max(last_close, 1e-9)
                if breakout_distance <= self._dynamic_confluence_tolerance(last_close, entry_atr):
                    breakout_align = 1
                debug["breakout_distance"] = breakout_distance

        key_levels = [float(level) for level in fib_levels.values()]
        key_levels.extend(float(level) for level in support_resistance)
        trend_ema200_value = float(ema200_value)
        if trend_ema200_value > 0:
            key_levels.append(trend_ema200_value)

        nearest_confluence = min(
            (abs(last_close - level) / max(last_close, 1e-9) for level in key_levels if level > 0),
            default=1.0,
        )
        confluence_ok = nearest_confluence <= self._dynamic_confluence_tolerance(last_close, entry_atr)
        debug.update(
            {
                "last_close": last_close,
                "trend_bias": trend_bias,
                "trend_strength": trend_strength,
                "ema200": ema200_value,
                "pattern_bias": pattern_bias,
                "divergence_bias": divergence_bias,
                "candle_bias": candle_bias,
                "breakout_align": breakout_align,
                "nearest_confluence_distance": nearest_confluence,
                "confluence_tolerance": self._dynamic_confluence_tolerance(last_close, entry_atr),
                "confluence_ok": confluence_ok,
                "filters": {
                    "min_confidence": self._filters.min_confidence,
                    "min_confirmations": self._filters.min_confirmations,
                    "require_pattern": self._filters.require_pattern,
                    "require_divergence": self._filters.require_divergence,
                    "require_candle": self._filters.require_candle,
                    "require_volume_confirm": self._filters.require_volume_confirm,
                    "require_trend_filter": self._filters.require_trend_filter,
                },
            }
        )

        confirmations = 0
        if pattern_pick and pattern_bias == direction_sign:
            confirmations += 2 if pattern_pick.state == "confirmed" else 1
        if trend_confirm and trend_bias == direction_sign:
            confirmations += 1
        if divergence_bias == direction_sign:
            confirmations += 1
        if candle_bias == direction_sign:
            confirmations += 1
        if breakout_align:
            confirmations += 1
        if confluence_ok:
            confirmations += 1

        volume_avg = float(volume.rolling(window=20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.mean())
        volume_confirm = bool(volume_avg > 0 and float(volume.iloc[-1]) >= volume_avg * 1.08)
        debug["volume_confirm"] = volume_confirm
        debug["confirmations"] = confirmations

        pattern_conf = float(pattern_pick.pattern.get("confidence", 0)) if pattern_pick else 0.0
        raw_confidence = 0.22
        if pattern_pick:
            raw_confidence += min(pattern_conf * 0.55, 0.42)
            if pattern_pick.state == "confirmed":
                raw_confidence += 0.08
            else:
                raw_confidence += 0.02
        if trend_confirm and trend_bias == direction_sign:
            raw_confidence += 0.10
        if divergence_bias == direction_sign:
            raw_confidence += 0.08
        if candle_bias == direction_sign:
            raw_confidence += 0.06
        if confluence_ok:
            raw_confidence += 0.08
        if breakout_align:
            raw_confidence += 0.05
        if volume_confirm:
            raw_confidence += 0.05
        if trend_strength < 0.08:
            raw_confidence -= 0.04

        confidence = min(max(raw_confidence, 0.0), 1.0)
        debug["confidence"] = confidence

        min_required_confirmations = int(self._filters.min_confirmations)
        if pattern_pick and pattern_pick.state == "candidate":
            min_required_confirmations = max(min_required_confirmations, 3)
        elif pattern_pick and pattern_pick.state == "confirmed":
            min_required_confirmations = max(min_required_confirmations, 2)
        else:
            min_required_confirmations = max(min_required_confirmations, 2)
        if str(self._filters.quality_mode).lower() == "sniper":
            min_required_confirmations = max(min_required_confirmations, 4)

        if self._filters.require_pattern and not pattern_pick:
            debug["reasons"].append("pattern_required")
            return None, debug
        if confirmations < min_required_confirmations:
            debug["reasons"].append("confirmations_below_min")
            return None, debug

        if confidence < self._filters.min_confidence:
            debug["reasons"].append("confidence_below_min")
            return None, debug
        if self._filters.require_divergence and divergence_bias != direction_sign:
            debug["reasons"].append("divergence_required")
            return None, debug
        if self._filters.require_candle and candle_bias != direction_sign:
            debug["reasons"].append("candle_required")
            return None, debug
        if self._filters.require_volume_confirm and not volume_confirm:
            debug["reasons"].append("volume_confirm_required")
            return None, debug

        if pattern_pick and pattern_pick.pattern.get("stop_level") is not None:
            stop_hint = float(pattern_pick.pattern.get("stop_level"))
        else:
            stop_hint = None
        level_pool = [float(level) for level in support_resistance] + [float(level) for level in fib_levels.values()]
        if pattern_pick and isinstance(pattern_pick.pattern.get("target"), (int, float)):
            level_pool.append(float(pattern_pick.pattern["target"]))
        trade_plan = self._trade_plan_service.build(
            entry=last_close,
            side=side,
            support_levels=level_pool,
            resistance_levels=level_pool,
            stop_hint=stop_hint,
        )
        if float(trade_plan.reward_risk) < float(self._filters.min_reward_risk):
            debug["reasons"].append("reward_risk_below_min")
            debug["reward_risk"] = trade_plan.reward_risk
            return None, debug

        risk = abs(trade_plan.entry - trade_plan.stop_loss)
        if risk <= 0:
            debug["reasons"].append("zero_risk")
            return None, debug
        if last_close > 0 and risk / last_close > 0.045:
            debug["reasons"].append("risk_too_wide")
            debug["risk_pct"] = risk / last_close
            return None, debug
        if last_close > 0 and risk / last_close < 0.001:
            debug["reasons"].append("risk_too_tight")
            debug["risk_pct"] = risk / last_close
            return None, debug
        if str(self._filters.quality_mode).lower() == "sniper":
            if not confluence_ok:
                debug["reasons"].append("sniper_requires_confluence")
                return None, debug
            if not any(
                [
                    volume_confirm,
                    breakout_align,
                    divergence_bias == direction_sign,
                    candle_bias == direction_sign,
                ]
            ):
                debug["reasons"].append("sniper_requires_extra_confirmation")
                return None, debug

        setup_state = pattern_pick.state if pattern_pick else ("trend" if trend_confirm else "momentum")
        setup_mode = "breakout" if breakout_align and pattern_pick else "pullback"
        risk_levels = {
            "stop_loss": trade_plan.stop_loss,
            "take_profit": trade_plan.take_profit,
        }
        rationale = (
            f"adaptive_pattern: state={setup_state}, mode={setup_mode}, side={side}, "
            f"trend={trend_bias}, pattern={pattern_bias}, divergence={divergence_bias}, candle={candle_bias}, "
            f"conf={confidence:.2f}, confluence={nearest_confluence:.4f}, risk={risk:.4f}"
        )

        payload = {
            "signal_type": side,
            "confidence": confidence,
            "entry_price": trade_plan.entry,
            "stop_loss": trade_plan.stop_loss,
            "take_profit": trade_plan.take_profit,
            "rationale": rationale,
            "meta": {
                "setup": {
                    "state": setup_state,
                    "mode": setup_mode,
                    "pattern_name": pattern_pick.pattern.get("name") if pattern_pick else None,
                    "pattern_confidence": pattern_conf,
                },
                "chart_pattern": pattern_pick.pattern if pattern_pick else None,
                "candles": {
                    "bullish": [hit["name"] for hit in candle_hits if hit["signal"] > 0],
                    "bearish": [hit["name"] for hit in candle_hits if hit["signal"] < 0],
                    "score": candle_bias,
                },
                "trend": {
                    "timeframe": self.trend_timeframe,
                    "bias": trend_bias,
                    "strength": trend_strength,
                    "ema26_now": trend_ema26_now,
                    "ema26_prev": trend_ema26_prev,
                    "ema200": ema200_value,
                },
                "divergence": divergence,
                "trade_plan": {
                    "entry": trade_plan.entry,
                    "stop_loss": trade_plan.stop_loss,
                    "take_profit": trade_plan.take_profit,
                    "take_levels": trade_plan.take_levels,
                    "breakeven_at": trade_plan.breakeven_at,
                    "reward_risk": trade_plan.reward_risk,
                    "stop_type": trade_plan.stop_type,
                    "min_hold_seconds": 3600 if timeframe == "1h" else 14400 if timeframe == "4h" else 0,
                },
                "position_profile": {
                    "style": "adaptive_pattern_confluence",
                    "allowed_timeframes": ["15m", "1h", "4h"],
                },
                "risk_levels": risk_levels,
                "probability": confidence,
                "elliott_pivots": len(elliott_pivots),
                "volume_confirm": volume_confirm,
            },
        }

        return payload, debug

    def _pick_pattern(self, data: pd.DataFrame, patterns: list[dict]) -> _PatternPick | None:
        if not patterns:
            return None
        last_close = float(data["close"].iloc[-1])
        scored: list[_PatternPick] = []
        for pattern in patterns:
            direction = pattern.get("direction")
            if direction not in {"long", "short"}:
                continue
            breakout = float(pattern.get("breakout") or 0.0)
            breakout_distance = abs(last_close - breakout) / max(last_close, 1e-9) if breakout > 0 else 1.0
            state = "confirmed" if pattern.get("confirmed") else "candidate"
            scored.append(_PatternPick(pattern=pattern, state=state, breakout_distance=breakout_distance))
        if not scored:
            return None
        scored.sort(
            key=lambda item: (
                1 if item.state == "confirmed" else 0,
                float(item.pattern.get("confidence", 0)),
                -item.breakout_distance,
                int(item.pattern.get("index", 0)),
            ),
            reverse=True,
        )
        return scored[0]

    def _pattern_bias(self, pattern: dict | None) -> int:
        if not pattern:
            return 0
        direction = pattern.get("direction")
        if direction == "long":
            return 1
        if direction == "short":
            return -1
        return 0

    def _candle_bias(self, candle_hits: list[dict]) -> int:
        if not candle_hits:
            return 0
        bullish = [hit for hit in candle_hits if hit["signal"] > 0]
        bearish = [hit for hit in candle_hits if hit["signal"] < 0]
        if len(bullish) > len(bearish):
            return 1
        if len(bearish) > len(bullish):
            return -1
        return 0

    def _choose_side(
        self,
        trend_bias: int,
        pattern_bias: int,
        divergence_bias: int,
        candle_bias: int,
    ) -> str | None:
        if pattern_bias != 0:
            return "long" if pattern_bias > 0 else "short"

        score = trend_bias
        score += divergence_bias
        score += candle_bias
        if score > 0:
            return "long"
        if score < 0:
            return "short"
        if divergence_bias != 0:
            return "long" if divergence_bias > 0 else "short"
        if candle_bias != 0:
            return "long" if candle_bias > 0 else "short"
        return None

    def _dynamic_confluence_tolerance(self, entry: float, atr: float) -> float:
        base = 0.005
        if entry <= 0:
            return base
        atr_ratio = atr / entry if atr > 0 else 0.0
        return min(max(base, atr_ratio * 1.8), 0.02)
