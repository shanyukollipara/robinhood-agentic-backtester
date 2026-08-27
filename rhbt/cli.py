"""Command line interface: ``rhbt run``, ``rhbt data``, ``rhbt sweep`` ...

Designed to be driven by an AI agent as much as by a human, so every command
fails with an explicit, actionable message and ``--json`` gives machine-readable
output.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import pandas as pd

from . import __version__
from .data import CACHE_DIR, DataError, cache_path, describe_cache, load, write_cache
from .data.rh_import import normalize_robinhood_payload
from .engine import Backtest, RunConfig
from .expr import ExpressionError
from .indicators import INDICATORS
from .portfolio import Costs
from .report import write_report
from .runner import _load_benchmark, _load_frames, load_strategy_class, run_spec, warmup_start
from .spec import (
    EXEC_KEYS, FEE_KEYS, RISK_KEYS, RULE_KEYS, SIZING_KEYS, SIZING_MODES,
    TOP_LEVEL, Spec, SpecError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = REPO_ROOT / "reports"


# --------------------------------------------------------------- formatting
def _pct(value, digits: int = 2, sign: bool = False) -> str:
    if value is None or value != value:
        return "-"
    return f"{'+' if sign and value > 0 else ''}{value * 100:.{digits}f}%"


def _money(value) -> str:
    return "-" if value is None or value != value else f"${value:,.2f}"


def _rule(width: int = 78) -> str:
    return "-" * width


def _print_summary(result) -> None:
    m = result.metrics
    print()
    print(_rule())
    print(f"  {result.strategy_name}   [{', '.join(result.symbols)}]")
    print(f"  {m.get('start')} to {m.get('end')}  ({m.get('bars')} bars, {m.get('years')} years)")
    if result.params:
        print(f"  params: {', '.join(f'{k}={v}' for k, v in result.params.items())}")
    print(_rule())
    rows = [
        ("Start equity", _money(m.get("initial_equity")), "Total return", _pct(m.get("total_return"), 2, True)),
        ("Final equity", _money(m.get("final_equity")), "CAGR", _pct(m.get("cagr"), 2, True)),
        ("Max drawdown", _pct(m.get("max_drawdown")), "Longest DD", f"{m.get('longest_drawdown_days', 0)} days"),
        ("Worst month", _pct(m.get("worst_month"), 2, True), "Worst in-month DD", _pct(m.get("worst_month_drawdown"))),
        ("Sharpe", f"{m.get('sharpe', 0):.2f}", "Sortino", f"{m.get('sortino', 0):.2f}"),
        ("Calmar", f"{m.get('calmar', 0):.2f}", "Volatility", _pct(m.get("volatility"))),
        ("Trades", str(m.get("trades", 0)), "Win rate", _pct(m.get("win_rate"), 1)),
        ("Profit factor", f"{m.get('profit_factor', 0):.2f}", "Expectancy", _money(m.get("expectancy"))),
        ("Avg exposure", _pct(m.get("avg_exposure"), 1), "Slippage cost", _money(result.meta.get("slippage_cost"))),
        ("Commissions", _money(result.meta.get("fees_paid")), "Fills", str(result.meta.get("fills", 0))),
    ]
    if "benchmark_total_return" in m:
        rows.append((f"{result.benchmark_symbol} return", _pct(m.get("benchmark_total_return"), 2, True),
                     "Alpha (annual)", _pct(m.get("alpha_annual"), 2, True)))
        rows.append((f"{result.benchmark_symbol} max DD", _pct(m.get("benchmark_max_drawdown")),
                     "Beta", f"{m.get('beta', 0):.2f}"))
    for left_label, left, right_label, right in rows:
        print(f"  {left_label:<18}{left:>14}    {right_label:<20}{right:>12}")
    print(_rule())


def _print_monthly(result, limit: int | None = None) -> None:
    monthly = result.monthly
    if monthly.empty:
        return
    has_bench = "benchmark_return_pct" in monthly.columns
    print("\n  Monthly performance and drawdown")
    header = f"  {'Month':<9}{'Return':>10}{'Max DD in mo':>15}{'DD vs ATH':>12}{'End equity':>15}"
    if has_bench:
        header += f"{'Benchmark':>12}"
    print(header)
    print(f"  {_rule(len(header) - 2)}")
    rows = monthly if limit is None else monthly.tail(limit)
    for month, row in rows.iterrows():
        line = (f"  {month:<9}{row['return_pct']:>9.2f}%{row['month_dd_pct']:>14.2f}%"
                f"{row['dd_from_peak_pct']:>11.2f}%{row['end_equity']:>15,.2f}")
        if has_bench:
            line += f"{row.get('benchmark_return_pct', float('nan')):>11.2f}%"
        print(line)
    if limit is not None and len(monthly) > limit:
        print(f"  ... {len(monthly) - limit} earlier months in the HTML report")
    print()


def _parse_params(pairs) -> dict:
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--param expects key=value, got {pair!r}")
        key, _, raw = pair.partition("=")
        out[key.strip()] = _coerce(raw.strip())
    return out


def _coerce(raw: str):
    lowered = raw.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("none", "null", ""):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _spec_from_args(args) -> Spec:
    """Build a Spec from CLI flags when no spec file was given."""
    if not args.symbols:
        raise SystemExit("give me something to trade: --symbols AAPL,MSFT (or pass a spec file)")
    symbols = [s.strip().upper() for s in ",".join(args.symbols).split(",") if s.strip()]
    if not args.entry:
        raise SystemExit(
            "no entry rule. Either pass a spec file (rhbt run mystrategy.yaml), "
            "a Python strategy (--strategy mine.py:MyStrategy), or inline rules "
            "(--entry 'rsi(close,2) < 10' --exit 'rsi(close,2) > 60')."
        )
    raw = {
        "name": args.name or "Inline strategy",
        "symbols": symbols,
        "start": args.start, "end": args.end, "interval": args.interval,
        "cash": args.cash, "benchmark": args.benchmark or "SPY",
        "rules": {k: v for k, v in
                  {"entry": args.entry, "exit": args.exit, "short_entry": args.short_entry,
                   "short_exit": args.short_exit}.items() if v},
        "params": _parse_params(args.param),
        "warmup": args.warmup,
    }
    return Spec.from_dict(raw)


def _apply_overrides(spec: Spec, args) -> Spec:
    """CLI flags win over whatever the spec file said."""
    if args.symbols:
        spec.symbols = [s.strip().upper() for s in ",".join(args.symbols).split(",") if s.strip()]
    for attr in ("start", "end", "name"):
        value = getattr(args, attr, None)
        if value:
            setattr(spec, attr, value)
    if args.interval and args.interval != "day":
        spec.interval = args.interval
    if args.cash is not None and args.cash != 10_000.0:
        spec.cash = args.cash
    if args.benchmark is not None:
        spec.benchmark = None if str(args.benchmark).lower() in ("none", "off", "") else args.benchmark.upper()
    if args.slippage_bps is not None:
        spec.fees["slippage_bps"] = args.slippage_bps
    if args.commission_bps is not None:
        spec.fees["commission_bps"] = args.commission_bps
    if args.fill:
        spec.execution["fill"] = args.fill
    if args.allow_short:
        spec.execution["allow_short"] = True
    if args.max_positions is not None:
        spec.execution["max_positions"] = args.max_positions
    if args.stop_loss is not None:
        spec.risk["stop_loss"] = args.stop_loss
    if args.take_profit is not None:
        spec.risk["take_profit"] = args.take_profit
    if args.trailing_stop is not None:
        spec.risk["trailing_stop"] = args.trailing_stop
    if args.warmup is not None:
        spec.warmup = args.warmup
    return spec


# ---------------------------------------------------------------- commands
def cmd_run(args) -> int:
    param_overrides = _parse_params(args.param)
    spec = None

    if args.strategy:
        cls = load_strategy_class(args.strategy)
        strategy = cls(**param_overrides)
        symbols = [s.strip().upper() for s in ",".join(args.symbols or []).split(",") if s.strip()]
        if not symbols:
            raise SystemExit("--strategy needs --symbols, e.g. --symbols AAPL,MSFT")
        config = RunConfig(
            cash=args.cash,
            costs=Costs(slippage_bps=args.slippage_bps if args.slippage_bps is not None else 5.0,
                        commission_bps=args.commission_bps or 0.0),
            fill=args.fill or "next_open",
            allow_short=args.allow_short,
            max_positions=args.max_positions,
            stop_loss=args.stop_loss,
            take_profit=args.take_profit,
            trailing_stop=args.trailing_stop,
            interval=args.interval,
        )
        load_start = warmup_start(args.start, args.warmup if args.warmup is not None else 250, args.interval)
        frames = _load_frames(symbols, load_start, args.end, args.interval, args.refresh, args.offline)
        bench_frame, bench_symbol = _load_benchmark(
            None if str(args.benchmark).lower() in ("none", "off") else (args.benchmark or "SPY"),
            load_start, args.end, args.interval, args.refresh, args.offline)
        result = Backtest(frames, strategy, config, bench_frame, bench_symbol,
                          trade_from=args.start).run()
    else:
        spec = Spec.load(args.spec) if args.spec else _spec_from_args(args)
        spec = _apply_overrides(spec, args)
        result = run_spec(spec, refresh=args.refresh, offline=args.offline,
                          param_overrides=param_overrides)

    _print_summary(result)
    if not args.no_monthly:
        _print_monthly(result, limit=None if args.all_months else 24)

    if args.json:
        payload = json.dumps(result.to_dict(), indent=2, default=str)
        if str(args.json) == "-":
            print(payload)
        else:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(payload)
            print(f"  JSON   {args.json}")

    if not args.no_report:
        default_name = "".join(ch if ch.isalnum() else "_" for ch in result.strategy_name).strip("_").lower()
        path = Path(args.report) if args.report else DEFAULT_REPORT_DIR / f"{default_name or 'backtest'}.html"
        write_report(result, path, spec=spec.to_dict() if spec else None)
        print(f"  Report {path}")
        if args.open:
            import webbrowser
            webbrowser.open(path.resolve().as_uri())
    print()
    return 0


def cmd_sweep(args) -> int:
    """Grid-search parameters and rank the runs."""
    spec = Spec.load(args.spec)
    grids = {}
    for pair in args.param:
        if "=" not in pair:
            raise SystemExit(f"--param expects key=v1,v2,v3 - got {pair!r}")
        key, _, raw = pair.partition("=")
        grids[key.strip()] = [_coerce(v.strip()) for v in raw.split(",") if v.strip()]
    if not grids:
        raise SystemExit("sweep needs at least one --param key=v1,v2,v3")

    keys = list(grids)
    combos = list(itertools.product(*(grids[k] for k in keys)))
    print(f"  Running {len(combos)} parameter combinations...\n")
    rows = []
    for combo in combos:
        overrides = dict(zip(keys, combo))
        try:
            result = run_spec(spec, refresh=False, offline=args.offline, param_overrides=overrides)
        except (SpecError, ExpressionError, DataError) as exc:
            print(f"  {overrides}  failed: {exc}")
            continue
        m = result.metrics
        rows.append({
            **overrides,
            "return_%": round(m.get("total_return", 0) * 100, 2),
            "cagr_%": round(m.get("cagr", 0) * 100, 2),
            "max_dd_%": round(m.get("max_drawdown", 0) * 100, 2),
            "sharpe": round(m.get("sharpe", 0), 2),
            "calmar": round(m.get("calmar", 0), 2),
            "trades": m.get("trades", 0),
            "win_%": round(m.get("win_rate", 0) * 100, 1),
        })
    if not rows:
        print("  every combination failed")
        return 1
    frame = pd.DataFrame(rows).sort_values(args.sort, ascending=False)
    print(frame.to_string(index=False))
    if args.csv:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False)
        print(f"\n  CSV    {args.csv}")
    print()
    return 0


def cmd_validate(args) -> int:
    spec = Spec.load(args.spec)
    print(f"  spec OK: {spec.name}")
    print(f"  symbols: {', '.join(spec.symbols)}")
    print(f"  window:  {spec.start or 'earliest available'} -> {spec.end or 'latest available'}")
    for key, rule in spec.rules.items():
        print(f"  rule {key}: {rule}")
    # Compile the rules against a synthetic frame so typos surface now.
    index = pd.date_range("2020-01-01", periods=320, freq="B")
    frame = pd.DataFrame({
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1e6,
    }, index=index)
    frame["close"] = 100 + pd.Series(range(len(index)), index=index) * 0.1
    from .expr import evaluate_bool
    for key, rule in spec.rules.items():
        try:
            evaluate_bool(rule, frame, spec.params)
        except ExpressionError as exc:
            print(f"\n  rule '{key}' is invalid:\n    {exc}")
            return 1
    print("\n  all rules compile.")
    return 0


def cmd_data_import(args) -> int:
    text = Path(args.file).read_text() if args.file else sys.stdin.read()
    frames = normalize_robinhood_payload(text)
    if args.symbol and len(frames) == 1:
        frames = {args.symbol.strip().upper(): next(iter(frames.values()))}
    unknown = [s for s in frames if s == "UNKNOWN"]
    if unknown:
        raise SystemExit(
            "the payload does not say which symbol these bars belong to - "
            "re-run with --symbol AAPL"
        )
    for symbol, frame in frames.items():
        path = write_cache(symbol, frame, interval=args.interval, source="robinhood-mcp")
        print(f"  imported {len(frame):>6} bars  {symbol:<8} "
              f"{frame.index[0].date()} -> {frame.index[-1].date()}  ({path})")
    return 0


def cmd_data_fetch(args) -> int:
    symbols = [s.strip().upper() for s in ",".join(args.symbols).split(",") if s.strip()]
    failed = False
    for symbol in symbols:
        try:
            frame = load(symbol, args.start, args.end, args.interval, refresh=True)
            print(f"  cached {len(frame):>6} bars  {symbol:<8} "
                  f"{frame.index[0].date()} -> {frame.index[-1].date()}")
        except DataError as exc:
            failed = True
            print(f"  {symbol}: {exc}")
    return 1 if failed else 0


def cmd_data_list(args) -> int:
    entries = describe_cache()
    if not entries:
        print(f"  cache is empty ({CACHE_DIR})")
        return 0
    print(f"  {'SYMBOL':<10}{'INTERVAL':<10}{'ROWS':>7}  {'FROM':<12}{'TO':<12}SOURCE")
    for entry in entries:
        print(f"  {entry['symbol']:<10}{entry['interval']:<10}{entry['rows']:>7}  "
              f"{entry['start']:<12}{entry['end']:<12}{entry['source']}")
    return 0


def cmd_data_clear(args) -> int:
    targets = list(CACHE_DIR.glob("*__*.csv")) + list(CACHE_DIR.glob("*.meta.json"))
    if args.symbol:
        wanted = args.symbol.strip().upper()
        targets = [p for p in targets if p.stem.partition("__")[0].upper() == wanted]
    if not targets:
        print("  nothing to remove")
        return 0
    for path in targets:
        path.unlink()
    print(f"  removed {len(targets)} cache files")
    return 0


def cmd_indicators(args) -> int:
    print("  Functions available inside entry/exit rule expressions:\n")
    seen = {}
    for name, fn in sorted(INDICATORS.items()):
        seen.setdefault(fn, []).append(name)
    for fn, names in sorted(seen.items(), key=lambda kv: kv[1][0]):
        import inspect as _inspect
        try:
            signature = str(_inspect.signature(fn))
        except (TypeError, ValueError):
            signature = "(...)"
        doc = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""
        print(f"  {'/'.join(names):<28}{signature}")
        if doc:
            print(f"  {'':<28}{doc}")
    print("\n  Price columns: open, high, low, close, volume, price, typical, returns")
    print("  Calendar:      bar, day, month, year, dayofweek")
    print("  Any key under `params:` in your spec is also usable by name.\n")
    return 0


def cmd_schema(args) -> int:
    schema = {
        "top_level_keys": sorted(TOP_LEVEL),
        "required": ["symbols", "rules.entry (or rules.short_entry)"],
        "rules": sorted(RULE_KEYS),
        "fees": sorted(FEE_KEYS),
        "execution": sorted(EXEC_KEYS),
        "risk": sorted(RISK_KEYS),
        "sizing": {"keys": sorted(SIZING_KEYS), "modes": sorted(SIZING_MODES)},
        "rebalance": ["every_bar", "daily", "weekly", "monthly", "quarterly"],
        "indicators": sorted(INDICATORS),
        "price_columns": ["open", "high", "low", "close", "volume", "price", "typical", "returns"],
        "example": {
            "name": "RSI dip buyer",
            "symbols": ["SPY", "QQQ"],
            "start": "2015-01-01",
            "cash": 10000,
            "benchmark": "SPY",
            "params": {"lookback": 2, "oversold": 10},
            "rules": {
                "entry": "rsi(close, lookback) < oversold and close > sma(close, 200)",
                "exit": "rsi(close, lookback) > 60",
            },
            "sizing": {"mode": "equal_weight"},
            "risk": {"stop_loss": 0.08, "max_hold_bars": 20},
            "fees": {"slippage_bps": 5},
            "execution": {"fill": "next_open"},
        },
    }
    print(json.dumps(schema, indent=2))
    return 0


def cmd_examples(args) -> int:
    examples = sorted((REPO_ROOT / "examples").glob("*.y*ml"))
    if not examples:
        print("  no bundled examples found")
        return 0
    print("  Bundled example specs (run one with: rhbt run <path>)\n")
    for path in examples:
        try:
            spec = Spec.load(path)
            print(f"  {path.relative_to(REPO_ROOT)}\n      {spec.name} - {spec.description or 'no description'}")
        except Exception as exc:  # pragma: no cover
            print(f"  {path}: unreadable ({exc})")
    print()
    return 0


# ------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rhbt",
        description="Robinhood Agentic Backtester - run a strategy, get monthly drawdowns and a tearsheet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  rhbt run examples/golden_cross.yaml\n"
            "  rhbt run --symbols SPY --entry 'rsi(close,2) < 10' --exit 'rsi(close,2) > 60'\n"
            "  rhbt run --strategy rhbt/strategies/sma_crossover.py --symbols AAPL --start 2018-01-01\n"
            "  rhbt sweep examples/golden_cross.yaml --param fast=20,50 --param slow=100,200\n"
            "  rhbt data import --symbol AAPL < robinhood_bars.json\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"rhbt {__version__}")
    subs = parser.add_subparsers(dest="command")

    run = subs.add_parser("run", help="run a backtest")
    run.add_argument("spec", nargs="?", help="path to a YAML/JSON strategy spec")
    run.add_argument("--strategy", help="Python strategy instead of a spec: file.py:ClassName, or a built-in name")
    run.add_argument("--symbols", action="append", help="comma-separated tickers (repeatable)")
    run.add_argument("--name", help="override the strategy name in the report")
    run.add_argument("--entry", help="inline entry rule expression")
    run.add_argument("--exit", help="inline exit rule expression")
    run.add_argument("--short-entry", dest="short_entry", help="inline short entry rule")
    run.add_argument("--short-exit", dest="short_exit", help="inline short exit rule")
    run.add_argument("--start", help="first date, YYYY-MM-DD")
    run.add_argument("--end", help="last date, YYYY-MM-DD")
    run.add_argument("--interval", default="day", help="bar size (default: day)")
    run.add_argument("--cash", type=float, default=10_000.0, help="starting cash (default: 10000)")
    run.add_argument("--benchmark", help="benchmark ticker, or 'none' (default: SPY)")
    run.add_argument("--slippage-bps", type=float, dest="slippage_bps", help="slippage in bps (default: 5)")
    run.add_argument("--commission-bps", type=float, dest="commission_bps", help="commission in bps (default: 0)")
    run.add_argument("--fill", choices=["next_open", "close"], help="when signalled orders fill (default: next_open)")
    run.add_argument("--allow-short", action="store_true", dest="allow_short")
    run.add_argument("--max-positions", type=int, dest="max_positions")
    run.add_argument("--stop-loss", type=float, dest="stop_loss", help="e.g. 0.08 for an 8%% stop")
    run.add_argument("--take-profit", type=float, dest="take_profit")
    run.add_argument("--trailing-stop", type=float, dest="trailing_stop")
    run.add_argument("--warmup", type=int, help="extra bars loaded before --start so indicators are warm (default: 250)")
    run.add_argument("--param", action="append", help="override a spec param: --param fast=20 (repeatable)")
    run.add_argument("--report", help="where to write the HTML tearsheet")
    run.add_argument("--json", help="write machine-readable results here ('-' for stdout)")
    run.add_argument("--no-report", action="store_true", dest="no_report")
    run.add_argument("--no-monthly", action="store_true", dest="no_monthly", help="skip the monthly table in the terminal")
    run.add_argument("--all-months", action="store_true", dest="all_months", help="print every month, not just the last 24")
    run.add_argument("--open", action="store_true", help="open the report in a browser when done")
    run.add_argument("--refresh", action="store_true", help="re-download data instead of using the cache")
    run.add_argument("--offline", action="store_true", help="use only cached data; never hit the network")
    run.set_defaults(func=cmd_run)

    sweep = subs.add_parser("sweep", help="grid-search spec parameters")
    sweep.add_argument("spec")
    sweep.add_argument("--param", action="append", default=[], help="key=v1,v2,v3 (repeatable)")
    sweep.add_argument("--sort", default="sharpe", help="column to rank by (default: sharpe)")
    sweep.add_argument("--csv", help="also write the results table here")
    sweep.add_argument("--offline", action="store_true")
    sweep.set_defaults(func=cmd_sweep)

    validate = subs.add_parser("validate", help="check a spec without running it")
    validate.add_argument("spec")
    validate.set_defaults(func=cmd_validate)

    data = subs.add_parser("data", help="manage the local price cache")
    data_subs = data.add_subparsers(dest="data_command")

    imp = data_subs.add_parser("import", help="import Robinhood MCP historicals JSON (stdin by default)")
    imp.add_argument("--symbol", help="symbol for the bars, if the payload does not name it")
    imp.add_argument("--interval", default="day")
    imp.add_argument("--file", help="read from this file instead of stdin")
    imp.set_defaults(func=cmd_data_import)

    fetch = data_subs.add_parser("fetch", help="download bars with the yfinance fallback")
    fetch.add_argument("symbols", nargs="+")
    fetch.add_argument("--start")
    fetch.add_argument("--end")
    fetch.add_argument("--interval", default="day")
    fetch.set_defaults(func=cmd_data_fetch)

    listing = data_subs.add_parser("list", help="show what is cached")
    listing.set_defaults(func=cmd_data_list)

    clear = data_subs.add_parser("clear", help="delete cached bars")
    clear.add_argument("--symbol", help="only this symbol (default: everything)")
    clear.set_defaults(func=cmd_data_clear)

    data.set_defaults(func=lambda args: (data.print_help(), 0)[1])

    subs.add_parser("indicators", help="list functions usable in rules").set_defaults(func=cmd_indicators)
    subs.add_parser("schema", help="print the spec schema as JSON (for agents)").set_defaults(func=cmd_schema)
    subs.add_parser("examples", help="list the bundled example specs").set_defaults(func=cmd_examples)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    if args.command == "data" and not getattr(args, "data_command", None):
        parser.parse_args(["data", "--help"])
        return 0
    try:
        return args.func(args)
    except (SpecError, ExpressionError, DataError) as exc:
        print(f"\nerror: {exc}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
