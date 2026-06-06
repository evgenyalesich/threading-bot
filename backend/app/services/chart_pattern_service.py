from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PivotPoint:
    index: int
    price: float
    kind: str


class ChartPatternService:
    def __init__(
        self,
        pivot_window: int = 4,
        slope_tolerance: float = 0.00012,
        level_tolerance: float = 0.01,
    ) -> None:
        self._pivot_window = pivot_window
        self._slope_tolerance = slope_tolerance
        self._level_tolerance = level_tolerance

    def detect(self, data: pd.DataFrame) -> list[dict]:
        if len(data) < 80:
            return []

        pivots = self._pivot_points(data)
        if not pivots:
            return []

        patterns: list[dict] = []
        patterns.extend(self._detect_triangles(data, pivots))
        patterns.extend(self._detect_double_tops(data, pivots))
        patterns.extend(self._detect_head_shoulders(data, pivots))
        patterns.extend(self._detect_flags(data))
        patterns.extend(self._detect_cup_handle(data))
        return patterns

    def _line_segment(
        self,
        start_index: int,
        start_price: float,
        end_index: int,
        end_price: float,
        role: str,
        color: str,
        style: int = 2,
    ) -> dict:
        return {
            "role": role,
            "style": style,
            "color": color,
            "points": [
                {"index": int(start_index), "price": float(start_price)},
                {"index": int(end_index), "price": float(end_price)},
            ],
        }

    def best_pattern(self, data: pd.DataFrame) -> dict | None:
        patterns = [item for item in self.detect(data) if item.get("confirmed")]
        if not patterns:
            return None
        return max(patterns, key=lambda item: item.get("confidence", 0))

    def _pivot_points(self, data: pd.DataFrame) -> list[PivotPoint]:
        highs = data["high"].to_numpy(dtype=float)
        lows = data["low"].to_numpy(dtype=float)
        window = self._pivot_window
        pivots: list[PivotPoint] = []
        for idx in range(window, len(data) - window):
            high_slice = highs[idx - window : idx + window + 1]
            low_slice = lows[idx - window : idx + window + 1]
            if highs[idx] >= high_slice.max():
                pivots.append(PivotPoint(index=idx, price=float(highs[idx]), kind="high"))
            if lows[idx] <= low_slice.min():
                pivots.append(PivotPoint(index=idx, price=float(lows[idx]), kind="low"))
        pivots.sort(key=lambda item: item.index)
        return pivots

    def _detect_triangles(self, data: pd.DataFrame, pivots: list[PivotPoint]) -> list[dict]:
        highs = [pivot for pivot in pivots if pivot.kind == "high"][-3:]
        lows = [pivot for pivot in pivots if pivot.kind == "low"][-3:]
        if len(highs) < 3 or len(lows) < 3:
            return []

        high_slope = (highs[-1].price - highs[0].price) / max(highs[-1].index - highs[0].index, 1)
        low_slope = (lows[-1].price - lows[0].price) / max(lows[-1].index - lows[0].index, 1)
        high_slope_pct = high_slope / highs[0].price
        low_slope_pct = low_slope / lows[0].price

        range_start = highs[0].price - lows[0].price
        range_end = highs[-1].price - lows[-1].price
        shrink = 0.0
        if range_start > 0:
            shrink = max(0.0, min(1.0, 1 - range_end / range_start))

        last_close = float(data["close"].iloc[-1])
        patterns: list[dict] = []
        upper_line = self._line_segment(
            highs[0].index,
            highs[0].price,
            highs[-1].index,
            highs[-1].price,
            "upper",
            "#60a5fa",
        )
        lower_line = self._line_segment(
            lows[0].index,
            lows[0].price,
            lows[-1].index,
            lows[-1].price,
            "lower",
            "#34d399",
        )

        if abs(high_slope_pct) <= self._slope_tolerance and low_slope_pct > self._slope_tolerance:
            resistance = np.mean([highs[-1].price, highs[-2].price])
            confirmed = last_close > resistance
            target = resistance + range_start if range_start > 0 else None
            patterns.append(
                {
                    "name": "ascending_triangle",
                    "direction": "long",
                    "confidence": min(0.9, 0.55 + shrink * 0.4),
                    "breakout": resistance,
                    "target": target,
                    "stop_level": lows[-1].price,
                    "confirmed": confirmed,
                    "index": len(data) - 1,
                    "lines": [upper_line, lower_line],
                }
            )
        if abs(low_slope_pct) <= self._slope_tolerance and high_slope_pct < -self._slope_tolerance:
            support = np.mean([lows[-1].price, lows[-2].price])
            confirmed = last_close < support
            target = support - range_start if range_start > 0 else None
            patterns.append(
                {
                    "name": "descending_triangle",
                    "direction": "short",
                    "confidence": min(0.9, 0.55 + shrink * 0.4),
                    "breakout": support,
                    "target": target,
                    "stop_level": highs[-1].price,
                    "confirmed": confirmed,
                    "index": len(data) - 1,
                    "lines": [upper_line, lower_line],
                }
            )
        if high_slope_pct < -self._slope_tolerance and low_slope_pct > self._slope_tolerance:
            upper = highs[-1].price
            lower = lows[-1].price
            if last_close > upper:
                direction = "long"
                breakout = upper
                target = upper + range_start if range_start > 0 else None
                stop_level = lower
                confirmed = True
            elif last_close < lower:
                direction = "short"
                breakout = lower
                target = lower - range_start if range_start > 0 else None
                stop_level = upper
                confirmed = True
            else:
                direction = "neutral"
                breakout = (upper + lower) / 2
                target = None
                stop_level = lower
                confirmed = False
            patterns.append(
                {
                    "name": "sym_triangle",
                    "direction": direction,
                    "confidence": min(0.88, 0.5 + shrink * 0.35),
                    "breakout": breakout,
                    "target": target,
                    "stop_level": stop_level,
                    "confirmed": confirmed,
                    "index": len(data) - 1,
                    "lines": [upper_line, lower_line],
                }
            )
        return patterns

    def _detect_double_tops(self, data: pd.DataFrame, pivots: list[PivotPoint]) -> list[dict]:
        highs = [pivot for pivot in pivots if pivot.kind == "high"][-2:]
        lows = [pivot for pivot in pivots if pivot.kind == "low"][-2:]
        patterns: list[dict] = []
        last_close = float(data["close"].iloc[-1])

        if len(highs) == 2 and highs[1].index > highs[0].index:
            avg_high = (highs[0].price + highs[1].price) / 2
            diff = abs(highs[0].price - highs[1].price) / avg_high
            valley = float(data["low"].iloc[highs[0].index : highs[1].index].min())
            drop = (avg_high - valley) / avg_high
            if diff <= self._level_tolerance and drop >= 0.012:
                neckline = valley
                confirmed = last_close < neckline
                peak_line = self._line_segment(
                    highs[0].index,
                    highs[0].price,
                    highs[1].index,
                    highs[1].price,
                    "peaks",
                    "#fb7185",
                )
                neck_line = self._line_segment(
                    highs[0].index,
                    neckline,
                    highs[1].index,
                    neckline,
                    "neckline",
                    "#94a3b8",
                )
                patterns.append(
                    {
                        "name": "double_top",
                        "direction": "short",
                        "confidence": min(0.9, 0.6 + (1 - diff / self._level_tolerance) * 0.3),
                        "breakout": neckline,
                        "target": neckline - (avg_high - neckline),
                        "stop_level": max(highs[0].price, highs[1].price),
                        "confirmed": confirmed,
                        "index": len(data) - 1,
                        "lines": [peak_line, neck_line],
                    }
                )

        if len(lows) == 2 and lows[1].index > lows[0].index:
            avg_low = (lows[0].price + lows[1].price) / 2
            diff = abs(lows[0].price - lows[1].price) / avg_low
            peak = float(data["high"].iloc[lows[0].index : lows[1].index].max())
            rise = (peak - avg_low) / avg_low
            if diff <= self._level_tolerance and rise >= 0.012:
                neckline = peak
                confirmed = last_close > neckline
                trough_line = self._line_segment(
                    lows[0].index,
                    lows[0].price,
                    lows[1].index,
                    lows[1].price,
                    "troughs",
                    "#38bdf8",
                )
                neck_line = self._line_segment(
                    lows[0].index,
                    neckline,
                    lows[1].index,
                    neckline,
                    "neckline",
                    "#94a3b8",
                )
                patterns.append(
                    {
                        "name": "double_bottom",
                        "direction": "long",
                        "confidence": min(0.9, 0.6 + (1 - diff / self._level_tolerance) * 0.3),
                        "breakout": neckline,
                        "target": neckline + (neckline - avg_low),
                        "stop_level": min(lows[0].price, lows[1].price),
                        "confirmed": confirmed,
                        "index": len(data) - 1,
                        "lines": [trough_line, neck_line],
                    }
                )

        return patterns

    def _detect_head_shoulders(self, data: pd.DataFrame, pivots: list[PivotPoint]) -> list[dict]:
        highs = [pivot for pivot in pivots if pivot.kind == "high"][-3:]
        lows = [pivot for pivot in pivots if pivot.kind == "low"][-3:]
        patterns: list[dict] = []
        last_close = float(data["close"].iloc[-1])

        if len(highs) == 3 and len(lows) >= 2:
            left, head, right = highs
            if head.price > left.price and head.price > right.price:
                shoulder_diff = abs(left.price - right.price) / max(left.price, right.price)
                head_gap = (head.price - max(left.price, right.price)) / head.price
                if shoulder_diff <= self._level_tolerance and head_gap >= 0.015:
                    low_between = [
                        float(data["low"].iloc[left.index : head.index].min()),
                        float(data["low"].iloc[head.index : right.index].min()),
                    ]
                    neckline = sum(low_between) / len(low_between)
                    confirmed = last_close < neckline
                    neck_line = self._line_segment(
                        left.index,
                        neckline,
                        right.index,
                        neckline,
                        "neckline",
                        "#94a3b8",
                    )
                    patterns.append(
                        {
                            "name": "head_shoulders",
                            "direction": "short",
                            "confidence": min(0.92, 0.6 + (1 - shoulder_diff / self._level_tolerance) * 0.3),
                            "breakout": neckline,
                            "target": neckline - (head.price - neckline),
                            "stop_level": right.price,
                            "confirmed": confirmed,
                            "index": len(data) - 1,
                            "lines": [neck_line],
                        }
                    )

        if len(lows) == 3 and len(highs) >= 2:
            left, head, right = lows
            if head.price < left.price and head.price < right.price:
                shoulder_diff = abs(left.price - right.price) / max(left.price, right.price)
                head_gap = (min(left.price, right.price) - head.price) / min(left.price, right.price)
                if shoulder_diff <= self._level_tolerance and head_gap >= 0.015:
                    high_between = [
                        float(data["high"].iloc[left.index : head.index].max()),
                        float(data["high"].iloc[head.index : right.index].max()),
                    ]
                    neckline = sum(high_between) / len(high_between)
                    confirmed = last_close > neckline
                    neck_line = self._line_segment(
                        left.index,
                        neckline,
                        right.index,
                        neckline,
                        "neckline",
                        "#94a3b8",
                    )
                    patterns.append(
                        {
                            "name": "inverse_head_shoulders",
                            "direction": "long",
                            "confidence": min(0.92, 0.6 + (1 - shoulder_diff / self._level_tolerance) * 0.3),
                            "breakout": neckline,
                            "target": neckline + (neckline - head.price),
                            "stop_level": right.price,
                            "confirmed": confirmed,
                            "index": len(data) - 1,
                            "lines": [neck_line],
                        }
                    )
        return patterns

    def _detect_flags(self, data: pd.DataFrame) -> list[dict]:
        if len(data) < 60:
            return []

        closes = data["close"].to_numpy(dtype=float)
        recent = closes[-15:]
        prior = closes[-35:-15]
        if len(prior) < 10:
            return []

        prior_trend = (prior[-1] - prior[0]) / max(prior[0], 1e-9)
        recent_trend = (recent[-1] - recent[0]) / max(recent[0], 1e-9)
        prior_range = prior.max() - prior.min()
        recent_range = recent.max() - recent.min()
        last_close = float(closes[-1])

        patterns: list[dict] = []
        start_idx = len(data) - len(recent)
        end_idx = len(data) - 1
        recent_high = float(recent.max())
        recent_low = float(recent.min())
        upper_line = self._line_segment(start_idx, recent_high, end_idx, recent_high, "flag_upper", "#fbbf24")
        lower_line = self._line_segment(start_idx, recent_low, end_idx, recent_low, "flag_lower", "#fbbf24")

        if prior_trend > 0.04 and abs(recent_trend) < 0.02 and recent_range < prior_range * 0.6:
            breakout = float(recent.max())
            confirmed = last_close > breakout
            patterns.append(
                {
                    "name": "bull_flag",
                    "direction": "long",
                    "confidence": min(0.88, 0.55 + min(prior_trend, 0.1) * 2),
                    "breakout": breakout,
                    "stop_level": float(recent.min()),
                    "confirmed": confirmed,
                    "index": len(data) - 1,
                    "lines": [upper_line, lower_line],
                }
            )
        if prior_trend < -0.04 and abs(recent_trend) < 0.02 and recent_range < prior_range * 0.6:
            breakout = float(recent.min())
            confirmed = last_close < breakout
            patterns.append(
                {
                    "name": "bear_flag",
                    "direction": "short",
                    "confidence": min(0.88, 0.55 + min(abs(prior_trend), 0.1) * 2),
                    "breakout": breakout,
                    "stop_level": float(recent.max()),
                    "confirmed": confirmed,
                    "index": len(data) - 1,
                    "lines": [upper_line, lower_line],
                }
            )
        return patterns

    def _detect_cup_handle(self, data: pd.DataFrame) -> list[dict]:
        if len(data) < 80:
            return []

        closes = data["close"].to_numpy(dtype=float)
        window = closes[-80:]
        left_window = window[:25]
        right_window = window[-25:]
        left_peak = float(left_window.max())
        right_peak = float(right_window.max())
        if left_peak <= 0:
            return []
        peak_diff = abs(left_peak - right_peak) / left_peak
        if peak_diff > 0.02:
            return []

        mid_low = window[25:-25].min()
        depth = (left_peak - mid_low) / left_peak
        if depth < 0.04:
            return []

        handle = window[-12:]
        handle_low = handle.min()
        handle_depth = (right_peak - handle_low) / right_peak
        if handle_depth > depth * 0.6:
            return []

        left_peak_index = len(data) - 80 + int(left_window.argmax())
        right_peak_index = len(data) - 25 + int(right_window.argmax())
        handle_start_index = len(data) - 12
        handle_end_index = len(data) - 1
        rim_line = self._line_segment(
            left_peak_index,
            left_peak,
            right_peak_index,
            right_peak,
            "rim",
            "#38bdf8",
        )
        handle_line = self._line_segment(
            handle_start_index,
            handle_low,
            handle_end_index,
            handle_low,
            "handle",
            "#f59e0b",
        )

        last_close = float(closes[-1])
        breakout = right_peak
        confirmed = last_close > breakout
        return [
            {
                "name": "cup_handle",
                "direction": "long",
                "confidence": min(0.9, 0.6 + min(depth, 0.15)),
                "breakout": breakout,
                "stop_level": handle_low,
                "confirmed": confirmed,
                "index": len(data) - 1,
                "lines": [rim_line, handle_line],
            }
        ]
