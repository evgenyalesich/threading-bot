from __future__ import annotations

from app.services.chart_pattern_service import ChartPatternService
from app.services.divergence_service import DivergenceService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.fibonacci_service import FibonacciService
from app.services.indicator_service import IndicatorService
from app.services.pattern_service import PatternService
from app.services.support_resistance_service import SupportResistanceService
from app.strategies.base_strategy import BaseStrategy
from app.strategies.strategy_filters import StrategyFilters
from app.strategies.unified_strategy_v3 import UnifiedStrategyV3


def normalize_strategy_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "": "unified_v3",
        "v3": "unified_v3",
        "unified": "unified_v3",
        "single": "unified_v3",
        "top": "unified_v3",
        "three_screens": "unified_v3",
        "three_screens_liquidity": "unified_v3",
        "adaptive_pattern_confluence": "unified_v3",
        "ema200_fib_divergence": "unified_v3",
    }
    return aliases.get(raw, "unified_v3")


def build_strategy(
    name: str | None,
    filters: StrategyFilters | None = None,
    h1_timeframe: str = "15m",
    trend_timeframe: str = "1h",
) -> BaseStrategy:
    _strategy_name = normalize_strategy_name(name)
    return UnifiedStrategyV3(
        indicator_service=IndicatorService(),
        pattern_service=PatternService(),
        chart_pattern_service=ChartPatternService(),
        divergence_service=DivergenceService(),
        support_resistance_service=SupportResistanceService(),
        fibonacci_service=FibonacciService(),
        elliott_wave_service=ElliottWaveService(),
        filters=filters or StrategyFilters(),
        h1_timeframe=h1_timeframe,
        trend_timeframe=trend_timeframe,
    )
