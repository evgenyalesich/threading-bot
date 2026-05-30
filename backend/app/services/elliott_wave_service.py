from __future__ import annotations

import pandas as pd


class ElliottWaveService:
    def analyze(self, data: pd.DataFrame, threshold: float = 0.03) -> list[dict]:
        closes = data["close"].to_list()
        if len(closes) < 2:
            return []

        pivots: list[dict] = []
        extreme_price = closes[0]
        extreme_index = 0
        direction = 0  # 1 uptrend leg, -1 downtrend leg, 0 unknown

        for idx, price in enumerate(closes[1:], start=1):
            if direction >= 0:
                if price >= extreme_price:
                    extreme_price = price
                    extreme_index = idx
                    direction = 1
                    continue
                change_down = (price - extreme_price) / extreme_price
                if change_down <= -threshold:
                    pivots.append({"index": extreme_index, "price": extreme_price, "type": "high"})
                    extreme_price = price
                    extreme_index = idx
                    direction = -1
                    continue

            if direction <= 0:
                if price <= extreme_price:
                    extreme_price = price
                    extreme_index = idx
                    direction = -1
                    continue
                change_up = (price - extreme_price) / extreme_price
                if change_up >= threshold:
                    pivots.append({"index": extreme_index, "price": extreme_price, "type": "low"})
                    extreme_price = price
                    extreme_index = idx
                    direction = 1

        if direction > 0:
            pivots.append({"index": extreme_index, "price": extreme_price, "type": "high"})
        elif direction < 0:
            pivots.append({"index": extreme_index, "price": extreme_price, "type": "low"})

        return pivots
