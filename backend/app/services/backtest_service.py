from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from app.repositories.candle_repository import CandleRepository
from app.strategies.base_strategy import BaseStrategy


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
    ) -> tuple[list[BacktestTrade], BacktestStats]:
        candles = await self._candle_repository.latest(symbol, timeframe, limit=max_bars)
        if len(candles) < window_bars + 2:
            return [], BacktestStats(0, 0.0, 0.0, 0.0, None, 0.0)

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
        trades: list[BacktestTrade] = []
        trade_id = 1
        for idx in range(window_bars - 1, len(data) - 1, max(stride, 1)):
            window = data.iloc[idx - window_bars + 1 : idx + 1]
            payload = self._strategy.evaluate(window)
            if not payload:
                continue
            trade = self._simulate_trade(
                payload,
                candles,
                start_index=idx + 1,
                symbol=symbol,
                timeframe=timeframe,
                trade_id=trade_id,
            )
            if trade:
                trades.append(trade)
                trade_id += 1

        stats = self._stats(trades)
        return trades, stats

    def _simulate_trade(
        self,
        payload: dict,
        candles: Iterable,
        start_index: int,
        symbol: str,
        timeframe: str,
        trade_id: int,
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

        entry_time = int(candles[start_index - 1].open_time.timestamp())
        exit_price = candles[-1].close
        exit_time = int(candles[-1].open_time.timestamp())
        exit_reason = "OPEN"

        for candle in candles[start_index:]:
            high = float(candle.high)
            low = float(candle.low)

            if breakeven_at and not moved_to_be:
                if side > 0 and high >= breakeven_at:
                    current_stop = entry
                    moved_to_be = True
                if side < 0 and low <= breakeven_at:
                    current_stop = entry
                    moved_to_be = True

            if current_stop is not None:
                hit_stop = low <= current_stop if side > 0 else high >= current_stop
                if hit_stop:
                    exit_price = current_stop
                    exit_time = int(candle.open_time.timestamp())
                    exit_reason = "BE" if moved_to_be and abs(current_stop - entry) < entry * 0.0001 else "SL"
                    break

            if take_levels:
                for index, level in enumerate(take_levels):
                    if any(hit["level"] == index + 1 for hit in tp_hits):
                        continue
                    hit_tp = high >= level if side > 0 else low <= level
                    if hit_tp:
                        tp_hits.append(
                            {
                                "level": index + 1,
                                "price": level,
                                "time": int(candle.open_time.timestamp()),
                            }
                        )
                if tp_hits and len(tp_hits) >= len(take_levels):
                    last = tp_hits[-1]
                    exit_price = float(last["price"])
                    exit_time = int(candle.open_time.timestamp())
                    exit_reason = f"TP{last['level']}"
                    break

        pnl = ((exit_price - entry) / entry) * 100 * side
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

    def _stats(self, trades: list[BacktestTrade]) -> BacktestStats:
        if not trades:
            return BacktestStats(0, 0.0, 0.0, 0.0, None, 0.0)
        pnl_values = [trade.pnl for trade in trades]
        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p < 0]
        total_pnl = sum(pnl_values)
        avg_pnl = total_pnl / len(pnl_values)
        win_rate = (len(wins) / len(pnl_values)) * 100
        profit = sum(wins)
        loss = sum(abs(p) for p in losses)
        profit_factor = profit / loss if loss > 0 else None
        max_drawdown = self._max_drawdown(pnl_values)
        return BacktestStats(
            total_trades=len(trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
        )

    def _max_drawdown(self, pnl_values: list[float]) -> float:
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for pnl in pnl_values:
            equity += pnl
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_dd:
                max_dd = drawdown
        return max_dd
