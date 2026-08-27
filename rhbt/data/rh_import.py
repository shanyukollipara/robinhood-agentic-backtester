"""Normalise Robinhood Trading MCP historicals into OHLCV frames.

The repo never calls Robinhood itself - it has no credentials. Instead the
user's AI agent (which *is* connected to the Robinhood Trading MCP) calls
``get_equity_historicals`` and pipes the raw JSON response into::

    rhbt data import --interval day < bars.json

This module accepts the response in whatever reasonable shape it arrives:
a bare list of bars, ``{"results": [...]}``, ``{"AAPL": [...]}``, or a list of
per-symbol objects each carrying their own bars.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import pandas as pd

from .loader import DataError

_DATE_KEYS = ("begins_at", "timestamp", "date", "datetime", "time", "t", "start_time")
_FIELD_ALIASES = {
    "open": ("open_price", "open", "o", "open_value"),
    "high": ("high_price", "high", "h", "high_value"),
    "low": ("low_price", "low", "l", "low_value"),
    "close": ("close_price", "close", "c", "close_value", "last_trade_price"),
    "volume": ("volume", "v", "share_volume"),
}
_BAR_LIST_KEYS = ("historicals", "bars", "results", "data", "candles", "items", "prices")
_SYMBOL_KEYS = ("symbol", "ticker", "instrument_symbol", "Symbol")


class PayloadError(DataError):
    """Raised when a payload cannot be interpreted as historical bars."""


#: Backwards-compatible alias.
ImportError_ = PayloadError


def _num(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    if isinstance(value, dict):  # e.g. {"amount": "123.45", "currency": "USD"}
        for key in ("amount", "value", "price"):
            if key in value:
                return _num(value[key])
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _pick(bar: dict, aliases: Iterable[str]) -> Any:
    for alias in aliases:
        if alias in bar:
            return bar[alias]
    lowered = {str(k).lower(): v for k, v in bar.items()}
    for alias in aliases:
        if alias in lowered:
            return lowered[alias]
    return None


def _looks_like_bar(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    has_date = any(k in obj for k in _DATE_KEYS)
    has_close = _pick(obj, _FIELD_ALIASES["close"]) is not None
    return has_date and has_close


def _bars_to_frame(bars: list[dict]) -> pd.DataFrame:
    rows = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        stamp = None
        for key in _DATE_KEYS:
            if key in bar and bar[key] not in (None, ""):
                stamp = bar[key]
                break
        if stamp is None:
            continue
        if isinstance(stamp, (int, float)):
            unit = "ms" if float(stamp) > 1e11 else "s"
            ts = pd.to_datetime(float(stamp), unit=unit, utc=True)
        else:
            ts = pd.to_datetime(str(stamp), utc=True, errors="coerce")
        if pd.isna(ts):
            continue
        close = _num(_pick(bar, _FIELD_ALIASES["close"]))
        row = {
            "date": ts,
            "open": _num(_pick(bar, _FIELD_ALIASES["open"])),
            "high": _num(_pick(bar, _FIELD_ALIASES["high"])),
            "low": _num(_pick(bar, _FIELD_ALIASES["low"])),
            "close": close,
            "volume": _num(_pick(bar, _FIELD_ALIASES["volume"])),
        }
        for field in ("open", "high", "low"):
            if pd.isna(row[field]):
                row[field] = close
        if pd.isna(row["volume"]):
            row["volume"] = 0.0
        if pd.isna(close):
            continue
        rows.append(row)
    if not rows:
        raise PayloadError("no usable bars found in payload")
    frame = pd.DataFrame(rows).drop_duplicates(subset="date", keep="last")
    frame["date"] = frame["date"].dt.tz_convert(None).dt.normalize() if _is_daily(frame) else frame["date"].dt.tz_convert(None)
    return frame.set_index("date").sort_index()


def _is_daily(frame: pd.DataFrame) -> bool:
    if len(frame) < 3:
        return True
    deltas = frame["date"].sort_values().diff().dropna()
    return bool(deltas.min() >= pd.Timedelta("20h"))


def _walk_for_symbols(node: Any, out: dict[str, list[dict]], hint: str | None = None) -> None:
    """Depth-first search for (symbol, bars) pairs anywhere in the payload."""
    if isinstance(node, list):
        if node and all(_looks_like_bar(item) for item in node):
            out.setdefault(hint or "UNKNOWN", []).extend(node)
            return
        for item in node:
            _walk_for_symbols(item, out, hint)
        return
    if not isinstance(node, dict):
        return
    symbol = None
    for key in _SYMBOL_KEYS:
        if isinstance(node.get(key), str):
            symbol = node[key].strip().upper()
            break
    symbol = symbol or hint
    for key in _BAR_LIST_KEYS:
        value = node.get(key)
        if isinstance(value, list) and value and all(_looks_like_bar(b) for b in value):
            out.setdefault(symbol or "UNKNOWN", []).extend(value)
    for key, value in node.items():
        if key in _BAR_LIST_KEYS:
            if not (isinstance(value, list) and value and all(_looks_like_bar(b) for b in value)):
                _walk_for_symbols(value, out, symbol)
            continue
        if isinstance(value, list) and value and all(_looks_like_bar(b) for b in value):
            key_symbol = key.strip().upper() if str(key).replace("-", "").replace(".", "").isalnum() else symbol
            out.setdefault(key_symbol or symbol or "UNKNOWN", []).extend(value)
        elif isinstance(value, (dict, list)):
            nested_hint = key.strip().upper() if isinstance(key, str) and 1 <= len(key) <= 8 and key.replace("-", "").isalnum() else symbol
            _walk_for_symbols(value, out, nested_hint)


def normalize_robinhood_payload(payload: str | bytes | dict | list) -> dict[str, pd.DataFrame]:
    """Turn a Robinhood MCP historicals response into ``{symbol: OHLCV frame}``."""
    if isinstance(payload, (str, bytes)):
        text = payload.decode() if isinstance(payload, bytes) else payload
        text = text.strip()
        if not text:
            raise PayloadError("empty payload")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PayloadError(f"payload is not valid JSON: {exc}") from exc

    if isinstance(payload, list) and payload and all(_looks_like_bar(b) for b in payload):
        return {"UNKNOWN": _bars_to_frame(payload)}

    found: dict[str, list[dict]] = {}
    _walk_for_symbols(payload, found)
    if not found:
        raise PayloadError(
            "could not find any historical bars in the payload. Expected a list of "
            "bars with a date field (begins_at/date/timestamp) and a close price."
        )
    return {sym: _bars_to_frame(bars) for sym, bars in found.items() if bars}
