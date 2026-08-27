import numpy as np
import pandas as pd
import pytest

from rhbt.metrics import (cagr, compute_metrics, drawdown_details, drawdown_series,
                          max_drawdown, monthly_table, period_table, sharpe)


def equity(values, start="2020-01-01", freq="B"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_drawdown_of_a_monotonic_curve_is_zero():
    assert max_drawdown(equity([100, 101, 102, 103])) == 0.0


def test_max_drawdown_is_peak_to_trough():
    assert max_drawdown(equity([100, 120, 60, 90])) == pytest.approx(-0.5)


def test_drawdown_details_finds_peak_trough_and_recovery():
    details = drawdown_details(equity([100, 120, 60, 90, 130]))
    assert details["max_drawdown"] == pytest.approx(-0.5)
    assert details["peak_date"] == "2020-01-02"
    assert details["trough_date"] == "2020-01-03"
    assert details["recovery_date"] == "2020-01-07"


def test_cagr_of_a_doubling_over_one_year():
    index = pd.DatetimeIndex(["2020-01-01", "2021-01-01"])
    # 2020 is a leap year, so 366/365.25 makes this a hair under a clean double.
    assert cagr(pd.Series([100.0, 200.0], index=index)) == pytest.approx(1.0, rel=5e-3)


def test_sharpe_of_a_flat_curve_is_zero():
    assert sharpe(equity([100.0] * 50)) == 0.0


def test_monthly_table_returns_chain_to_the_total():
    values = 100 * np.cumprod(1 + np.random.default_rng(0).normal(0.0005, 0.01, 400))
    curve = equity(values)
    table = monthly_table(curve)
    compounded = np.prod(1 + table["return_pct"] / 100.0)
    assert compounded == pytest.approx(curve.iloc[-1] / curve.iloc[0], rel=1e-9)


def test_month_drawdown_resets_each_month():
    index = pd.bdate_range("2020-01-01", periods=45)
    values = np.concatenate([np.linspace(100, 80, 23), np.linspace(80, 120, 22)])
    table = monthly_table(pd.Series(values, index=index))
    # January only falls, so its in-month drawdown is the full fall.
    assert table.loc["2020-01", "month_dd_pct"] < -15
    # February only rises, so nothing new is lost inside it...
    assert table.loc["2020-02", "month_dd_pct"] == pytest.approx(0.0, abs=1e-9)
    # ...but it is still underwater versus the all-time high for part of it.
    assert table.loc["2020-02", "dd_from_peak_pct"] < 0


def test_yearly_table_covers_every_year():
    curve = equity(np.linspace(100, 200, 800))
    table = period_table(curve, "Y")
    assert list(table.index) == ["2020", "2021", "2022", "2023"]


def test_compute_metrics_has_the_headline_fields():
    metrics = compute_metrics(equity(np.linspace(100, 150, 300)))
    for key in ("total_return", "cagr", "max_drawdown", "sharpe", "sortino",
                "calmar", "worst_month", "worst_month_drawdown", "monthly_win_rate"):
        assert key in metrics


def test_trade_stats_are_summarised():
    trades = pd.DataFrame({
        "pnl": [100.0, -50.0, 200.0, -25.0],
        "return_pct": [10.0, -5.0, 20.0, -2.5],
        "bars_held": [5, 3, 9, 2],
        "mae_pct": [-1.0, -6.0, -0.5, -3.0],
        "mfe_pct": [11.0, 1.0, 22.0, 0.5],
    })
    metrics = compute_metrics(equity(np.linspace(100, 150, 300)), trades=trades)
    assert metrics["trades"] == 4
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == pytest.approx(300 / 75)
    assert metrics["max_consecutive_losses"] == 1
