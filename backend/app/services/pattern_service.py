from __future__ import annotations

import pandas as pd


class PatternService:
    def available_patterns(self) -> list[str]:
        try:
            import talib
        except ImportError:
            return []
        return talib.get_function_groups().get("Pattern Recognition", [])

    def scan(self, data: pd.DataFrame, patterns: list[str] | None = None) -> dict[str, int]:
        try:
            import talib
        except ImportError:
            return {}

        patterns = patterns or self.available_patterns()
        if not patterns:
            return {}

        open_series = data["open"].astype(float).to_numpy()
        high_series = data["high"].astype(float).to_numpy()
        low_series = data["low"].astype(float).to_numpy()
        close_series = data["close"].astype(float).to_numpy()

        signals: dict[str, int] = {}
        for name in patterns:
            func = getattr(talib, name, None)
            if func is None:
                continue
            values = func(open_series, high_series, low_series, close_series)
            if len(values) == 0:
                continue
            last_value = int(values[-1])
            if last_value != 0:
                signals[name] = last_value
        return signals

    def scan_latest(
        self,
        data: pd.DataFrame,
        patterns: list[str] | None = None,
    ) -> list[dict]:
        try:
            import talib
        except ImportError:
            return []

        patterns = patterns or self.available_patterns()
        if not patterns:
            return []

        open_series = data["open"].astype(float).to_numpy()
        high_series = data["high"].astype(float).to_numpy()
        low_series = data["low"].astype(float).to_numpy()
        close_series = data["close"].astype(float).to_numpy()

        hits: list[dict] = []
        for name in patterns:
            func = getattr(talib, name, None)
            if func is None:
                continue
            values = func(open_series, high_series, low_series, close_series)
            if len(values) == 0:
                continue
            last_value = int(values[-1])
            if last_value == 0:
                continue
            hits.append({"name": name, "signal": last_value})
        return hits

    def scan_series(
        self,
        data: pd.DataFrame,
        patterns: list[str] | None = None,
        max_items: int = 200,
    ) -> list[dict]:
        try:
            import talib
        except ImportError:
            return []

        patterns = patterns or self.available_patterns()
        if not patterns:
            return []

        open_series = data["open"].astype(float).to_numpy()
        high_series = data["high"].astype(float).to_numpy()
        low_series = data["low"].astype(float).to_numpy()
        close_series = data["close"].astype(float).to_numpy()

        hits: list[dict] = []
        for name in patterns:
            func = getattr(talib, name, None)
            if func is None:
                continue
            values = func(open_series, high_series, low_series, close_series)
            for idx, value in enumerate(values):
                if value == 0:
                    continue
                hits.append({"index": idx, "name": name, "signal": int(value)})

        hits.sort(key=lambda item: item["index"])
        if max_items > 0 and len(hits) > max_items:
            hits = hits[-max_items:]
        return hits
