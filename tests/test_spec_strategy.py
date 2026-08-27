"""Behaviour of the declarative rules, using prices designed to be obvious."""

import numpy as np
import pandas as pd
import pytest

from rhbt.engine import Backtest, RunConfig
from rhbt.portfolio import Costs
from rhbt.spec import Spec, SpecStrategy

NO_COST = RunConfig(cash=10_000, costs=Costs(slippage_bps=0))


def frame_from(closes):
    index = pd.bdate_range("2020-01-01", periods=len(closes))
    series = pd.Series(closes, index=index, dtype=float)
    return pd.DataFrame({"open": series, "high": series * 1.001, "low": series * 0.999,
                         "close": series, "volume": 1e6}, index=index)


def run(spec_dict, frames, config=None):
    spec = Spec.from_dict({"symbols": list(frames), **spec_dict})
    return Backtest(frames, SpecStrategy(spec), config or spec.run_config()).run()


def test_entry_and_exit_rules_fire_where_expected():
    frame = frame_from([10, 10, 20, 20, 20, 10, 10, 10])
    result = run({"rules": {"entry": "close > 15", "exit": "close < 15"},
                  "fees": {"slippage_bps": 0}}, {"X": frame})
    trade = result.trades.iloc[0]
    # Signalled on bar 2 (Fri 3 Jan), filled at bar 3's open (Mon 6 Jan).
    assert trade["entry_date"] == "2020-01-06"
    assert trade["exit_date"] == "2020-01-09"


def test_a_filter_rule_gates_entries():
    frame = frame_from([10, 20, 20, 20, 20, 20])
    blocked = run({"rules": {"entry": "close > 15", "exit": "close < 5", "filter": "close > 100"},
                   "fees": {"slippage_bps": 0}}, {"X": frame})
    assert blocked.trades.empty


def test_max_hold_bars_forces_an_exit():
    frame = frame_from([10] + [20] * 20)
    result = run({"rules": {"entry": "close > 15", "exit": "close < 1"},
                  "risk": {"max_hold_bars": 3}, "fees": {"slippage_bps": 0}}, {"X": frame})
    assert result.trades.iloc[0]["exit_reason"] == "max_hold"


def test_fixed_shares_sizing_buys_exactly_that_many():
    frame = frame_from([10] * 10)
    result = run({"rules": {"entry": "bar == 0", "exit": "bar > 100"},
                  "sizing": {"mode": "fixed_shares", "value": 7},
                  "fees": {"slippage_bps": 0}}, {"X": frame})
    assert result.fills[0].qty == pytest.approx(7)


def test_fixed_value_sizing_spends_exactly_that_much():
    frame = frame_from([10] * 10)
    result = run({"rules": {"entry": "bar == 0", "exit": "bar > 100"},
                  "sizing": {"mode": "fixed_value", "value": 2500},
                  "fees": {"slippage_bps": 0}}, {"X": frame})
    assert result.fills[0].qty * result.fills[0].price == pytest.approx(2500)


def test_monthly_rebalance_only_acts_once_a_month():
    closes = np.where(np.arange(120) % 2 == 0, 20.0, 21.0)
    result = run({"rules": {"entry": "close > 15", "exit": "close < 5"},
                  "rebalance": "monthly", "fees": {"slippage_bps": 0}},
                 {"X": frame_from(closes)})
    assert len(result.fills) <= 7   # one entry per month at most, plus liquidation


def test_equal_weight_splits_across_symbols():
    frames = {"A": frame_from([10] * 30), "B": frame_from([10] * 30)}
    result = run({"rules": {"entry": "bar == 0", "exit": "bar > 100"},
                  "sizing": {"mode": "equal_weight"}, "fees": {"slippage_bps": 0}}, frames)
    assert result.exposure.iloc[5] == pytest.approx(1.0, abs=0.01)
    assert len(result.trades) == 2
