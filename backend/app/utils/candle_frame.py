from __future__ import annotations

import pandas as pd


def candles_to_df(candles: list) -> pd.DataFrame:
    """Build a pandas DataFrame compatible with yfinance-style OHLCV columns.

    We keep our internal column names lowercase for strategy code, but include
    `dividends` and `stock_splits` so the structure matches what users expect
    from yfinance output. For crypto candles these are typically 0.0.
    """

    return pd.DataFrame(
        [
            {
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume),
                "dividends": float(getattr(candle, "dividends", 0.0) or 0.0),
                "stock_splits": float(getattr(candle, "stock_splits", 0.0) or 0.0),
                "open_time": candle.open_time,
            }
            for candle in candles
        ]
    )

