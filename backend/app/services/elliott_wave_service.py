from __future__ import annotations

import pandas as pd


class ElliottWaveService:
    def analyze(self, data: pd.DataFrame, threshold: float = 0.03) -> list[dict]:
        closes = data["close"].to_list()
        if len(closes) < 2:
            return []

        pivots: list[dict] = []
        last_pivot_price = closes[0]
        last_pivot_index = 0
        direction = 0

        for idx, price in enumerate(closes[1:], start=1):
            change = (price - last_pivot_price) / last_pivot_price
            if direction >= 0 and change <= -threshold:
                pivots.append({"index": last_pivot_index, "price": last_pivot_price, "type": "high"})
                last_pivot_price = price
                last_pivot_index = idx
                direction = -1
            elif direction <= 0 and change >= threshold:
                pivots.append({"index": last_pivot_index, "price": last_pivot_price, "type": "low"})
                last_pivot_price = price
                last_pivot_index = idx
                direction = 1

        return pivots
