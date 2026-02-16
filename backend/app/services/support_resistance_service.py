from __future__ import annotations

import numpy as np
import pandas as pd


class SupportResistanceService:
    def levels(self, data: pd.DataFrame, window: int = 5, tolerance: float = 0.005) -> list[float]:
        highs = data["high"].to_numpy()
        lows = data["low"].to_numpy()
        candidates: list[float] = []

        for idx in range(window, len(data) - window):
            local_high = highs[idx - window : idx + window + 1].max()
            local_low = lows[idx - window : idx + window + 1].min()
            if highs[idx] == local_high:
                candidates.append(float(highs[idx]))
            if lows[idx] == local_low:
                candidates.append(float(lows[idx]))

        levels: list[float] = []
        for level in sorted(candidates):
            if not levels:
                levels.append(level)
                continue
            if abs(level - levels[-1]) / levels[-1] > tolerance:
                levels.append(level)

        return levels
