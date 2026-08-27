"""Vectorised technical indicators.

Every function takes and returns a ``pandas.Series`` aligned to the price
index, so they compose freely inside strategy expressions:

    sma(close, 50) > sma(close, 200) and rsi(close, 14) < 30
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "sma", "ema", "wma", "rsi", "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_lower", "bb_mid", "bb_pct", "atr", "true_range",
    "stdev", "roc", "pct_change", "momentum", "highest", "lowest",
    "crossover", "crossunder", "zscore", "stoch_k", "stoch_d", "adx",
    "obv", "vwap", "donchian_high", "donchian_low", "rolling_max_drawdown",
    "shift", "abs_", "clip", "INDICATORS",
]


def _s(x) -> pd.Series:
    if isinstance(x, pd.Series):
        return x
    raise TypeError(f"expected a price series, got {type(x).__name__}")


def sma(series, window: int) -> pd.Series:
    """Simple moving average."""
    return _s(series).rolling(int(window), min_periods=int(window)).mean()


def ema(series, window: int) -> pd.Series:
    """Exponential moving average."""
    return _s(series).ewm(span=int(window), adjust=False, min_periods=int(window)).mean()


def wma(series, window: int) -> pd.Series:
    """Linearly weighted moving average."""
    w = np.arange(1, int(window) + 1, dtype=float)
    return _s(series).rolling(int(window)).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def stdev(series, window: int) -> pd.Series:
    """Rolling standard deviation."""
    return _s(series).rolling(int(window), min_periods=int(window)).std(ddof=0)


def rsi(series, window: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index (0-100)."""
    s = _s(series)
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / int(window), adjust=False, min_periods=int(window)).mean()
    avg_loss = loss.ewm(alpha=1.0 / int(window), adjust=False, min_periods=int(window)).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # A window with no losses at all is a maximally overbought reading, not NaN.
    all_gains = avg_loss.eq(0.0) & avg_gain.gt(0.0)
    return out.mask(out.isna() & all_gains, 100.0)


def macd(series, fast: int = 12, slow: int = 26) -> pd.Series:
    """MACD line: EMA(fast) - EMA(slow)."""
    s = _s(series)
    return ema(s, fast) - ema(s, slow)


def macd_signal(series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """Signal line of the MACD."""
    return ema(macd(series, fast, slow).dropna(), signal).reindex(_s(series).index)


def macd_hist(series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD histogram (line minus signal)."""
    return macd(series, fast, slow) - macd_signal(series, fast, slow, signal)


def bb_mid(series, window: int = 20) -> pd.Series:
    """Bollinger middle band."""
    return sma(series, window)


def bb_upper(series, window: int = 20, mult: float = 2.0) -> pd.Series:
    """Bollinger upper band."""
    return sma(series, window) + float(mult) * stdev(series, window)


def bb_lower(series, window: int = 20, mult: float = 2.0) -> pd.Series:
    """Bollinger lower band."""
    return sma(series, window) - float(mult) * stdev(series, window)


def bb_pct(series, window: int = 20, mult: float = 2.0) -> pd.Series:
    """Position within the Bollinger band: 0 at lower band, 1 at upper."""
    lo, up = bb_lower(series, window, mult), bb_upper(series, window, mult)
    return (_s(series) - lo) / (up - lo).replace(0.0, np.nan)


def true_range(high, low, close) -> pd.Series:
    """True range."""
    h, l, c = _s(high), _s(low), _s(close)
    prev = c.shift(1)
    return pd.Series(
        np.maximum.reduce([(h - l).to_numpy(), (h - prev).abs().to_numpy(), (l - prev).abs().to_numpy()]),
        index=c.index,
    )


def atr(high, low, close, window: int = 14) -> pd.Series:
    """Average true range (Wilder smoothing)."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / int(window), adjust=False, min_periods=int(window)).mean()


def roc(series, window: int = 1) -> pd.Series:
    """Rate of change over ``window`` bars, as a fraction (0.05 == +5%)."""
    return _s(series).pct_change(int(window))


pct_change = roc


def momentum(series, window: int = 10) -> pd.Series:
    """Absolute price change over ``window`` bars."""
    return _s(series).diff(int(window))


def highest(series, window: int) -> pd.Series:
    """Rolling maximum."""
    return _s(series).rolling(int(window), min_periods=1).max()


def lowest(series, window: int) -> pd.Series:
    """Rolling minimum."""
    return _s(series).rolling(int(window), min_periods=1).min()


def donchian_high(high, window: int = 20) -> pd.Series:
    """Donchian channel top, excluding the current bar."""
    return _s(high).shift(1).rolling(int(window), min_periods=int(window)).max()


def donchian_low(low, window: int = 20) -> pd.Series:
    """Donchian channel bottom, excluding the current bar."""
    return _s(low).shift(1).rolling(int(window), min_periods=int(window)).min()


def crossover(a, b) -> pd.Series:
    """True on the bar where ``a`` crosses above ``b``."""
    a, b = _s(a), (b if isinstance(b, pd.Series) else pd.Series(float(b), index=_s(a).index))
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a, b) -> pd.Series:
    """True on the bar where ``a`` crosses below ``b``."""
    a, b = _s(a), (b if isinstance(b, pd.Series) else pd.Series(float(b), index=_s(a).index))
    return (a < b) & (a.shift(1) >= b.shift(1))


def zscore(series, window: int = 20) -> pd.Series:
    """Rolling z-score."""
    s = _s(series)
    return (s - sma(s, window)) / stdev(s, window).replace(0.0, np.nan)


def stoch_k(high, low, close, window: int = 14) -> pd.Series:
    """Stochastic %K (0-100)."""
    hh = _s(high).rolling(int(window), min_periods=int(window)).max()
    ll = _s(low).rolling(int(window), min_periods=int(window)).min()
    return 100.0 * (_s(close) - ll) / (hh - ll).replace(0.0, np.nan)


def stoch_d(high, low, close, window: int = 14, smooth: int = 3) -> pd.Series:
    """Stochastic %D (smoothed %K)."""
    return stoch_k(high, low, close, window).rolling(int(smooth)).mean()


def adx(high, low, close, window: int = 14) -> pd.Series:
    """Average directional index (0-100)."""
    h, l = _s(high), _s(low)
    up, down = h.diff(), -l.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=h.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=h.index)
    tr = true_range(high, low, close)
    alpha = 1.0 / int(window)
    atr_ = tr.ewm(alpha=alpha, adjust=False, min_periods=int(window)).mean()
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_.replace(0.0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_.replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=alpha, adjust=False, min_periods=int(window)).mean()


def obv(close, volume) -> pd.Series:
    """On-balance volume."""
    c, v = _s(close), _s(volume)
    return (np.sign(c.diff().fillna(0.0)) * v).cumsum()


def vwap(high, low, close, volume, window: int = 20) -> pd.Series:
    """Rolling volume-weighted average price."""
    tp = (_s(high) + _s(low) + _s(close)) / 3.0
    v = _s(volume)
    w = int(window)
    return (tp * v).rolling(w, min_periods=w).sum() / v.rolling(w, min_periods=w).sum()


def rolling_max_drawdown(series, window: int = 252) -> pd.Series:
    """Rolling max drawdown of a price/equity series, as a negative fraction."""
    s = _s(series)
    peak = s.rolling(int(window), min_periods=1).max()
    return s / peak - 1.0


def shift(series, periods: int = 1) -> pd.Series:
    """Value from ``periods`` bars ago."""
    return _s(series).shift(int(periods))


def abs_(series) -> pd.Series:
    """Absolute value."""
    return _s(series).abs()


def clip(series, lo: float, hi: float) -> pd.Series:
    """Clamp a series between ``lo`` and ``hi``."""
    return _s(series).clip(float(lo), float(hi))


#: Name -> callable map exposed to strategy expressions.
INDICATORS = {
    "sma": sma, "ema": ema, "wma": wma, "rsi": rsi,
    "macd": macd, "macd_signal": macd_signal, "macd_hist": macd_hist,
    "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid, "bb_pct": bb_pct,
    "atr": atr, "true_range": true_range, "stdev": stdev, "std": stdev,
    "roc": roc, "pct_change": pct_change, "momentum": momentum,
    "highest": highest, "lowest": lowest, "max_of": highest, "min_of": lowest,
    "crossover": crossover, "crossunder": crossunder, "cross_above": crossover,
    "cross_below": crossunder, "zscore": zscore,
    "stoch_k": stoch_k, "stoch_d": stoch_d, "adx": adx, "obv": obv, "vwap": vwap,
    "donchian_high": donchian_high, "donchian_low": donchian_low,
    "rolling_max_drawdown": rolling_max_drawdown,
    "shift": shift, "prev": shift, "abs": abs_, "clip": clip,
}
