import pandas as pd

try:
    import talib
except ImportError:  # pragma: no cover - optional dependency fallback
    talib = None


class IndicatorService:
    def ema(self, series: pd.Series, period: int) -> pd.Series:
        if talib:
            values = talib.EMA(series.to_numpy(dtype=float), timeperiod=period)
            return pd.Series(values, index=series.index)
        return series.ewm(span=period, adjust=False).mean()

    def rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        if talib:
            values = talib.RSI(series.to_numpy(dtype=float), timeperiod=period)
            return pd.Series(values, index=series.index).fillna(0)
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        # Wilder smoothing: alpha = 1/period
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(0)

    def atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        if talib:
            values = talib.ATR(
                high.to_numpy(dtype=float),
                low.to_numpy(dtype=float),
                close.to_numpy(dtype=float),
                timeperiod=period,
            )
            return pd.Series(values, index=close.index).fillna(0)
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        # Wilder smoothing for ATR
        return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().fillna(0)

    def bbands(
        self,
        series: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        if talib:
            upper, middle, lower = talib.BBANDS(
                series.to_numpy(dtype=float),
                timeperiod=period,
                nbdevup=std_dev,
                nbdevdn=std_dev,
                matype=0,
            )
            return (
                pd.Series(upper, index=series.index),
                pd.Series(middle, index=series.index),
                pd.Series(lower, index=series.index),
            )
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std(ddof=0)
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper.fillna(0), middle.fillna(0), lower.fillna(0)

    def stochastic(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 5,
        d_period: int = 3,
        smooth_k: int = 3,
    ) -> tuple[pd.Series, pd.Series]:
        if talib:
            slowk, slowd = talib.STOCH(
                high.to_numpy(dtype=float),
                low.to_numpy(dtype=float),
                close.to_numpy(dtype=float),
                fastk_period=k_period,
                slowk_period=smooth_k,
                slowk_matype=0,
                slowd_period=d_period,
                slowd_matype=0,
            )
            idx = close.index
            return pd.Series(slowk, index=idx).fillna(50), pd.Series(slowd, index=idx).fillna(50)
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, pd.NA)
        slow_k = raw_k.fillna(50).rolling(window=smooth_k).mean().fillna(50)
        slow_d = slow_k.rolling(window=d_period).mean().fillna(50)
        return slow_k, slow_d
