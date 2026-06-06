from __future__ import annotations

from app.services.chart_pattern_service import ChartPatternService
from app.services.divergence_service import DivergenceService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.fibonacci_service import FibonacciService
from app.services.indicator_service import IndicatorService
from app.services.pattern_service import PatternService
from app.services.risk_service import RiskService
from app.services.support_resistance_service import SupportResistanceService
from app.services.trade_plan_service import TradePlanService
from app.strategies.adaptive_pattern_confluence_strategy import AdaptivePatternConfluenceStrategy
from app.strategies.base_strategy import BaseStrategy
from app.strategies.ema200_fib_divergence_strategy import Ema200FibDivergenceStrategy
from app.strategies.strategy_filters import StrategyFilters
from app.strategies.three_screens_strategy import ThreeScreensStrategy


def normalize_strategy_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "adaptive": "adaptive_pattern_confluence",
        "adaptive_pattern": "adaptive_pattern_confluence",
        "pattern": "adaptive_pattern_confluence",
        "ema200_adaptive_pattern": "adaptive_pattern_confluence",
        "ema200_fib": "ema200_fib_divergence",
        "ema_fib": "ema200_fib_divergence",
        "elder": "three_screens",
        "elder_three_screens": "three_screens",
        "triple_screen": "three_screens",
    }
    return aliases.get(raw, raw or "adaptive_pattern_confluence")


def build_strategy(
    name: str | None,
    filters: StrategyFilters | None = None,
    h1_timeframe: str = "1h",
    trend_timeframe: str = "4h",
) -> BaseStrategy:
    strategy_name = normalize_strategy_name(name)
    effective_filters = filters or StrategyFilters()
    indicator_service = IndicatorService()

    if strategy_name == "three_screens":
        return ThreeScreensStrategy(
            indicator_service=indicator_service,
            trend_timeframe=trend_timeframe,
            h1_timeframe=h1_timeframe,
            filters=effective_filters,
        )

    common = {
        "indicator_service": indicator_service,
        "pattern_service": PatternService(),
        "chart_pattern_service": ChartPatternService(),
        "divergence_service": DivergenceService(),
        "support_resistance_service": SupportResistanceService(),
        "fibonacci_service": FibonacciService(),
        "elliott_wave_service": ElliottWaveService(),
        "trade_plan_service": TradePlanService(),
        "filters": effective_filters,
    }

    if strategy_name == "ema200_fib_divergence":
        return Ema200FibDivergenceStrategy(
            risk_service=RiskService(),
            **common,
        )

    strategy = AdaptivePatternConfluenceStrategy(**common)
    strategy.h1_timeframe = h1_timeframe
    strategy.trend_timeframe = trend_timeframe
    return strategy
