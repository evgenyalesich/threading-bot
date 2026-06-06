from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from app.services.divergence_service import DivergenceService
from app.services.fibonacci_service import FibonacciService
from app.services.order_sizing_service import OrderSizingService
from app.services.support_resistance_service import SupportResistanceService
from app.strategies.factory import build_strategy
from app.strategies.strategy_filters import StrategyFilters


def _make_ohlcv(closes: list[float], volume_base: float = 200.0) -> pd.DataFrame:
    rows = []
    for idx, close in enumerate(closes):
        rows.append(
            {
                "open": close,
                "high": close + max(close * 0.002, 0.8),
                "low": close - max(close * 0.002, 0.8),
                "close": close,
                "volume": volume_base + idx,
            }
        )
    return pd.DataFrame(rows)


def _trend_data(direction: str = "up") -> pd.DataFrame:
    if direction == "down":
        closes = [150 - i * 0.18 for i in range(260)]
    else:
        closes = [100 + i * 0.18 for i in range(260)]
    return _make_ohlcv(closes, volume_base=900)


def _entry_pullback(direction: str = "up") -> pd.DataFrame:
    if direction == "down":
        closes = [130 - i * 0.11 for i in range(70)] + [122 + i * 0.18 for i in range(20)]
    else:
        closes = [100 + i * 0.11 for i in range(70)] + [108 - i * 0.18 for i in range(20)]
    data = _make_ohlcv(closes, volume_base=600)
    data.loc[data.index[-5:], "volume"] = [520, 500, 480, 460, 440]
    return data


class _MarketStub:
    async def list_pairs(self, market: str) -> list[dict]:
        return [
            {
                "symbol": "TESTUSDT",
                "step_size": 0.1,
                "min_qty": 1.0,
                "max_qty": 100000.0,
                "min_notional": 5.0,
                "tick_size": 0.01,
            }
        ]


@pytest.mark.asyncio
async def test_order_sizing_raises_quantity_to_pair_minimum() -> None:
    result = await OrderSizingService(_MarketStub()).size_order(
        "TESTUSDT",
        "futures",
        quote_amount=0.1,
        price=2.0,
        leverage=25,
    )

    assert result.error is None
    assert result.quantity == 2.5


def test_divergence_detects_recent_extrema_without_5_bar_delay() -> None:
    data = pd.DataFrame(
        {
            "high": [10.0, 10.8, 11.0, 10.9, 10.6, 10.5, 10.7, 10.9, 10.8, 10.7, 10.6, 10.5, 10.7],
            "low": [9.8, 9.4, 9.1, 8.8, 8.5, 8.3, 8.9, 9.0, 8.8, 8.6, 8.5, 7.8, 8.1],
            "close": [9.9, 10.1, 10.6, 10.4, 10.2, 10.1, 10.4, 10.7, 10.3, 10.0, 9.9, 9.7, 10.0],
        }
    )
    oscillator = pd.Series([45, 43, 41, 39, 37, 35, 36, 38, 37, 36, 37, 39, 38])

    result = DivergenceService().detect(data, oscillator, window=5, min_right_window=1)

    assert result["bullish"]
    assert not result["bearish"]


def test_support_resistance_clusters_by_touch_density() -> None:
    closes = [100, 101, 103, 101.5, 104.5, 102.0, 105.0, 102.5, 104.8, 102.2, 105.1, 103.0]
    data = _make_ohlcv(closes)
    data.loc[[2, 4, 6, 8, 10], "high"] = [105.0, 105.2, 104.9, 105.1, 105.0]
    data.loc[[1, 5, 9], "low"] = [99.9, 100.1, 100.0]
    data.loc[11, "high"] = 112.0

    levels = SupportResistanceService().levels(data, window=2, tolerance=0.005)

    assert levels
    assert any(abs(level - 105.0) < 0.3 for level in levels)


def test_fibonacci_is_directional_for_up_and_down_impulses() -> None:
    fib = FibonacciService()
    up_levels = fib.levels(pd.DataFrame({"high": [100, 103, 106, 110], "low": [95, 96, 98, 100]}), lookback=4)
    down_levels = fib.levels(pd.DataFrame({"high": [110, 108, 104, 101], "low": [100, 98, 95, 92]}), lookback=4)

    assert up_levels["0.618"] < up_levels["0.5"]
    assert down_levels["0.618"] > down_levels["0.5"]


def test_strategy_factory_maps_everything_to_unified_v3() -> None:
    filters = StrategyFilters()

    for name in ["unified_v3", "three_screens", "three_screens_liquidity", "adaptive_pattern_confluence", "ema200_fib_divergence"]:
        strategy = build_strategy(name, filters=filters)
        assert strategy.name == "unified_v3"


def test_unified_v3_balanced_produces_stop_entry_plan() -> None:
    strategy = build_strategy(
        "unified_v3",
        filters=StrategyFilters(min_confidence=0.0, min_confirmations=1, quality_mode="balanced"),
        h1_timeframe="15m",
        trend_timeframe="1h",
    )
    data = _entry_pullback("up")
    context = {
        "trend_data": _trend_data("up"),
        "timeframe": "15m",
        "now": datetime(2026, 6, 7, 10, 0, tzinfo=UTC),
        "order_book": {
            "bid_notional": 2_000_000,
            "ask_notional": 1_200_000,
            "imbalance": 0.25,
            "spread_pct": 0.01,
            "bid_walls": [{"price": float(data["close"].iloc[-1]), "notional": 500_000}],
            "ask_walls": [],
        },
    }

    payload = strategy.evaluate(data, context)

    assert payload is not None
    assert payload["signal_type"] == "long"
    assert payload["meta"]["strategy"] == "unified_v3"
    assert payload["meta"]["trade_plan"]["entry_order_type"] == "STOP_MARKET"
    assert payload["meta"]["trade_plan"]["take_levels"][0] > payload["entry_price"]
    assert payload["meta"]["confidence_score"] >= 3


def test_unified_v3_blocks_dom_against_trade() -> None:
    strategy = build_strategy(
        "unified_v3",
        filters=StrategyFilters(min_confidence=0.0, quality_mode="balanced"),
        h1_timeframe="15m",
        trend_timeframe="1h",
    )
    data = _entry_pullback("up")
    context = {
        "trend_data": _trend_data("up"),
        "timeframe": "15m",
        "now": datetime(2026, 6, 7, 10, 0, tzinfo=UTC),
        "order_book": {
            "bid_notional": 500_000,
            "ask_notional": 3_000_000,
            "imbalance": -0.55,
            "spread_pct": 0.01,
            "bid_walls": [{"price": float(data["close"].iloc[-1]), "notional": 500_000}],
            "ask_walls": [],
        },
    }

    debug = strategy.explain(data, context)
    payload = strategy.evaluate(data, context)

    assert payload is None
    assert "dom_opposite_pressure" in debug["reasons"]


def test_unified_v3_sniper_requires_dom_confirmation() -> None:
    strategy = build_strategy(
        "unified_v3",
        filters=StrategyFilters(min_confidence=0.0, quality_mode="sniper"),
        h1_timeframe="15m",
        trend_timeframe="1h",
    )
    data = _entry_pullback("up")
    context = {
        "trend_data": _trend_data("up"),
        "timeframe": "15m",
        "now": datetime(2026, 6, 7, 10, 0, tzinfo=UTC),
        "order_book": {
            "bid_notional": 1_000_000,
            "ask_notional": 1_000_000,
            "imbalance": 0.0,
            "spread_pct": 0.01,
            "bid_walls": [{"price": float(data["close"].iloc[-1]), "notional": 500_000}],
            "ask_walls": [],
        },
    }

    debug = strategy.explain(data, context)

    assert "dom_not_confirmed" in debug["reasons"]


def test_unified_v3_blocks_high_impact_news_window() -> None:
    strategy = build_strategy(
        "unified_v3",
        filters=StrategyFilters(min_confidence=0.0, quality_mode="balanced"),
        h1_timeframe="15m",
        trend_timeframe="1h",
    )
    data = _entry_pullback("up")
    context = {
        "trend_data": _trend_data("up"),
        "timeframe": "15m",
        "now": datetime(2026, 6, 7, 10, 0, tzinfo=UTC),
        "news_block": True,
        "blocking_news": [{"title": "FOMC rate decision", "impact": "high"}],
    }

    debug = strategy.explain(data, context)

    assert "news_blackout" in debug["reasons"]
