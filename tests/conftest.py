"""Deterministic synthetic prices so the suite never touches the network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rhbt.data import loader


def make_frame(seed: int = 0, periods: int = 900, drift: float = 0.0004,
               vol: float = 0.012, start: str = "2018-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(start, periods=periods)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, periods)))
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1 + rng.normal(0, 0.001, periods))
    high = np.maximum.reduce([close, open_]) * (1 + np.abs(rng.normal(0, 0.003, periods)))
    low = np.minimum.reduce([close, open_]) * (1 - np.abs(rng.normal(0, 0.003, periods)))
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": rng.integers(1_000_000, 5_000_000, periods).astype(float)},
        index=index,
    )


@pytest.fixture
def ramp() -> pd.DataFrame:
    """A price series that rises 1% a day, every day - easy to reason about."""
    index = pd.bdate_range("2020-01-01", periods=120)
    close = 100 * (1.01 ** np.arange(len(index)))
    return pd.DataFrame(
        {"open": close, "high": close * 1.001, "low": close * 0.999,
         "close": close, "volume": 1_000_000.0},
        index=index,
    )


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Point the price cache at a temp dir and preload a few symbols."""
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path / "cache")
    for i, symbol in enumerate(["SPY", "QQQ", "IWM"]):
        loader.write_cache(symbol, make_frame(seed=i), "day", source="test")
    return tmp_path / "cache"
