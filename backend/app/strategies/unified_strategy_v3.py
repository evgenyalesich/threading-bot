from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite

import pandas as pd

from app.services.chart_pattern_service import ChartPatternService
from app.services.divergence_service import DivergenceService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.fibonacci_service import FibonacciService
from app.services.indicator_service import IndicatorService
from app.services.pattern_service import PatternService
from app.services.support_resistance_service import SupportResistanceService
from app.strategies.base_strategy import BaseStrategy
from app.strategies.strategy_filters import StrategyFilters


@dataclass(frozen=True)
class ProfileRules:
    name: str
    min_score: int
    min_layer23_score: int
    min_reward_risk: float
    sl_atr_mult: float
    require_dom: bool
    require_poi: bool
    breakout_only: bool
    stoch_long: float
    stoch_short: float


class UnifiedStrategyV3(BaseStrategy):
    """Single v3 strategy: filters -> trend -> POI -> confirmation -> DOM -> risk.

    This is intentionally one strategy with profiles instead of many competing strategies.
    quality_mode controls the entry profile: sniper, balanced, aggressive, breakout.
    """

    name = "unified_v3"
    is_mtf = True
    requires_order_book = True
    min_bars = 80
    trend_timeframe = "1h"
    h1_timeframe = "15m"

    _PROFILES = {
        "sniper": ProfileRules("sniper", 5, 2, 2.5, 1.5, True, True, False, 20, 80),
        "balanced": ProfileRules("balanced", 3, 2, 2.0, 2.0, False, False, False, 25, 75),
        "aggressive": ProfileRules("aggressive", 3, 1, 1.8, 2.5, False, False, False, 30, 70),
        "breakout": ProfileRules("breakout", 4, 2, 2.0, 2.0, True, True, True, 35, 65),
    }

    def __init__(
        self,
        indicator_service: IndicatorService,
        pattern_service: PatternService,
        chart_pattern_service: ChartPatternService,
        divergence_service: DivergenceService,
        support_resistance_service: SupportResistanceService,
        fibonacci_service: FibonacciService,
        elliott_wave_service: ElliottWaveService,
        filters: StrategyFilters | None = None,
        trend_timeframe: str = "1h",
        h1_timeframe: str = "15m",
    ) -> None:
        self._ind = indicator_service
        self._patterns = pattern_service
        self._chart_patterns = chart_pattern_service
        self._divergence = divergence_service
        self._sr = support_resistance_service
        self._fib = fibonacci_service
        self._elliott = elliott_wave_service
        self._filters = filters or StrategyFilters()
        self.trend_timeframe = trend_timeframe or "1h"
        self.h1_timeframe = h1_timeframe or "15m"

    def evaluate(self, data: pd.DataFrame, context: dict | None = None) -> dict | None:
        payload, _debug = self._evaluate(data, context)
        return payload

    def explain(self, data: pd.DataFrame, context: dict | None = None) -> dict:
        _payload, debug = self._evaluate(data, context)
        return debug

    def _evaluate(self, data: pd.DataFrame, context: dict | None = None) -> tuple[dict | None, dict]:
        ctx = context or {}
        profile = self._profile()
        debug: dict = {
            "strategy": self.name,
            "profile": profile.name,
            "reasons": [],
            "layers": {},
        }
        if len(data) < self.min_bars:
            debug["reasons"].append("insufficient_entry_bars")
            return None, debug

        entry = self._normalize_ohlcv(data)
        trend = self._normalize_ohlcv(ctx.get("trend_data")) if ctx.get("trend_data") is not None else entry

        layer0 = self._layer0_market_filter(entry, ctx)
        debug["layers"]["layer0_filter"] = layer0
        if not layer0["passed"]:
            debug["reasons"].extend(layer0["reasons"])
            return None, debug

        layer1 = self._layer1_trend(trend)
        debug["layers"]["layer1_trend"] = layer1
        if not layer1["passed"]:
            debug["reasons"].extend(layer1["reasons"])
            return None, debug
        side = "long" if layer1["bias"] > 0 else "short"

        layer2 = self._layer2_poi(entry, trend, side, ctx)
        debug["layers"]["layer2_poi"] = layer2
        if profile.require_poi and layer2["score"] <= 0:
            debug["reasons"].append("no_poi_confluence")
            return None, debug

        layer3 = self._layer3_confirmation(entry, side, profile)
        debug["layers"]["layer3_confirmation"] = layer3
        if layer2["score"] + layer3["score"] < profile.min_layer23_score:
            debug["reasons"].append("layer2_3_score_too_low")
            return None, debug

        layer4 = self._layer4_dom_and_breakout(entry, side, ctx)
        debug["layers"]["layer4_dom"] = layer4
        if layer4["blocked"]:
            debug["reasons"].extend(layer4["reasons"])
            return None, debug
        if profile.require_dom and not layer4["confirmed"]:
            debug["reasons"].append("dom_not_confirmed")
            return None, debug
        if profile.breakout_only and not layer4["breakout_confirmed"]:
            debug["reasons"].append("breakout_volume_not_confirmed")
            return None, debug

        risk = self._layer5_risk(entry, side, profile, layer2)
        debug["layers"]["layer5_risk"] = risk
        if not risk["passed"]:
            debug["reasons"].extend(risk["reasons"])
            return None, debug

        total_score = int(layer1["score"] + layer2["score"] + layer3["score"] + layer4["score"] + risk["score"])
        debug["confidence_score"] = total_score
        if total_score < profile.min_score:
            debug["reasons"].append("confidence_score_too_low")
            return None, debug

        confidence = min(0.98, max(float(self._filters.min_confidence), 0.42 + total_score * 0.085))
        confidence += 0.02 if profile.name == "sniper" else 0.0
        confidence = min(confidence, 0.98)

        trade_plan = {
            "entry": risk["entry"],
            "stop_loss": risk["stop_loss"],
            "take_profit": risk["take_levels"][-1],
            "take_levels": risk["take_levels"],
            "breakeven_at": risk["take_levels"][0],
            "reward_risk": risk["reward_risk"],
            "stop_type": f"dynamic_atr_{profile.sl_atr_mult:g}",
            "entry_order_type": "STOP_MARKET",
            "entry_trigger": risk["entry"],
            "tp1_close_pct": 0.30,
            "tp2_close_pct": 0.40,
            "runner_close_pct": 0.30,
            "trailing": {
                "enabled": True,
                "method": "ema26_close",
                "activate_after_r": 1.6,
            },
        }
        rationale = self._rationale(side, profile, layer1, layer2, layer3, layer4, risk, total_score)
        payload = {
            "signal_type": side,
            "confidence": confidence,
            "entry_price": risk["entry"],
            "stop_loss": risk["stop_loss"],
            "take_profit": risk["take_levels"][-1],
            "rationale": rationale,
            "meta": {
                "strategy": self.name,
                "profile": profile.name,
                "setup_state": "ready_to_trigger",
                "confidence_score": total_score,
                "layers": debug["layers"],
                "trade_plan": trade_plan,
                "entry_order": {
                    "type": "STOP_MARKET",
                    "label": "BUY STOP" if side == "long" else "SELL STOP",
                    "trigger": risk["entry"],
                    "signal_candle_high": risk["signal_high"],
                    "signal_candle_low": risk["signal_low"],
                },
            },
        }
        return payload, debug

    def _profile(self) -> ProfileRules:
        key = str(self._filters.quality_mode or "balanced").strip().lower()
        return self._PROFILES.get(key, self._PROFILES["balanced"])

    def _normalize_ohlcv(self, data: pd.DataFrame | None) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame()
        normalized = data.copy()
        for column in ["open", "high", "low", "close", "volume"]:
            if column not in normalized:
                normalized[column] = 0.0
            normalized[column] = normalized[column].astype(float)
        return normalized

    def _layer0_market_filter(self, data: pd.DataFrame, ctx: dict) -> dict:
        reasons: list[str] = []
        high, low, close = data["high"], data["low"], data["close"]
        atr = self._ind.atr(high, low, close, 14)
        atr_now = float(atr.iloc[-1])
        atr_avg = float(atr.rolling(40).mean().iloc[-1]) if len(atr) >= 40 else atr_now
        session = self._session_name(ctx)
        news_block = bool(ctx.get("news_block") or ctx.get("high_impact_news"))
        if news_block:
            reasons.append("news_blackout")
        if atr_avg > 0 and atr_now < atr_avg * 0.55:
            reasons.append("market_dead_atr_low")
        if session == "asia" and self._profile().name in {"sniper", "breakout"}:
            reasons.append("asia_session_sniper_stop")
        return {
            "passed": not reasons,
            "reasons": reasons,
            "session": session,
            "atr": atr_now,
            "atr_avg": atr_avg,
        }

    def _session_name(self, ctx: dict) -> str:
        raw = str(ctx.get("session") or "").lower()
        if raw:
            return raw
        now = ctx.get("now")
        hour = (now if isinstance(now, datetime) else datetime.now(UTC)).hour
        if 7 <= hour < 13:
            return "london"
        if 13 <= hour < 21:
            return "new_york"
        return "asia"

    def _layer1_trend(self, trend: pd.DataFrame) -> dict:
        reasons: list[str] = []
        if len(trend) < 210:
            reasons.append("insufficient_trend_bars")
            return {"passed": False, "reasons": reasons, "score": 0, "bias": 0}
        close = trend["close"]
        ema26 = self._ind.ema(close, 26)
        ema200 = self._ind.ema(close, 200)
        ema26_now = float(ema26.iloc[-1])
        ema26_prev = float(ema26.iloc[-4])
        ema200_now = float(ema200.iloc[-1])
        price = float(close.iloc[-1])
        atr = self._ind.atr(trend["high"], trend["low"], close, 14)
        atr_now = float(atr.iloc[-1])
        slope = ema26_now - ema26_prev
        ema_gap = abs(ema26_now - ema200_now)
        sideways = atr_now > 0 and (abs(slope) < atr_now * 0.05 or ema_gap < atr_now * 0.12)
        if sideways:
            reasons.append("trend_sideways_ema_near")
        bias = 1 if ema26_now > ema200_now and slope > 0 and price >= ema26_now else -1 if ema26_now < ema200_now and slope < 0 and price <= ema26_now else 0
        if bias == 0:
            reasons.append("no_clear_ema26_ema200_trend")
        score = 1 + int(atr_now > 0 and abs(slope) > atr_now * 0.12) if bias else 0
        return {
            "passed": bias != 0 and not sideways,
            "reasons": reasons,
            "score": score,
            "bias": bias,
            "ema26": ema26_now,
            "ema200": ema200_now,
            "slope": slope,
            "atr": atr_now,
        }

    def _layer2_poi(self, entry: pd.DataFrame, trend: pd.DataFrame, side: str, ctx: dict) -> dict:
        close = entry["close"]
        price = float(close.iloc[-1])
        atr = float(self._ind.atr(entry["high"], entry["low"], close, 14).iloc[-1])
        tolerance = max(atr * 0.8, price * 0.002)
        trend_close = trend["close"] if len(trend) else close
        ema200 = float(self._ind.ema(trend_close, 200).iloc[-1]) if len(trend_close) >= 200 else price
        fib = self._fib.levels(entry, lookback=min(160, len(entry)))
        sr = self._sr.levels(entry, window=5, tolerance=0.004)
        order_block = self._order_block_zone(entry, side)
        pieces: list[dict] = []

        def near(value: float | None) -> bool:
            return value is not None and isfinite(value) and abs(price - value) <= tolerance

        fib618 = fib.get("0.618")
        fib05 = fib.get("0.5")
        fib382 = fib.get("0.382")
        near_sr = any(abs(price - level) <= tolerance for level in sr)
        if near(fib618) and near(ema200):
            pieces.append({"name": "fib_0.618_ema200", "weight": 3, "label": "Fib 0.618 + EMA200"})
        if near_sr and near(fib05):
            pieces.append({"name": "sr_fib_0.5", "weight": 2, "label": "SR + Fib 0.5"})
        if near(fib382) and near_sr:
            pieces.append({"name": "fib_0.382_sr", "weight": 1, "label": "Fib 0.382 + SR"})
        if order_block["active"]:
            pieces.append({"name": "order_block", "weight": 1, "label": "OB / liquidity zone"})
        order_book = ctx.get("order_book") or {}
        if self._liquidity_near_price(order_book, price, tolerance, side):
            pieces.append({"name": "liquidity_wall", "weight": 1, "label": "DOM wall near POI"})
        score = min(sum(piece["weight"] for piece in pieces), 3)
        return {
            "score": score,
            "price": price,
            "tolerance": tolerance,
            "zones": pieces,
            "fib": fib,
            "sr_near": near_sr,
            "order_block": order_block,
        }

    def _layer3_confirmation(self, entry: pd.DataFrame, side: str, profile: ProfileRules) -> dict:
        high, low, close = entry["high"], entry["low"], entry["close"]
        stoch_k, stoch_d = self._ind.stochastic(high, low, close, 5, 3, 3)
        rsi = self._ind.rsi(close, 14)
        last_k = float(stoch_k.iloc[-1])
        last_d = float(stoch_d.iloc[-1])
        last_rsi = float(rsi.iloc[-1])
        oscillator = (last_k <= profile.stoch_long and last_rsi <= 45) if side == "long" else (last_k >= profile.stoch_short and last_rsi >= 55)
        divergence = self._divergence.detect(entry, rsi)
        divergence_ok = bool(divergence.get("bullish") if side == "long" else divergence.get("bearish"))
        candle_patterns = self._patterns.scan_latest(entry)
        candle_ok = any((item.get("signal") or 0) > 0 for item in candle_patterns) if side == "long" else any((item.get("signal") or 0) < 0 for item in candle_patterns)
        chart_pattern = self._chart_patterns.best_pattern(entry)
        pattern_direction = str(chart_pattern.get("direction") or "").lower() if chart_pattern else ""
        pattern_ok = pattern_direction in {side, "bullish" if side == "long" else "bearish"}
        elliott = self._elliott.analyze(entry)
        elliott_ok = bool(elliott.get("direction") == side or elliott.get("bias") == side) if isinstance(elliott, dict) else False
        volume_ok = self._pullback_volume_fades(entry)
        items = {
            "oscillator": oscillator,
            "divergence": divergence_ok,
            "pattern": candle_ok or pattern_ok or elliott_ok,
            "volume_pullback": volume_ok,
        }
        score = sum(1 for value in items.values() if value)
        return {
            "score": score,
            "items": items,
            "stoch_k": last_k,
            "stoch_d": last_d,
            "rsi": last_rsi,
            "candle_patterns": candle_patterns[:5],
            "chart_pattern": chart_pattern,
            "elliott": elliott,
        }

    def _layer4_dom_and_breakout(self, entry: pd.DataFrame, side: str, ctx: dict) -> dict:
        reasons: list[str] = []
        order_book = ctx.get("order_book") or {}
        bid_notional = float(order_book.get("bid_notional") or 0)
        ask_notional = float(order_book.get("ask_notional") or 0)
        imbalance = float(order_book.get("imbalance") or 0)
        spread_pct = float(order_book.get("spread_pct") or 0)
        available = bid_notional > 0 and ask_notional > 0
        aligned = (side == "long" and imbalance > 0.08) or (side == "short" and imbalance < -0.08)
        opposite = (side == "long" and imbalance < -0.30) or (side == "short" and imbalance > 0.30)
        if available and spread_pct > 0.08:
            reasons.append("spread_too_wide")
        if opposite:
            reasons.append("dom_opposite_pressure")
        breakout_confirmed = self._breakout_volume_confirmed(entry, side)
        score = int(aligned) + int(breakout_confirmed)
        return {
            "score": score,
            "available": available,
            "confirmed": aligned or not available,
            "aligned": aligned,
            "blocked": bool(reasons),
            "reasons": reasons,
            "imbalance": imbalance,
            "spread_pct": spread_pct,
            "bid_notional": bid_notional,
            "ask_notional": ask_notional,
            "breakout_confirmed": breakout_confirmed,
        }

    def _layer5_risk(self, entry: pd.DataFrame, side: str, profile: ProfileRules, layer2: dict) -> dict:
        reasons: list[str] = []
        high, low, close = entry["high"], entry["low"], entry["close"]
        atr = float(self._ind.atr(high, low, close, 14).iloc[-1])
        signal_high = float(high.iloc[-1])
        signal_low = float(low.iloc[-1])
        price = float(close.iloc[-1])
        buffer = max(price * 0.0002, atr * 0.05)
        entry_price = signal_high + buffer if side == "long" else signal_low - buffer
        lookback = min(12, len(entry))
        local_extreme = float(low.iloc[-lookback:].min()) if side == "long" else float(high.iloc[-lookback:].max())
        atr_stop = entry_price - atr * profile.sl_atr_mult if side == "long" else entry_price + atr * profile.sl_atr_mult
        stop = min(local_extreme, atr_stop) if side == "long" else max(local_extreme, atr_stop)
        risk = abs(entry_price - stop)
        if risk <= 0 or not isfinite(risk):
            reasons.append("invalid_risk")
            return {"passed": False, "reasons": reasons, "score": 0}
        reward_risk = max(float(self._filters.min_reward_risk or profile.min_reward_risk), profile.min_reward_risk)
        if reward_risk < 2.0:
            reasons.append("rr_below_1_2")
        if risk / max(entry_price, 1e-9) > 0.045:
            reasons.append("stop_too_wide")
        if side == "long":
            take_levels = [entry_price + 2 * risk, entry_price + 4 * risk, entry_price + 6 * risk]
        else:
            take_levels = [entry_price - 2 * risk, entry_price - 4 * risk, entry_price - 6 * risk]
        return {
            "passed": not reasons,
            "reasons": reasons,
            "score": 1,
            "entry": entry_price,
            "stop_loss": stop,
            "risk": risk,
            "reward_risk": reward_risk,
            "take_levels": take_levels,
            "signal_high": signal_high,
            "signal_low": signal_low,
            "poi_score": layer2.get("score", 0),
        }

    def _order_block_zone(self, data: pd.DataFrame, side: str) -> dict:
        recent = data.tail(30)
        if len(recent) < 10:
            return {"active": False}
        volume_avg = float(recent["volume"].rolling(10).mean().iloc[-1])
        candidates = recent[recent["volume"] >= volume_avg * 1.35] if volume_avg > 0 else recent.iloc[0:0]
        if candidates.empty:
            return {"active": False}
        row = candidates.iloc[-1]
        price = float(data["close"].iloc[-1])
        low = float(row["low"])
        high = float(row["high"])
        active = low <= price <= high if side == "long" else low <= price <= high
        return {"active": active, "low": low, "high": high, "volume": float(row["volume"])}

    def _liquidity_near_price(self, order_book: dict, price: float, tolerance: float, side: str) -> bool:
        rows = order_book.get("bid_walls" if side == "long" else "ask_walls") or []
        return any(abs(float(row.get("price") or 0) - price) <= tolerance for row in rows)

    def _pullback_volume_fades(self, data: pd.DataFrame) -> bool:
        if len(data) < 8:
            return False
        recent = data["volume"].tail(5).astype(float)
        previous = data["volume"].tail(12).head(7).astype(float)
        return float(recent.mean()) < float(previous.mean()) * 0.9 if float(previous.mean()) > 0 else False

    def _breakout_volume_confirmed(self, data: pd.DataFrame, side: str) -> bool:
        if len(data) < 25:
            return False
        volume = data["volume"].astype(float)
        avg = float(volume.tail(21).head(20).mean())
        high = data["high"].astype(float)
        low = data["low"].astype(float)
        close = data["close"].astype(float)
        if avg <= 0 or float(volume.iloc[-1]) < avg * 1.5:
            return False
        if side == "long":
            return float(close.iloc[-1]) > float(high.tail(8).iloc[:-1].max())
        return float(close.iloc[-1]) < float(low.tail(8).iloc[:-1].min())

    def _rationale(self, side: str, profile: ProfileRules, layer1: dict, layer2: dict, layer3: dict, layer4: dict, risk: dict, score: int) -> str:
        poi = ", ".join(zone["label"] for zone in layer2.get("zones", [])[:3]) or "POI weak"
        confirmations = [name for name, ok in layer3.get("items", {}).items() if ok]
        dom = "DOM confirmed" if layer4.get("aligned") else "DOM neutral/unavailable"
        return (
            f"unified_v3[{profile.name}] {side.upper()}: "
            f"trend EMA26/EMA200 ok, POI={poi}, confirm={'+'.join(confirmations) or 'none'}, "
            f"{dom}, score={score}, entry=STOP {risk['entry']:.6g}, "
            f"SL={risk['stop_loss']:.6g}, TP1=2R, TP2=4R, runner=6R"
        )
