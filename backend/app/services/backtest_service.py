from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd
import math

from app.repositories.candle_repository import CandleRepository
from app.strategies.base_strategy import BaseStrategy
from app.utils.candle_frame import candles_to_df


@dataclass
class BacktestTrade:
    id: int
    symbol: str
    timeframe: str
    side: str
    entry: float
    entry_time: int
    exit_price: float
    exit_time: int
    exit_reason: str
    pnl: float
    # Strategy context at entry (optional, but useful for visual review).
    confidence: float | None = None
    rationale: str | None = None
    chart_pattern: str | None = None
    candle_bullish: list[str] = field(default_factory=list)
    candle_bearish: list[str] = field(default_factory=list)
    trade_plan: dict | None = None
    tp_hits: list[dict] = field(default_factory=list)


@dataclass
class BacktestStats:
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    profit_factor: float | None
    max_drawdown: float
    max_drawdown_pct: float
    expectancy_pct: float
    sharpe: float | None
    cagr_pct: float | None
    ending_equity: float


class BacktestService:
    def __init__(self, candle_repository: CandleRepository, strategy: BaseStrategy) -> None:
        self._candle_repository = candle_repository
        self._strategy = strategy

    async def run(
        self,
        symbol: str,
        timeframe: str,
        window_bars: int,
        max_bars: int,
        stride: int,
        initial_equity: float = 10_000.0,
        risk_per_trade: float = 0.01,
        fee_bps: float = 4.0,
        slippage_bps: float = 2.0,
        intra_candle_mode: str = "pessimistic",
    ) -> tuple[list[BacktestTrade], BacktestStats]:
        candles = await self._candle_repository.latest(symbol, timeframe, limit=max_bars)
        if len(candles) < window_bars + 2:
            return [], BacktestStats(0, 0.0, 0.0, 0.0, None, 0.0, 0.0, 0.0, None, None, initial_equity)

        records = [
            {
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "dividends": float(getattr(candle, "dividends", 0.0) or 0.0),
                "stock_splits": float(getattr(candle, "stock_splits", 0.0) or 0.0),
                "open_time": candle.open_time,
            }
            for candle in candles
        ]
        data = pd.DataFrame(records)

        # MTF: load trend data once before the loop
        h1_data_indexed: pd.DataFrame | None = None
        if getattr(self._strategy, "is_mtf", False):
            trend_tf = getattr(self._strategy, "trend_timeframe", None) or getattr(self._strategy, "h1_timeframe", "1h")
            h1_candles = await self._candle_repository.latest(symbol, trend_tf, limit=5000)
            if h1_candles:
                h1_df = candles_to_df(h1_candles)
                h1_data_indexed = h1_df.set_index("open_time")

        trades: list[BacktestTrade] = []
        trade_id = 1
        next_allowed_idx = window_bars - 1  # cooldown: skip until previous trade closes
        for idx in range(window_bars - 1, len(data) - 1, max(stride, 1)):
            if idx < next_allowed_idx:
                continue
            window = data.iloc[idx - window_bars + 1 : idx + 1]
            context: dict | None = None
            if h1_data_indexed is not None:
                last_time = candles[idx].open_time
                h1_slice = h1_data_indexed[h1_data_indexed.index <= last_time]
                if len(h1_slice) >= 30:
                    trend_df_slice = h1_slice.reset_index()
                    context = {
                        "trend_data": trend_df_slice,
                        "h1_data": trend_df_slice,  # legacy compat
                        "timeframe": timeframe,
                    }
            elif context is None:
                context = {"timeframe": timeframe}
            payload = self._strategy.evaluate(window, context)
            if not payload:
                continue
            trade = self._simulate_trade(
                payload,
                data=data,
                candles=candles,
                start_index=idx + 1,
                window_bars=window_bars,
                symbol=symbol,
                timeframe=timeframe,
                trade_id=trade_id,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                intra_candle_mode=intra_candle_mode,
            )
            if trade:
                trades.append(trade)
                trade_id += 1
                # Don't enter a new trade until this one has closed
                next_allowed_idx = idx + 1 + self._trade_close_bar(trade, candles, idx + 1)

        stats = self._stats(trades, initial_equity=initial_equity, risk_per_trade=risk_per_trade)
        return trades, stats

    def _trade_close_bar(self, trade: "BacktestTrade", candles: list, start_index: int) -> int:
        """Return how many bars after start_index the trade closed (for cooldown)."""
        close_ts = trade.exit_time
        for offset, candle in enumerate(candles[start_index:], start=0):
            if int(candle.open_time.timestamp()) >= close_ts:
                return offset
        return len(candles) - start_index

    def _simulate_trade(
        self,
        payload: dict,
        data: pd.DataFrame,
        candles: Iterable,
        start_index: int,
        window_bars: int,
        symbol: str,
        timeframe: str,
        trade_id: int,
        fee_bps: float,
        slippage_bps: float,
        intra_candle_mode: str,
    ) -> BacktestTrade | None:
        candles = list(candles)
        if start_index >= len(candles):
            return None

        plan = (payload.get("meta") or {}).get("trade_plan") or {}
        entry = float(plan.get("entry") or payload.get("entry_price") or candles[start_index - 1].close)
        stop = plan.get("stop_loss") or payload.get("stop_loss")
        raw_tps = plan.get("take_levels") or [plan.get("take_profit") or payload.get("take_profit")]
        take_levels = [float(level) for level in raw_tps if level is not None]
        breakeven_at = plan.get("breakeven_at")

        side = 1 if payload.get("signal_type") == "long" else -1
        current_stop = float(stop) if stop is not None else None
        moved_to_be = False
        tp_hits: list[dict] = []
        weights: list[float] = []
        if take_levels:
            if len(take_levels) == 1:
                weights = [1.0]
            elif len(take_levels) == 2:
                weights = [0.5, 0.5]
            else:
                even = 1.0 / len(take_levels)
                weights = [even for _ in take_levels]
        remaining = 1.0
        realized_pnl = 0.0

        entry_time = int(candles[start_index - 1].open_time.timestamp())
        exit_price = candles[-1].close
        exit_time = int(candles[-1].open_time.timestamp())
        exit_reason = "OPEN"
        min_hold_seconds = int(plan.get("min_hold_seconds") or 0)

        for candle_index in range(start_index, len(candles)):
            candle = candles[candle_index]
            high = float(candle.high)
            low = float(candle.low)
            elapsed_seconds = int(candle.open_time.timestamp()) - entry_time
            hold_locked = elapsed_seconds < min_hold_seconds
            stop_hit = current_stop is not None and (low <= current_stop if side > 0 else high >= current_stop)

            # Handle ambiguous intra-candle hit order (both TP and SL touched).
            if take_levels and not hold_locked:
                final_tp_hit = False
                for index, level in enumerate(take_levels):
                    if any(hit["level"] == index + 1 for hit in tp_hits):
                        continue
                    hit_tp = high >= level if side > 0 else low <= level
                    if hit_tp:
                        if stop_hit and intra_candle_mode == "pessimistic":
                            continue
                        tp_hits.append(
                            {
                                "level": index + 1,
                                "price": level,
                                "time": int(candle.open_time.timestamp()),
                            }
                        )
                        # Move stop to breakeven when TP1 is hit
                        if index == 0 and not moved_to_be:
                            current_stop = float(breakeven_at) if breakeven_at is not None else entry
                            moved_to_be = True
                        fill_price = self._apply_fill(level, side=side, is_exit=True, slippage_bps=slippage_bps)
                        trade_r = ((fill_price - entry) / entry) * 100 * side
                        w = min(weights[index] if index < len(weights) else 0.0, remaining)
                        realized_pnl += trade_r * w
                        remaining = max(0.0, remaining - w)
                        # Exit immediately when the last TP level is hit
                        if index + 1 == len(take_levels):
                            exit_price = fill_price
                            exit_time = int(candle.open_time.timestamp())
                            exit_reason = f"TP{index + 1}"
                            final_tp_hit = True
                            break
                if final_tp_hit:
                    break

            if current_stop is not None and stop_hit:
                    stop_fill = self._apply_fill(current_stop, side=side, is_exit=True, slippage_bps=slippage_bps)
                    exit_price = stop_fill
                    exit_time = int(candle.open_time.timestamp())
                    exit_reason = "BE" if moved_to_be and abs(current_stop - entry) < entry * 0.0001 else "SL"
                    if remaining > 0:
                        trade_r = ((stop_fill - entry) / entry) * 100 * side
                        realized_pnl += trade_r * remaining
                        remaining = 0.0
                    break

            window_start = max(0, candle_index - window_bars + 1)
            window = data.iloc[window_start : candle_index + 1]
            opposite_payload = self._strategy.evaluate(window, {"timeframe": timeframe})
            if opposite_payload:
                opposite_side = 1 if opposite_payload.get("signal_type") == "long" else -1
                if opposite_side == -side and not hold_locked:
                    exit_price = self._apply_fill(float(candle.close), side=side, is_exit=True, slippage_bps=slippage_bps)
                    exit_time = int(candle.open_time.timestamp())
                    exit_reason = "OPPOSITE_SIGNAL"
                    if remaining > 0:
                        trade_r = ((exit_price - entry) / entry) * 100 * side
                        realized_pnl += trade_r * remaining
                        remaining = 0.0
                    break

        if remaining > 0:
            if exit_reason == "OPEN":
                exit_price = self._apply_fill(float(exit_price), side=side, is_exit=True, slippage_bps=slippage_bps)
            trade_r = ((exit_price - entry) / entry) * 100 * side
            realized_pnl += trade_r * remaining
        entry_fill = self._apply_fill(entry, side=side, is_exit=False, slippage_bps=slippage_bps)
        impact_pct = ((entry_fill - entry) / entry) * 100 * side
        fee_pct = 2 * (fee_bps / 10000.0) * 100
        pnl = realized_pnl - impact_pct - fee_pct
        meta = payload.get("meta") or {}
        chart_pattern = meta.get("chart_pattern") or {}
        candles_meta = meta.get("candles") or {}
        trade_plan = meta.get("trade_plan") or {}
        return BacktestTrade(
            id=trade_id,
            symbol=symbol,
            timeframe=timeframe,
            side="long" if side > 0 else "short",
            entry=entry,
            entry_time=entry_time,
            confidence=float(payload.get("confidence")) if payload.get("confidence") is not None else None,
            rationale=payload.get("rationale"),
            chart_pattern=chart_pattern.get("name") if isinstance(chart_pattern, dict) else None,
            candle_bullish=list(candles_meta.get("bullish") or []),
            candle_bearish=list(candles_meta.get("bearish") or []),
            trade_plan=trade_plan if isinstance(trade_plan, dict) else None,
            tp_hits=tp_hits,
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=exit_reason,
            pnl=pnl,
        )

    def _stats(self, trades: list[BacktestTrade], initial_equity: float, risk_per_trade: float) -> BacktestStats:
        if not trades:
            return BacktestStats(0, 0.0, 0.0, 0.0, None, 0.0, 0.0, 0.0, None, None, initial_equity)
        pnl_values = [trade.pnl for trade in trades]
        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p < 0]
        total_pnl = sum(pnl_values)
        avg_pnl = total_pnl / len(pnl_values)
        win_rate = (len(wins) / len(pnl_values)) * 100
        profit = sum(wins)
        loss = sum(abs(p) for p in losses)
        profit_factor = profit / loss if loss > 0 else None
        ending_equity, max_drawdown, max_drawdown_pct, sharpe, cagr = self._equity_stats(
            trades,
            initial_equity=initial_equity,
            risk_per_trade=risk_per_trade,
        )
        expectancy = avg_pnl
        return BacktestStats(
            total_trades=len(trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            expectancy_pct=expectancy,
            sharpe=sharpe,
            cagr_pct=cagr,
            ending_equity=ending_equity,
        )

    def _equity_stats(
        self,
        trades: list[BacktestTrade],
        initial_equity: float,
        risk_per_trade: float,
    ) -> tuple[float, float, float, float | None, float | None]:
        equity = float(initial_equity)
        peak = equity
        max_dd = 0.0
        trade_returns: list[float] = []
        for trade in trades:
            stop_loss = None
            if isinstance(trade.trade_plan, dict):
                stop_loss = trade.trade_plan.get("stop_loss")
            stop_dist_pct = 0.0
            try:
                if stop_loss is not None and trade.entry > 0:
                    stop_dist_pct = abs((trade.entry - float(stop_loss)) / trade.entry) * 100.0
            except Exception:
                stop_dist_pct = 0.0
            if stop_dist_pct > 0:
                r_multiple = trade.pnl / stop_dist_pct
                trade_ret = r_multiple * risk_per_trade
            else:
                # Fallback for legacy trades without stop in payload.
                trade_ret = (trade.pnl / 100.0) * risk_per_trade
            trade_returns.append(trade_ret)
            equity *= 1 + trade_ret
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = (max_dd / peak) * 100 if peak > 0 else 0.0

        sharpe = None
        if len(trade_returns) >= 2:
            mean_r = sum(trade_returns) / len(trade_returns)
            var = sum((r - mean_r) ** 2 for r in trade_returns) / (len(trade_returns) - 1)
            std = math.sqrt(var)
            if std > 0:
                sharpe = mean_r / std * math.sqrt(len(trade_returns))

        cagr = None
        if trades and initial_equity > 0:
            days = max((trades[-1].exit_time - trades[0].entry_time) / 86400.0, 1.0)
            years = days / 365.25
            if years > 0 and equity > 0:
                cagr = ((equity / initial_equity) ** (1 / years) - 1) * 100
        return equity, max_dd, max_dd_pct, sharpe, cagr

    def _apply_fill(self, price: float, side: int, is_exit: bool, slippage_bps: float) -> float:
        slip = (slippage_bps / 10000.0) * price
        if side > 0:
            return price - slip if is_exit else price + slip
        return price + slip if is_exit else price - slip
