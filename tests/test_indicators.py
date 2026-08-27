import numpy as np
import pandas as pd

from rhbt.indicators import atr, crossover, rsi, sma, true_range, zscore
from tests.conftest import make_frame


def test_sma_matches_rolling_mean():
    frame = make_frame(seed=2, periods=100)
    assert np.allclose(sma(frame["close"], 10).dropna(),
                       frame["close"].rolling(10).mean().dropna())


def test_rsi_is_bounded():
    values = rsi(make_frame(seed=3, periods=300)["close"], 14).dropna()
    assert values.between(0, 100).all()


def test_rsi_of_a_pure_uptrend_is_100():
    rising = pd.Series(100 * (1.01 ** np.arange(60)), index=pd.bdate_range("2020-01-01", periods=60))
    assert rsi(rising, 14).dropna().iloc[-1] == 100.0


def test_true_range_is_never_negative():
    frame = make_frame(seed=4, periods=200)
    assert (true_range(frame["high"], frame["low"], frame["close"]).dropna() >= 0).all()


def test_atr_tracks_volatility():
    calm = make_frame(seed=5, periods=300, vol=0.002)
    wild = make_frame(seed=5, periods=300, vol=0.05)
    calm_atr = atr(calm["high"], calm["low"], calm["close"]).dropna().mean()
    wild_atr = atr(wild["high"], wild["low"], wild["close"]).dropna().mean()
    assert wild_atr > calm_atr


def test_crossover_fires_once():
    index = pd.bdate_range("2020-01-01", periods=6)
    a = pd.Series([1, 1, 3, 3, 3, 3], index=index, dtype=float)
    b = pd.Series([2, 2, 2, 2, 2, 2], index=index, dtype=float)
    fired = crossover(a, b)
    assert fired.sum() == 1 and fired.iloc[2]


def test_zscore_of_constant_series_is_nan_not_inf():
    flat = pd.Series(5.0, index=pd.bdate_range("2020-01-01", periods=40))
    assert zscore(flat, 10).dropna().empty
