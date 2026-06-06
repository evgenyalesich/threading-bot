from __future__ import annotations

import pandas as pd

from app.services.indicator_service import IndicatorService
from app.strategies.base_strategy import BaseStrategy
from app.strategies.strategy_filters import StrategyFilters


class ThreeScreensStrategy(BaseStrategy):
    """Elder's Triple Screen strategy — H1 trend + M15 pullback version.

    Screen 1 (H1): EMA26 slope determines trend direction.
    Screen 2 (M15): Stochastic(5,3,3) identifies oversold/overbought pullback.
    Screen 3 (M15): stop-entry above/below signal candle.
    Stop-loss: nearest local extremum on M15 plus ATR buffer.
    Take-profit: TP1=1.5R (breakeven trigger), TP2=2.5R (full exit).

    context keys:
        "trend_data"  — 4H OHLCV DataFrame (Screen 1)
        "h1_data"     — legacy alias for trend_data (backwards compat)
    The entry-timeframe data is passed as the main `data` argument (1H).
    """

    name = "three_screens"
    is_mtf = True
    min_bars = 30

    # Services look for these attributes to know which TFs to load
    trend_timeframe: str = "1h"   # Screen 1 — trend
    h1_timeframe: str = "15m"     # Screen 2+3 — entry signal (kept for compat)

    def __init__(
        self,
        indicator_service: IndicatorService,
        trend_timeframe: str = "1h",
        h1_timeframe: str = "15m",
        filters: StrategyFilters | None = None,
    ) -> None:
        self._ind = indicator_service
        self.trend_timeframe = trend_timeframe
        self.h1_timeframe = h1_timeframe
        self._filters = filters or StrategyFilters()

    def evaluate(self, data: pd.DataFrame, context: dict | None = None) -> dict | None:
        payload, _debug = self._evaluate(data, context)
        return payload

    def explain(self, data: pd.DataFrame, context: dict | None = None) -> dict:
        _payload, debug = self._evaluate(data, context)
        return debug

    def _evaluate(
        self, data: pd.DataFrame, context: dict | None = None
    ) -> tuple[dict | None, dict]:
        debug: dict = {"reasons": []}
        ctx = context or {}

        # Screen 1: H1 trend via EMA26 slope + optional EMA200 alignment
        # Support both "trend_data" (new) and "h1_data" (legacy) keys
        trend_data: pd.DataFrame | None = ctx.get("trend_data") if ctx.get("trend_data") is not None else ctx.get("h1_data")
        if trend_data is None or len(trend_data) < 30:
            debug["reasons"].append("no_trend_data_or_insufficient")
            return None, debug

        trend_close = trend_data["close"].astype(float)
        ema26 = self._ind.ema(trend_close, 26)
        ema26_now = float(ema26.iloc[-1])
        ema26_prev = float(ema26.iloc[-4])
        h1_trend = 1 if ema26_now > ema26_prev else -1
        trend_atr = self._ind.atr(
            trend_data["high"].astype(float),
            trend_data["low"].astype(float),
            trend_close,
            period=14,
        )
        trend_atr_now = float(trend_atr.iloc[-1])
        trend_slope = abs(ema26_now - ema26_prev)
        min_trend_slope = trend_atr_now * 0.08
        if self._filters.require_trend_filter and trend_atr_now > 0 and trend_slope < min_trend_slope:
            debug["reasons"].append("trend_too_flat")
            debug["trend_slope"] = trend_slope
            debug["min_trend_slope"] = min_trend_slope
            return None, debug

        # EMA200 alignment: trade WITH the macro trend only
        ema200_ok = True
        if len(trend_close) >= 200:
            ema200 = self._ind.ema(trend_close, 200)
            ema200_val = float(ema200.iloc[-1])
            current_price = float(trend_close.iloc[-1])
            if self._filters.require_trend_filter and h1_trend == 1 and current_price < ema200_val:
                debug["reasons"].append("below_ema200_no_long")
                debug["h1_trend"] = h1_trend
                debug["ema200"] = ema200_val
                return None, debug
            if self._filters.require_trend_filter and h1_trend == -1 and current_price > ema200_val:
                debug["reasons"].append("above_ema200_no_short")
                debug["h1_trend"] = h1_trend
                debug["ema200"] = ema200_val
                return None, debug
            debug["ema200"] = ema200_val

        debug["h1_trend"] = h1_trend
        debug["ema26_now"] = ema26_now
        debug["ema26_prev"] = ema26_prev

        # Screen 2: M15 oscillator pullback against H1 trend
        if len(data) < self.min_bars:
            debug["reasons"].append("insufficient_entry_bars")
            return None, debug

        high = data["high"].astype(float)
        low = data["low"].astype(float)
        close = data["close"].astype(float)
        volume = data["volume"].astype(float)

        stoch_k, stoch_d = self._ind.stochastic(high, low, close, k_period=5, d_period=3, smooth_k=3)
        rsi = self._ind.rsi(close, period=14)
        atr = self._ind.atr(high, low, close, period=14)

        last_k = float(stoch_k.iloc[-1])
        last_d = float(stoch_d.iloc[-1])
        last_rsi = float(rsi.iloc[-1])
        last_atr = float(atr.iloc[-1])
        atr_avg = float(atr.rolling(window=20).mean().iloc[-1]) if len(atr) >= 20 else last_atr
        vol_avg = float(volume.rolling(window=20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.mean())
        last_vol = float(volume.iloc[-1])
        body = abs(float(close.iloc[-1]) - float(data["open"].astype(float).iloc[-1]))
        candle_range = max(float(high.iloc[-1]) - float(low.iloc[-1]), 0.0)
        body_ratio = body / candle_range if candle_range > 0 else 0.0

        if atr_avg > 0 and last_atr < atr_avg * 0.75:
            debug["reasons"].append("volatility_too_low")
            debug["atr"] = last_atr
            debug["atr_avg"] = atr_avg
            return None, debug

        if h1_trend == 1:
            stoch_confirm = last_k < 20 and last_d < 25
            rsi_confirm = last_rsi < 50
        else:
            stoch_confirm = last_k > 80 and last_d > 75
            rsi_confirm = last_rsi > 50

        debug.update({
            "stoch_k": last_k,
            "stoch_d": last_d,
            "rsi": last_rsi,
            "stoch_confirm": stoch_confirm,
            "rsi_confirm": rsi_confirm,
            "atr": last_atr,
            "atr_avg": atr_avg,
            "body_ratio": body_ratio,
            "filters": {
                "min_confidence": self._filters.min_confidence,
                "min_confirmations": self._filters.min_confirmations,
                "require_trend_filter": self._filters.require_trend_filter,
            },
        })

        confirmations = int(stoch_confirm) + int(rsi_confirm)
        debug["confirmations"] = confirmations
        if confirmations < max(int(self._filters.min_confirmations), 1):
            if not stoch_confirm:
                debug["reasons"].append("stoch_not_confirming")
            if not rsi_confirm:
                debug["reasons"].append("rsi_not_confirming")
            return None, debug

        side = "long" if h1_trend == 1 else "short"

        # Confidence
        confidence = 0.35
        if stoch_confirm:
            confidence += 0.20
        if rsi_confirm:
            confidence += 0.20
        if atr_avg > 0 and last_atr > atr_avg:
            confidence += 0.10
        if vol_avg > 0 and last_vol > vol_avg:
            confidence += 0.10
        confidence = min(confidence, 1.0)

        debug["confidence"] = confidence

        if confidence < self._filters.min_confidence:
            debug["reasons"].append("confidence_below_min")
            return None, debug

        # Screen 3: stop-entry around the M15 signal candle.
        last_high = float(high.iloc[-1])
        last_low = float(low.iloc[-1])
        tick_buffer = max(last_atr * 0.05, float(close.iloc[-1]) * 0.0002)
        entry = last_high + tick_buffer if side == "long" else last_low - tick_buffer

        if body_ratio < 0.18:
            debug["reasons"].append("weak_signal_candle")
            return None, debug

        # Stop-loss: local extremum of last 10 M15 bars, minimum 1.0 ATR from entry
        lookback_sl = min(10, len(data))
        min_sl_dist = last_atr * 1.0

        if side == "long":
            sl_candidate = float(low.iloc[-lookback_sl:].min())
            stop_loss = min(sl_candidate, entry - min_sl_dist)
        else:
            sl_candidate = float(high.iloc[-lookback_sl:].max())
            stop_loss = max(sl_candidate, entry + min_sl_dist)

        risk = abs(entry - stop_loss)
        if risk <= 0:
            debug["reasons"].append("zero_risk")
            return None, debug
        if entry > 0 and risk / entry > 0.035:
            debug["reasons"].append("risk_too_wide")
            debug["risk_pct"] = risk / entry
            return None, debug

        # Take-profit: TP1=1.5R (breakeven trigger), TP2=2.5R (full exit)
        if side == "long":
            take_levels = [entry + 1.5 * risk, entry + 2.5 * risk]
        else:
            take_levels = [entry - 1.5 * risk, entry - 2.5 * risk]

        breakeven_at = take_levels[0]

        rationale = (
            f"three_screens: trend={'bull' if h1_trend == 1 else 'bear'} ({self.trend_timeframe} EMA26), "
            f"stoch(K={last_k:.1f}/D={last_d:.1f}), rsi={last_rsi:.1f} ({self.h1_timeframe}), "
            f"entry_order={'BUY STOP' if side == 'long' else 'SELL STOP'}, "
            f"atr={last_atr:.4f}, conf={confidence:.2f}, "
            f"entry={entry:.4f}, sl={stop_loss:.4f}, risk={risk:.4f}"
        )

        payload = {
            "signal_type": side,
            "confidence": confidence,
            "entry_price": entry,
            "stop_loss": stop_loss,
            "take_profit": take_levels[-1],
            "rationale": rationale,
            "meta": {
                "screen1": {
                    "timeframe": self.trend_timeframe,
                    "h1_trend": h1_trend,
                    "ema26_now": ema26_now,
                    "ema26_prev": ema26_prev,
                },
                "screen2": {
                    "timeframe": self.h1_timeframe,
                    "stoch_k": last_k,
                    "stoch_d": last_d,
                    "rsi": last_rsi,
                    "stoch_confirm": stoch_confirm,
                    "rsi_confirm": rsi_confirm,
                    "atr": last_atr,
                    "atr_avg": atr_avg,
                },
                "trade_plan": {
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_levels[-1],
                    "take_levels": take_levels,
                    "breakeven_at": breakeven_at,
                    "reward_risk": 2.5,
                    "stop_type": "atr_local_extremum",
                    "entry_order_type": "STOP_MARKET",
                    "entry_trigger": entry,
                },
                "entry_order": {
                    "type": "STOP_MARKET",
                    "label": "BUY STOP" if side == "long" else "SELL STOP",
                    "trigger": entry,
                    "buffer": tick_buffer,
                    "signal_candle_high": last_high,
                    "signal_candle_low": last_low,
                },
            },
        }

        return payload, debug
