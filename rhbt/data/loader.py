"""Price loading: local CSV cache first, then yfinance.

Resolution order for every symbol:

1. ``data/cache/<SYMBOL>__<interval>.csv`` - populated by ``rhbt data import``
   (Robinhood MCP bars supplied by your agent) or by a previous download.
2. yfinance, if installed and the cache does not cover the requested range.

Set ``RHBT_DATA_DIR`` to move the cache somewhere else. Pass ``offline=True``
to forbid network access entirely.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

OHLCV = ["open", "high", "low", "close", "volume"]

_REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = Path(os.environ.get("RHBT_DATA_DIR") or (_REPO_ROOT / "data" / "cache"))


class DataError(RuntimeError):
    """Raised when price data cannot be obtained for a symbol."""


def cache_path(symbol: str, interval: str = "day") -> Path:
    safe = "".join(ch for ch in symbol.upper() if ch.isalnum() or ch in "-._")
    return CACHE_DIR / f"{safe}__{interval}.csv"


def _meta_path(symbol: str, interval: str) -> Path:
    return cache_path(symbol, interval).with_suffix(".meta.json")


def _coerce(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "adj close" in frame.columns and "close" not in frame.columns:
        frame["close"] = frame["adj close"]
    missing = [c for c in ("open", "high", "low", "close") if c not in frame.columns]
    if missing:
        raise DataError(f"price frame is missing columns: {missing}")
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    frame = frame[OHLCV].astype(float)
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    if frame.index.tz is not None:
        frame.index = frame.index.tz_convert(None)
    frame.index.name = "date"
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame.dropna(subset=["close"])


def write_cache(symbol: str, frame: pd.DataFrame, interval: str = "day",
                source: str = "unknown", merge: bool = True) -> Path:
    """Write (or merge into) the CSV cache for a symbol. Returns the file path."""
    frame = _coerce(frame)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(symbol, interval)
    if merge and path.exists():
        previous = _meta_path(symbol, interval)
        if previous.exists():
            try:
                old_source = json.loads(previous.read_text()).get("source")
            except Exception:
                old_source = None
            if old_source and old_source != source:
                print(f"[rhbt] warning: {symbol} cache already holds {old_source} bars; merging in "
                      f"{source} bars mixes price adjustments. Run 'rhbt data clear --symbol "
                      f"{symbol.upper()}' first if you want one clean source.")
        try:
            existing = _coerce(pd.read_csv(path, index_col=0, parse_dates=True))
            frame = pd.concat([existing, frame])
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
    frame.to_csv(path)
    _meta_path(symbol, interval).write_text(json.dumps({
        "symbol": symbol.upper(),
        "interval": interval,
        "source": source,
        "rows": int(len(frame)),
        "start": str(frame.index[0].date()) if len(frame) else None,
        "end": str(frame.index[-1].date()) if len(frame) else None,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }, indent=2))
    return path


def read_cache(symbol: str, interval: str = "day") -> pd.DataFrame | None:
    path = cache_path(symbol, interval)
    if not path.exists():
        return None
    try:
        return _coerce(pd.read_csv(path, index_col=0, parse_dates=True))
    except Exception:
        return None


def describe_cache() -> list[dict]:
    """Summarise every cached series (used by ``rhbt data list``)."""
    out = []
    if not CACHE_DIR.exists():
        return out
    for path in sorted(CACHE_DIR.glob("*__*.csv")):
        symbol, _, interval = path.stem.partition("__")
        meta_file = path.with_suffix(".meta.json")
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                meta = {}
        frame = read_cache(symbol, interval)
        out.append({
            "symbol": symbol,
            "interval": interval,
            "rows": len(frame) if frame is not None else 0,
            "start": str(frame.index[0].date()) if frame is not None and len(frame) else "-",
            "end": str(frame.index[-1].date()) if frame is not None and len(frame) else "-",
            "source": meta.get("source", "unknown"),
            "path": str(path),
        })
    return out


_YF_INTERVALS = {
    "day": "1d", "1d": "1d", "daily": "1d",
    "week": "1wk", "1wk": "1wk", "weekly": "1wk",
    "month": "1mo", "1mo": "1mo", "monthly": "1mo",
    "hour": "1h", "1h": "1h",
    "30minute": "30m", "30m": "30m",
    "15minute": "15m", "15m": "15m",
    "5minute": "5m", "5m": "5m",
    "minute": "1m", "1m": "1m",
}


def _download_yfinance(symbol: str, start, end, interval: str) -> pd.DataFrame:
    try:
        import yfinance  # type: ignore
    except ImportError as exc:
        raise DataError(
            f"no cached data for {symbol} and yfinance is not installed.\n"
            f"  Either:  pip install yfinance\n"
            f"  Or feed Robinhood bars in:  rhbt data import --symbol {symbol} < bars.json"
        ) from exc

    yf_interval = _YF_INTERVALS.get(str(interval).lower())
    if yf_interval is None:
        raise DataError(f"interval {interval!r} is not supported by the yfinance fallback")

    kwargs = dict(interval=yf_interval, auto_adjust=True, progress=False, threads=False)
    if start is not None:
        kwargs["start"] = str(pd.Timestamp(start).date())
    if end is not None:
        kwargs["end"] = str((pd.Timestamp(end) + pd.Timedelta(days=1)).date())
    if start is None and end is None:
        kwargs["period"] = "max"
    try:
        raw = yfinance.download(symbol, **kwargs)
    except Exception as exc:
        raise DataError(f"yfinance download failed for {symbol}: {exc}") from exc
    if raw is None or len(raw) == 0:
        raise DataError(f"yfinance returned no rows for {symbol!r} - is the ticker right?")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    return _coerce(raw)


def _covers(frame: pd.DataFrame | None, start, end, interval: str) -> bool:
    if frame is None or frame.empty:
        return False
    tol = pd.Timedelta(days=7 if str(interval).lower() in ("day", "1d", "daily") else 3)
    if start is not None and frame.index[0] > pd.Timestamp(start) + tol:
        return False
    if end is not None and frame.index[-1] < pd.Timestamp(end) - tol:
        return False
    return True


def load(symbol: str, start=None, end=None, interval: str = "day",
         refresh: bool = False, offline: bool = False) -> pd.DataFrame:
    """Load an OHLCV frame for one symbol, slicing to ``[start, end]``."""
    symbol = symbol.strip().upper()
    cached = None if refresh else read_cache(symbol, interval)
    frame = cached
    if not _covers(cached, start, end, interval):
        if offline:
            if cached is None:
                raise DataError(
                    f"no cached data for {symbol} ({interval}) and --offline was set. "
                    f"Import bars first: rhbt data import --symbol {symbol} < bars.json"
                )
        else:
            downloaded = _download_yfinance(symbol, start, end, interval)
            write_cache(symbol, downloaded, interval, source="yfinance")
            frame = read_cache(symbol, interval)
    if frame is None or frame.empty:
        raise DataError(f"no price data available for {symbol}")
    if start is not None:
        frame = frame[frame.index >= pd.Timestamp(start)]
    if end is not None:
        frame = frame[frame.index <= pd.Timestamp(end) + pd.Timedelta(hours=23, minutes=59)]
    if frame.empty:
        raise DataError(f"{symbol} has no bars between {start} and {end}")
    return frame


def load_many(symbols, start=None, end=None, interval: str = "day",
              refresh: bool = False, offline: bool = False) -> dict[str, pd.DataFrame]:
    """Load several symbols. Raises only if *every* symbol fails."""
    frames, errors = {}, {}
    for symbol in symbols:
        try:
            frames[symbol.strip().upper()] = load(symbol, start, end, interval, refresh, offline)
        except DataError as exc:
            errors[symbol] = str(exc)
    if not frames:
        detail = "\n".join(f"  {sym}: {msg}" for sym, msg in errors.items())
        raise DataError(f"could not load any symbols:\n{detail}")
    for symbol, msg in errors.items():
        print(f"[rhbt] warning: skipping {symbol}: {msg}")
    return frames
