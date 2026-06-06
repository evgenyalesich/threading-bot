from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyFilters:
    # Defaults are intentionally "test-friendly" to avoid a dead UI when data/logic is still evolving.
    # Users can tighten these from the UI.
    min_confidence: float = 0.45
    min_confirmations: int = 1
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
    min_trend_strength: float = 0.12
    min_reward_risk: float = 2.5
    allow_candidate_patterns: bool = False
    quality_mode: str = "sniper"
