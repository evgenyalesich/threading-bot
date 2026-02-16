from __future__ import annotations

import pandas as pd


class FibonacciService:
    def levels(self, data: pd.DataFrame, lookback: int = 120) -> dict[str, float]:
        segment = data.tail(lookback)
        swing_high = float(segment["high"].max())
        swing_low = float(segment["low"].min())
        diff = swing_high - swing_low
        if diff <= 0:
            return {}

        levels = {
            "0.236": swing_high - diff * 0.236,
            "0.382": swing_high - diff * 0.382,
            "0.5": swing_high - diff * 0.5,
            "0.618": swing_high - diff * 0.618,
            "0.786": swing_high - diff * 0.786,
            "1.0": swing_low,
        }
        return levels
