from __future__ import annotations

import pandas as pd


class DivergenceService:
    def detect(
        self,
        data: pd.DataFrame,
        oscillator: pd.Series,
        window: int = 5,
        min_right_window: int = 1,
    ) -> dict[str, bool]:
        highs = data["high"].to_numpy()
        lows = data["low"].to_numpy()
        osc = oscillator.to_numpy()

        price_highs: list[tuple[int, float]] = []
        price_lows: list[tuple[int, float]] = []
        osc_highs: list[tuple[int, float]] = []
        osc_lows: list[tuple[int, float]] = []

        for idx in range(window, len(data)):
            right_window = min(window, len(data) - idx - 1)
            if right_window < min_right_window:
                continue
            left = idx - window
            right = idx + right_window + 1
            if highs[idx] == highs[left:right].max():
                price_highs.append((idx, highs[idx]))
                osc_highs.append((idx, osc[idx]))
            if lows[idx] == lows[left:right].min():
                price_lows.append((idx, lows[idx]))
                osc_lows.append((idx, osc[idx]))

        bullish = False
        bearish = False
        if len(price_lows) >= 2 and len(osc_lows) >= 2:
            (_, price_low_1), (_, price_low_2) = price_lows[-2], price_lows[-1]
            (_, osc_low_1), (_, osc_low_2) = osc_lows[-2], osc_lows[-1]
            bullish = price_low_2 < price_low_1 and osc_low_2 > osc_low_1

        if len(price_highs) >= 2 and len(osc_highs) >= 2:
            (_, price_high_1), (_, price_high_2) = price_highs[-2], price_highs[-1]
            (_, osc_high_1), (_, osc_high_2) = osc_highs[-2], osc_highs[-1]
            bearish = price_high_2 > price_high_1 and osc_high_2 < osc_high_1

        return {"bullish": bullish, "bearish": bearish}
