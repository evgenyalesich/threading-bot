from __future__ import annotations

import pandas as pd


class BaseStrategy:
    name = "base"
    is_mtf: bool = False

    def evaluate(self, data: pd.DataFrame, context: dict | None = None) -> dict | None:
        raise NotImplementedError
