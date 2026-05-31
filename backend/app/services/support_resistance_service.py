from __future__ import annotations

import numpy as np
import pandas as pd


class SupportResistanceService:
    def levels(self, data: pd.DataFrame, window: int = 5, tolerance: float = 0.005) -> list[float]:
        highs = data["high"].to_numpy()
        lows = data["low"].to_numpy()
        candidates: list[float] = []

        for idx in range(window, len(data)):
            right_window = min(window, len(data) - idx - 1)
            if right_window < 1:
                continue
            left = idx - window
            right = idx + right_window + 1
            local_high = highs[left:right].max()
            local_low = lows[left:right].min()
            if highs[idx] == local_high:
                candidates.append(float(highs[idx]))
            if lows[idx] == local_low:
                candidates.append(float(lows[idx]))

        if not candidates:
            return []

        candidates = sorted(candidates)
        clusters: list[list[float]] = []
        for level in candidates:
            if not clusters:
                clusters.append([level])
                continue
            cluster_mean = float(np.mean(clusters[-1]))
            if cluster_mean > 0 and abs(level - cluster_mean) / cluster_mean <= tolerance:
                clusters[-1].append(level)
            else:
                clusters.append([level])

        ranked = sorted(clusters, key=lambda cluster: (len(cluster), np.std(cluster) if len(cluster) > 1 else 0.0), reverse=True)
        levels = [float(np.mean(cluster)) for cluster in ranked]
        levels.sort()

        return levels
