from __future__ import annotations

import pandas as pd


class BaseStrategy:
    name = "base"

    def evaluate(self, data: pd.DataFrame) -> dict | None:
        raise NotImplementedError
