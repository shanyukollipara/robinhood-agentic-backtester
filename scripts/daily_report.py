#!/usr/bin/env python3
"""Re-run every bundled example strategy against fresh prices and record the result.

This is what the daily GitHub Actions workflow executes. Each run pulls the
latest bars, backtests every spec in ``examples/`` from its start date through
today, and writes three things:

* ``results/RESULTS.md``  - a human-readable snapshot, rendered into the README
* ``results/<name>.json`` - the full metrics blob for each strategy
* ``results/history.csv`` - one row per strategy per day, appended forever

That last file is the interesting one: over time it becomes a genuine
out-of-sample record of how these strategies did *after* they were published,
which is the only backtest number anyone should actually trust.
"""

from __future__ import annotations

import csv
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from rhbt.report import write_report          # noqa: E402
from rhbt.runner import run_spec              # noqa: E402
from rhbt.spec import Spec                    # noqa: E402

RESULTS_DIR = REPO_ROOT / "results"
REPORT_DIR = REPO_ROOT / "reports"
HISTORY = RESULTS_DIR / "history.csv"

HISTORY_FIELDS = [
    "run_date", "strategy", "symbols", "start", "end", "final_equity",
    "total_return_pct", "cagr_pct", "max_drawdown_pct", "worst_month_pct",
    "worst_month_dd_pct", "sharpe", "sortino", "calmar", "trades",
    "win_rate_pct", "avg_exposure_pct", "benchmark", "benchmark_return_pct",
]


def _pct(value, digits: int = 2) -> str:
    return "-" if value is None else f"{value * 100:.{digits}f}"


def run_all() -> tuple[list[dict], list[tuple[str, str]]]:
    rows, failures = [], []
    for path in sorted((REPO_ROOT / "examples").glob("*.y*ml")):
        try:
            spec = Spec.load(path)
            result = run_spec(spec, refresh=True)
        except Exception as exc:                       # keep going; one bad ticker
            failures.append((path.name, f"{type(exc).__name__}: {exc}"))
            traceback.print_exc()
            continue

        metrics = result.metrics
        name = spec.name
        slug = path.stem

        (RESULTS_DIR / f"{slug}.json").write_text(
            json.dumps(result.to_dict(), indent=2, default=str)
        )
        write_report(result, REPORT_DIR / f"{slug}.html", spec=spec.to_dict())

        rows.append({
            "slug": slug,
            "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "strategy": name,
            "symbols": " ".join(result.symbols),
            "start": metrics.get("start"),
            "end": metrics.get("end"),
            "final_equity": f"{metrics.get('final_equity', 0):.2f}",
            "total_return_pct": _pct(metrics.get("total_return")),
            "cagr_pct": _pct(metrics.get("cagr")),
            "max_drawdown_pct": _pct(metrics.get("max_drawdown")),
            "worst_month_pct": _pct(metrics.get("worst_month")),
            "worst_month_dd_pct": _pct(metrics.get("worst_month_drawdown")),
            "sharpe": f"{metrics.get('sharpe', 0):.2f}",
            "sortino": f"{metrics.get('sortino', 0):.2f}",
            "calmar": f"{metrics.get('calmar', 0):.2f}",
            "trades": str(metrics.get("trades", 0)),
            "win_rate_pct": _pct(metrics.get("win_rate"), 1),
            "avg_exposure_pct": _pct(metrics.get("avg_exposure"), 1),
            "benchmark": result.benchmark_symbol or "-",
            "benchmark_return_pct": _pct(metrics.get("benchmark_total_return")),
            "_monthly": result.monthly,
        })
        print(f"  ok  {name:<22} return {rows[-1]['total_return_pct']:>8}%  "
              f"maxDD {rows[-1]['max_drawdown_pct']:>7}%  trades {rows[-1]['trades']}")
    return rows, failures


def append_history(rows: list[dict]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not HISTORY.exists()
    with HISTORY.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in HISTORY_FIELDS})


def write_markdown(rows: list[dict], failures: list[tuple[str, str]]) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Live results",
        "",
        f"Every strategy in [`examples/`](../examples) re-run against fresh market data on "
        f"**{stamp}**. Regenerated daily by "
        "[`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - "
        "these numbers move because the market moved, not because anything was tuned.",
        "",
        "| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| [{row['strategy']}](../examples/{row['slug']}.yaml) | `{row['symbols']}` | "
            f"{row['start']} | {row['total_return_pct']}% | {row['cagr_pct']}% | "
            f"{row['max_drawdown_pct']}% | {row['worst_month_pct']}% | {row['sharpe']} | "
            f"{row['trades']} | {row['win_rate_pct']}% | "
            f"{row['benchmark']} {row['benchmark_return_pct']}% |"
        )

    lines += [
        "",
        "## Last 6 months, month by month",
        "",
        "Return and the worst peak-to-trough fall *inside* each month.",
        "",
    ]
    for row in rows:
        monthly = row["_monthly"].tail(6)
        lines += [f"### {row['strategy']}", "",
                  "| Month | Return | Max DD in month | DD vs all-time high | End equity |",
                  "|---|---|---|---|---|"]
        for month, data in monthly.iterrows():
            lines.append(
                f"| {month} | {data['return_pct']:+.2f}% | {data['month_dd_pct']:.2f}% | "
                f"{data['dd_from_peak_pct']:.2f}% | ${data['end_equity']:,.2f} |"
            )
        lines.append("")

    if failures:
        lines += ["## Strategies that did not run today", ""]
        lines += [f"- `{name}` - {error}" for name, error in failures]
        lines.append("")

    lines += [
        "---",
        "",
        "Full history of every daily run: [`history.csv`](history.csv). "
        "Per-strategy metrics: the `.json` files beside it. "
        "Interactive tearsheets are rebuilt into [`reports/`](../reports).",
        "",
        "A backtest is a simulation over historical prices, not advice, and not a "
        "promise about the future. See the disclaimer in the [README](../README.md).",
    ]
    (RESULTS_DIR / "RESULTS.md").write_text("\n".join(lines))


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    print("Running every example strategy against fresh data...\n")
    rows, failures = run_all()
    if not rows:
        print("\nNo strategy completed - refusing to write an empty snapshot.")
        for name, error in failures:
            print(f"  {name}: {error}")
        return 1
    append_history(rows)
    write_markdown(rows, failures)
    print(f"\nWrote results for {len(rows)} strategies"
          f"{f', {len(failures)} failed' if failures else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
