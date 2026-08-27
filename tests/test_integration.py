"""End-to-end: spec -> data -> engine -> metrics -> report, all offline."""

import json
from pathlib import Path

import pytest

from rhbt.cli import main
from rhbt.report import render_html
from rhbt.runner import run_spec, run_spec_file
from rhbt.spec import Spec

SPEC = {
    "name": "Integration",
    "symbols": ["SPY", "QQQ"],
    "start": "2019-01-01",
    "cash": 10_000,
    "benchmark": "SPY",
    "params": {"fast": 20, "slow": 60},
    "rules": {
        "entry": "crossover(sma(close, fast), sma(close, slow))",
        "exit": "crossunder(sma(close, fast), sma(close, slow))",
    },
    "sizing": {"mode": "equal_weight"},
    "fees": {"slippage_bps": 5},
}


def test_spec_runs_end_to_end(cache):
    result = run_spec(Spec.from_dict(SPEC), offline=True)
    assert len(result.equity) > 100
    assert result.equity.iloc[0] == pytest.approx(10_000)
    assert result.metrics["trades"] >= 1
    assert not result.monthly.empty
    assert {"return_pct", "month_dd_pct", "dd_from_peak_pct"} <= set(result.monthly.columns)


def test_monthly_table_compounds_to_the_total_return(cache):
    result = run_spec(Spec.from_dict(SPEC), offline=True)
    compounded = (1 + result.monthly["return_pct"] / 100).prod() - 1
    assert compounded == pytest.approx(result.metrics["total_return"], rel=1e-9)


def test_warmup_means_the_first_bar_is_tradable(cache):
    """Without warm-up the 60-bar SMA is blind for a quarter; with it, it is not."""
    warm = run_spec(Spec.from_dict({**SPEC, "warmup": 250}), offline=True)
    cold = run_spec(Spec.from_dict({**SPEC, "warmup": 0}), offline=True)
    assert warm.meta["warmup_bars"] > 0
    assert cold.meta["warmup_bars"] == 0
    assert warm.equity.index[0] == cold.equity.index[0]


def test_risk_settings_change_the_outcome(cache):
    plain = run_spec(Spec.from_dict(SPEC), offline=True)
    stopped = run_spec(Spec.from_dict({**SPEC, "risk": {"stop_loss": 0.03}}), offline=True)
    assert stopped.metrics["trades"] >= plain.metrics["trades"]
    assert "stop_loss" in set(stopped.trades["exit_reason"])


def test_short_side_can_be_traded(cache):
    spec = Spec.from_dict({**SPEC, "rules": {
        "entry": "crossover(sma(close, fast), sma(close, slow))",
        "exit": "crossunder(sma(close, fast), sma(close, slow))",
        "short_entry": "crossunder(sma(close, fast), sma(close, slow))",
        "short_exit": "crossover(sma(close, fast), sma(close, slow))",
    }})
    result = run_spec(spec, offline=True)
    assert "short" in set(result.trades["side"])


def test_report_is_self_contained_html(cache, tmp_path):
    result = run_spec(Spec.from_dict(SPEC), offline=True)
    html = render_html(result, spec=SPEC)
    assert html.startswith("<!doctype html>")
    assert "Monthly returns" in html and "Month-by-month detail" in html
    for forbidden in ("http://", "https://cdn", "<script src"):
        assert forbidden not in html


def test_json_export_round_trips(cache, tmp_path):
    result = run_spec(Spec.from_dict(SPEC), offline=True)
    payload = json.loads(json.dumps(result.to_dict(), default=str))
    assert payload["metrics"]["max_drawdown"] <= 0
    assert len(payload["monthly"]) == len(result.monthly)


def test_cli_run_writes_a_report(cache, tmp_path, capsys):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(json.dumps(SPEC))
    report = tmp_path / "out.html"
    code = main(["run", str(spec_path), "--offline", "--report", str(report),
                 "--json", str(tmp_path / "out.json")])
    assert code == 0
    assert report.exists() and report.stat().st_size > 5_000
    out = capsys.readouterr().out
    assert "Max drawdown" in out and "Monthly performance" in out


def test_cli_reports_a_bad_rule_without_a_traceback(cache, tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text(json.dumps({**SPEC, "rules": {"entry": "smaa(close, 10) > 0"}}))
    assert main(["run", str(bad), "--offline"]) == 1
    assert "unknown name" in capsys.readouterr().err


def test_cli_sweep_ranks_parameter_sets(cache, tmp_path, capsys):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(json.dumps(SPEC))
    code = main(["sweep", str(spec_path), "--param", "fast=10,20", "--offline",
                 "--csv", str(tmp_path / "sweep.csv")])
    assert code == 0
    assert (tmp_path / "sweep.csv").exists()
    assert "sharpe" in capsys.readouterr().out


def test_cli_data_list_and_schema(cache, capsys):
    assert main(["data", "list"]) == 0
    assert "SPY" in capsys.readouterr().out
    assert main(["schema"]) == 0
    assert "indicators" in capsys.readouterr().out


def test_python_strategy_file_runs(cache, tmp_path, capsys):
    code = main(["run", "--strategy", "buy_and_hold", "--symbols", "SPY,QQQ",
                 "--offline", "--no-report", "--no-monthly"])
    assert code == 0
    assert "Total return" in capsys.readouterr().out
