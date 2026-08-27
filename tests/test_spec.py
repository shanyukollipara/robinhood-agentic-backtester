import pytest
import yaml

from rhbt.spec import Spec, SpecError


BASE = {
    "name": "Test",
    "symbols": ["SPY"],
    "rules": {"entry": "close > sma(close, 50)", "exit": "close < sma(close, 50)"},
}


def test_minimal_spec_parses():
    spec = Spec.from_dict(BASE)
    assert spec.symbols == ["SPY"]
    assert spec.cash == 10_000
    assert spec.benchmark == "SPY"


def test_symbols_accepts_a_string():
    assert Spec.from_dict({**BASE, "symbols": "AAPL, MSFT"}).symbols == ["AAPL", "MSFT"]


def test_missing_symbols_is_an_error():
    with pytest.raises(SpecError, match="symbols"):
        Spec.from_dict({"rules": BASE["rules"]})


def test_missing_entry_rule_is_an_error():
    with pytest.raises(SpecError, match="rules.entry"):
        Spec.from_dict({"symbols": ["SPY"], "rules": {"exit": "close < 1"}})


def test_typo_in_a_key_is_caught_with_a_suggestion():
    with pytest.raises(SpecError, match="Did you mean 'symbols'"):
        Spec.from_dict({**BASE, "symbol s": ["SPY"], "symbolz": ["SPY"]})


def test_unknown_nested_key_is_caught():
    with pytest.raises(SpecError, match="unknown key"):
        Spec.from_dict({**BASE, "risk": {"stoploss": 0.1}})


def test_bad_sizing_mode_is_caught():
    with pytest.raises(SpecError, match="sizing.mode"):
        Spec.from_dict({**BASE, "sizing": {"mode": "yolo"}})


def test_benchmark_can_be_switched_off():
    assert Spec.from_dict({**BASE, "benchmark": "none"}).benchmark is None


def test_run_config_carries_fees_and_risk():
    spec = Spec.from_dict({**BASE, "fees": {"slippage_bps": 12},
                           "risk": {"stop_loss": 0.05, "take_profit": 0.2}})
    config = spec.run_config()
    assert config.costs.slippage_bps == 12
    assert config.stop_loss == 0.05
    assert config.take_profit == 0.2


def test_short_rules_enable_shorting_by_default():
    spec = Spec.from_dict({**BASE, "rules": {**BASE["rules"], "short_entry": "close < sma(close, 200)"}})
    assert spec.run_config().allow_short is True


def test_every_bundled_example_is_valid(tmp_path):
    from pathlib import Path
    for path in sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.y*ml")):
        spec = Spec.load(path)
        assert spec.symbols and spec.rules.get("entry")
