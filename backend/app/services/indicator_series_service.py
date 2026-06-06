from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.services.chart_pattern_service import ChartPatternService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.indicator_service import IndicatorService
from app.services.pattern_service import PatternService
from app.services.support_resistance_service import SupportResistanceService
from app.utils.candle_frame import candles_to_df


class IndicatorSeriesService:
    def __init__(
        self,
        indicator_service: IndicatorService,
        pattern_service: PatternService,
        support_resistance_service: SupportResistanceService,
        elliott_wave_service: ElliottWaveService,
        chart_pattern_service: ChartPatternService,
    ) -> None:
        self._indicator_service = indicator_service
        self._pattern_service = pattern_service
        self._support_resistance_service = support_resistance_service
        self._elliott_wave_service = elliott_wave_service
        self._chart_pattern_service = chart_pattern_service

    def build(self, candles: list) -> dict:
        if not candles:
            return {
                "ema200": [],
                "bbands": {"upper": [], "middle": [], "lower": []},
                "atr": [],
                "rsi": [],
                "volume": [],
                "patterns": [],
                "support_resistance": [],
                "elliott": [],
                "chart_patterns": [],
            }

        data = candles_to_df(candles)
        def _to_epoch(ts_value: datetime | str) -> int:
            if isinstance(ts_value, datetime):
                ts = ts_value
            else:
                ts = datetime.fromisoformat(str(ts_value))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            return int(ts.timestamp())

        times = [_to_epoch(ts) for ts in data["open_time"].to_list()]

        close = data["close"].astype(float)
        high = data["high"].astype(float)
        low = data["low"].astype(float)

        ema200 = self._indicator_service.ema(close, 200)
        upper, middle, lower = self._indicator_service.bbands(close)
        atr = self._indicator_service.atr(high, low, close)
        rsi = self._indicator_service.rsi(close)
        patterns = self._pattern_service.scan_series(data, max_items=120)
        support_resistance = self._support_resistance_service.levels(data)
        elliott = self._elliott_wave_service.analyze(data)
        chart_patterns = self._chart_pattern_service.detect(data)

        def _series(values: pd.Series) -> list[dict]:
            points = []
            for idx, value in enumerate(values):
                if pd.isna(value):
                    continue
                points.append({"time": times[idx], "value": float(value)})
            return points

        def _volume_series(values: pd.Series) -> list[dict]:
            return [{"time": times[idx], "value": float(value)} for idx, value in enumerate(values)]

        pattern_markers = []
        for hit in patterns:
            idx = hit["index"]
            if idx >= len(times):
                continue
            pattern_markers.append(
                {
                    "time": times[idx],
                    "name": hit["name"],
                    "signal": hit["signal"],
                }
            )

        elliott_markers = []
        for pivot in elliott:
            idx = pivot.get("index")
            if idx is None or idx >= len(times):
                continue
            elliott_markers.append(
                {
                    "time": times[idx],
                    "price": float(pivot.get("price", 0)),
                    "kind": pivot.get("type", "pivot"),
                }
            )

        chart_markers = []
        for pattern in chart_patterns:
            idx = pattern.get("index", len(times) - 1)
            if idx is None or idx >= len(times):
                continue
            line_payloads = []
            for line in pattern.get("lines", []) or []:
                points = []
                for point in line.get("points", []):
                    pt_idx = point.get("index")
                    if pt_idx is None or pt_idx >= len(times):
                        continue
                    points.append({"time": times[pt_idx], "value": float(point.get("price", 0))})
                if len(points) >= 2:
                    line_payloads.append(
                        {
                            "role": line.get("role"),
                            "style": line.get("style", 2),
                            "color": line.get("color"),
                            "points": points,
                        }
                    )
            chart_markers.append(
                {
                    "time": times[idx],
                    "name": pattern.get("name"),
                    "direction": pattern.get("direction", "neutral"),
                    "confidence": float(pattern.get("confidence", 0)),
                    "state": "confirmed" if pattern.get("confirmed") else "candidate",
                    "confirmed": bool(pattern.get("confirmed")),
                    "breakout": float(pattern.get("breakout")) if isinstance(pattern.get("breakout"), (int, float)) else None,
                    "target": float(pattern.get("target")) if isinstance(pattern.get("target"), (int, float)) else None,
                    "stop_level": float(pattern.get("stop_level")) if isinstance(pattern.get("stop_level"), (int, float)) else None,
                    "lines": line_payloads,
                }
            )

        return {
            "ema200": _series(ema200),
            "bbands": {
                "upper": _series(upper),
                "middle": _series(middle),
                "lower": _series(lower),
            },
            "atr": _series(atr),
            "rsi": _series(rsi),
            "volume": _volume_series(data["volume"].astype(float)),
            "patterns": pattern_markers,
            "support_resistance": [float(level) for level in support_resistance],
            "elliott": elliott_markers,
            "chart_patterns": chart_markers,
        }
