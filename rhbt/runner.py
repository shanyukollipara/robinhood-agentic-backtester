"""Glue: load data, build the strategy, run the engine."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import pandas as pd

from .data import DataError, load, load_many
from .engine import Backtest, BacktestResult, RunConfig
from .spec import Spec, SpecError, SpecStrategy
from .strategy import Strategy


def load_strategy_class(target: str) -> type[Strategy]:
    """Resolve ``path/to/file.py:ClassName``, ``path/to/file.py`` or a built-in name."""
    from .strategies import BUILTIN

    name = None
    if ":" in target and not target.endswith(".py"):
        path_part, _, name = target.partition(":")
    else:
        path_part, name = target, None
    if "::" in target:
        path_part, _, name = target.partition("::")

    key = path_part.strip().lower().replace("-", "_")
    if key in BUILTIN and not Path(path_part).exists():
        return BUILTIN[key]

    path = Path(path_part).expanduser()
    if not path.exists():
        raise SpecError(
            f"strategy {target!r} not found. Pass a Python file (mine.py:MyStrategy) "
            f"or one of the built-ins: {', '.join(sorted(BUILTIN))}"
        )

    spec = importlib.util.spec_from_file_location(f"rhbt_user_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise SpecError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    if name:
        cls = getattr(module, name, None)
        if cls is None:
            raise SpecError(f"{path} has no class named {name!r}")
    else:
        candidates = [
            obj for _, obj in inspect.getmembers(module, inspect.isclass)
            if issubclass(obj, Strategy) and obj is not Strategy and obj.__module__ == spec.name
        ]
        if not candidates:
            raise SpecError(f"{path} defines no Strategy subclass")
        if len(candidates) > 1:
            names = ", ".join(c.__name__ for c in candidates)
            raise SpecError(f"{path} defines several strategies ({names}); pick one with {path}:ClassName")
        cls = candidates[0]

    if not (isinstance(cls, type) and issubclass(cls, Strategy)):
        raise SpecError(f"{target} is not a rhbt Strategy subclass")
    return cls


def warmup_start(start, warmup_bars: int, interval: str = "day"):
    """Back the load start up by ``warmup_bars`` so indicators are warm on day one."""
    if start is None or not warmup_bars:
        return start
    per_bar = {"day": 1.45, "week": 7.2, "month": 31.0}.get(str(interval).lower(), 1.45)
    return pd.Timestamp(start) - pd.Timedelta(days=int(warmup_bars * per_bar) + 7)


def _load_frames(symbols, start, end, interval, refresh, offline):
    return load_many(symbols, start=start, end=end, interval=interval,
                     refresh=refresh, offline=offline)


def _load_benchmark(symbol, start, end, interval, refresh, offline):
    if not symbol:
        return None, None
    try:
        return load(symbol, start=start, end=end, interval=interval,
                    refresh=refresh, offline=offline), symbol.upper()
    except DataError as exc:
        print(f"[rhbt] warning: benchmark {symbol} unavailable ({exc.__class__.__name__}); continuing without it")
        return None, None


def run_backtest(strategy: Strategy, symbols, start=None, end=None, interval: str = "day",
                 config: RunConfig | None = None, benchmark: str | None = "SPY",
                 refresh: bool = False, offline: bool = False,
                 warmup: int = 250) -> BacktestResult:
    """Run a strategy object over freshly loaded data."""
    config = config or RunConfig(interval=interval)
    load_start = warmup_start(start, warmup, interval)
    frames = _load_frames(symbols, load_start, end, interval, refresh, offline)
    bench_frame, bench_symbol = _load_benchmark(benchmark, load_start, end, interval, refresh, offline)
    return Backtest(frames, strategy, config, bench_frame, bench_symbol, trade_from=start).run()


def run_spec(spec: Spec, refresh: bool = False, offline: bool = False,
             param_overrides: dict | None = None) -> BacktestResult:
    """Run a parsed :class:`~rhbt.spec.Spec`."""
    strategy = SpecStrategy(spec, **(param_overrides or {}))
    load_start = warmup_start(spec.start, spec.warmup, spec.interval)
    frames = _load_frames(spec.symbols, load_start, spec.end, spec.interval, refresh, offline)
    bench_frame, bench_symbol = _load_benchmark(
        spec.benchmark, load_start, spec.end, spec.interval, refresh, offline
    )
    return Backtest(frames, strategy, spec.run_config(), bench_frame, bench_symbol,
                    trade_from=spec.start).run()


def run_spec_file(path, refresh: bool = False, offline: bool = False,
                  param_overrides: dict | None = None) -> BacktestResult:
    """Load a YAML/JSON spec from disk and run it."""
    return run_spec(Spec.load(path), refresh=refresh, offline=offline,
                    param_overrides=param_overrides)
