from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC

import pandas as pd
import pytest

from app.services.backtest_service import BacktestService
from app.services.divergence_service import DivergenceService
from app.services.fibonacci_service import FibonacciService
from app.services.support_resistance_service import SupportResistanceService
from app.strategies.ema200_fib_divergence_strategy import Ema200FibDivergenceStrategy
from app.strategies.strategy_filters import StrategyFilters


def _make_ohlcv(closes: list[float]) -> pd.DataFrame:
    rows = []
    for idx, close in enumerate(closes):
        rows.append(
            {
                "open": close,
                "high": close + 0.8,
                "low": close - 0.8,
                "close": close,
                "volume": 200 + idx,
            }
        )
    return pd.DataFrame(rows)


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
    # Dense touch cluster around 105 plus sparse outliers.
    data.loc[[2, 4, 6, 8, 10], "high"] = [105.0, 105.2, 104.9, 105.1, 105.0]
    data.loc[[1, 5, 9], "low"] = [99.9, 100.1, 100.0]
    data.loc[11, "high"] = 112.0

    levels = SupportResistanceService().levels(data, window=2, tolerance=0.005)

    assert levels
    assert any(abs(level - 105.0) < 0.3 for level in levels)


def test_fibonacci_is_directional_for_up_and_down_impulses() -> None:
    fib = FibonacciService()

    up = pd.DataFrame(
        {
            "high": [100, 103, 106, 110],
            "low": [95, 96, 98, 100],
        }
    )
    up_levels = fib.levels(up, lookback=4)
    assert up_levels["0.618"] < up_levels["0.5"]

    down = pd.DataFrame(
        {
            "high": [110, 108, 104, 101],
            "low": [100, 98, 95, 92],
        }
    )
    down_levels = fib.levels(down, lookback=4)
    assert down_levels["0.618"] > down_levels["0.5"]


class _IndicatorStub:
    def __init__(self, ema_value: float) -> None:
        self._ema_value = ema_value

    def ema(self, close: pd.Series, period: int) -> pd.Series:
        return pd.Series([self._ema_value] * len(close))

    def rsi(self, close: pd.Series) -> pd.Series:
        return pd.Series([50.0] * len(close))


class _PatternStub:
    def scan_latest(self, data: pd.DataFrame) -> list[dict]:
        return [{"name": "bullish_engulfing", "signal": 1}]


class _ChartPatternStub:
    def best_pattern(self, data: pd.DataFrame) -> dict:
        return {"name": "ascending_triangle", "direction": "long", "confidence": 1.0}


class _DivergenceStub:
    def detect(self, data: pd.DataFrame, oscillator: pd.Series) -> dict[str, bool]:
        return {"bullish": True, "bearish": False}


class _SRStub:
    def levels(self, data: pd.DataFrame) -> list[float]:
        return [99.0, 101.0, 103.0, 105.0]


class _FibStub:
    def __init__(self, levels: dict[str, float]) -> None:
        self._levels = levels

    def levels(self, data: pd.DataFrame) -> dict[str, float]:
        return self._levels


class _ElliottStub:
    def analyze(self, data: pd.DataFrame) -> list[dict]:
        return []


@dataclass
class _Plan:
    entry: float
    stop_loss: float
    take_profit: float
    take_levels: list[float]
    breakeven_at: float
    reward_risk: float
    stop_type: str


class _TradePlanStub:
    def build(self, **kwargs) -> _Plan:
        entry = float(kwargs["entry"])
        return _Plan(
            entry=entry,
            stop_loss=entry - 2.0,
            take_profit=entry + 6.0,
            take_levels=[entry + 2.0, entry + 4.0, entry + 6.0],
            breakeven_at=entry + 2.0,
            reward_risk=3.0,
            stop_type="level",
        )


def _build_strategy(fib_levels: dict[str, float], ema_value: float = 100.0) -> Ema200FibDivergenceStrategy:
    return Ema200FibDivergenceStrategy(
        indicator_service=_IndicatorStub(ema_value=ema_value),
        pattern_service=_PatternStub(),
        chart_pattern_service=_ChartPatternStub(),
        divergence_service=_DivergenceStub(),
        support_resistance_service=_SRStub(),
        fibonacci_service=_FibStub(fib_levels),
        elliott_wave_service=_ElliottStub(),
        risk_service=object(),  # no longer used for strategy risk levels payload
        trade_plan_service=_TradePlanStub(),
        filters=StrategyFilters(min_confidence=0.0, min_confirmations=1),
    )


def test_strategy_requires_fib_or_ema_confluence() -> None:
    prices = [100.0 + i * 0.01 for i in range(220)]
    data = _make_ohlcv(prices)

    near_strategy = _build_strategy({"0.5": 102.1, "0.618": 102.2, "0.786": 102.3}, ema_value=102.0)
    near_signal = near_strategy.evaluate(data)
    assert near_signal is not None

    far_strategy = _build_strategy({"0.5": 97.0, "0.618": 96.5, "0.786": 96.0}, ema_value=95.0)
    far_signal = far_strategy.evaluate(data)
    assert far_signal is None


def test_strategy_risk_levels_match_trade_plan_levels() -> None:
    prices = [100.0 + i * 0.01 for i in range(220)]
    data = _make_ohlcv(prices)
    strategy = _build_strategy({"0.5": 102.1, "0.618": 102.2, "0.786": 102.3}, ema_value=102.0)

    payload = strategy.evaluate(data)

    assert payload is not None
    meta = payload["meta"]
    assert meta["risk_levels"]["stop_loss"] == meta["trade_plan"]["stop_loss"]
    assert meta["risk_levels"]["take_profit"] == meta["trade_plan"]["take_profit"]


@pytest.mark.parametrize(
    ("symbol", "base_price", "step"),
    [
        ("BTCUSDT", 68000.0, 3.0),
        ("ETHUSDT", 3400.0, 0.4),
        ("XRPUSDT", 0.58, 0.0003),
        ("SOLUSDT", 165.0, 0.08),
    ],
)
def test_strategy_is_scale_invariant_across_symbols(symbol: str, base_price: float, step: float) -> None:
    prices = [base_price + i * step for i in range(220)]
    data = _make_ohlcv(prices)
    last_close = prices[-1]
    strategy = _build_strategy(
        {
            "0.5": last_close * 0.999,
            "0.618": last_close * 1.0005,
            "0.786": last_close * 1.001,
        },
        ema_value=last_close * 0.9995,
    )

    payload = strategy.evaluate(data, {"timeframe": "1h", "symbol": symbol})

    assert payload is not None
    assert payload["signal_type"] in {"long", "short"}
    assert payload["meta"]["trade_plan"]["min_hold_seconds"] == 3600


def test_strategy_allows_only_1h_or_4h_for_position_mode() -> None:
    prices = [100.0 + i * 0.01 for i in range(220)]
    data = _make_ohlcv(prices)
    last_close = prices[-1]
    strategy = _build_strategy(
        {"0.5": last_close, "0.618": last_close * 1.001, "0.786": last_close * 0.999},
        ema_value=last_close * 0.998,
    )

    signal_1h = strategy.evaluate(data, {"timeframe": "1h"})
    signal_4h = strategy.evaluate(data, {"timeframe": "4h"})
    signal_15m = strategy.evaluate(data, {"timeframe": "15m"})

    assert signal_1h is not None
    assert signal_4h is not None
    assert signal_4h["meta"]["trade_plan"]["min_hold_seconds"] == 14400
    assert signal_15m is None


@dataclass
class _Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_time: datetime


class _RepoStub:
    async def latest(self, symbol: str, timeframe: str, limit: int):
        return []


class _OppositeSignalStrategy:
    def evaluate(self, data: pd.DataFrame, context: dict | None = None) -> dict | None:
        if len(data) >= 6:
            return {"signal_type": "short"}
        return None


def test_backtest_exits_on_opposite_signal() -> None:
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        _Candle(100, 101, 99.7, 100.2, 1000, base_time + timedelta(hours=i))
        for i in range(10)
    ]
    df = pd.DataFrame(
        {
            "open": [c.open for c in candles],
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
            "volume": [c.volume for c in candles],
        }
    )
    payload = {
        "signal_type": "long",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "meta": {
            "trade_plan": {
                "entry": 100.0,
                "stop_loss": 90.0,
                "take_levels": [120.0],
                "breakeven_at": 110.0,
            }
        },
    }
    service = BacktestService(candle_repository=_RepoStub(), strategy=_OppositeSignalStrategy())

    trade = service._simulate_trade(
        payload=payload,
        data=df,
        candles=candles,
        start_index=1,
        window_bars=6,
        symbol="BTCUSDT",
        timeframe="1h",
        trade_id=1,
        fee_bps=0.0,
        slippage_bps=0.0,
        intra_candle_mode="pessimistic",
    )

    assert trade is not None
    assert trade.exit_reason == "OPPOSITE_SIGNAL"
