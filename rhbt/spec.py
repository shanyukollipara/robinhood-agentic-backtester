"""Declarative strategy specs - the format AI agents should write.

A spec is a YAML (or JSON) file describing what to trade, when to enter and
exit, how big to size, and what it costs. Rules are ordinary expressions over
price columns and the indicator library, so an agent can translate a plain
English strategy into a spec without writing any Python::

    name: Golden Cross
    symbols: [SPY]
    start: 2015-01-01
    cash: 10000
    params: { fast: 50, slow: 200 }
    rules:
      entry: "crossover(sma(close, fast), sma(close, slow))"
      exit:  "crossunder(sma(close, fast), sma(close, slow))"
    risk:
      stop_loss: 0.10

Unknown keys are rejected with a suggestion, so a mistyped spec fails loudly
instead of silently ignoring half the strategy.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import expr as expr_mod
from .engine import RunConfig
from .indicators import atr as atr_ind
from .portfolio import Costs
from .strategy import Strategy

TOP_LEVEL = {
    "name", "description", "symbols", "symbol", "universe", "start", "end",
    "interval", "cash", "initial_cash", "benchmark", "fees", "costs",
    "execution", "risk", "sizing", "rules", "params", "rebalance", "notes",
    "warmup",
}
FEE_KEYS = {"slippage_bps", "commission_bps", "commission_per_share", "commission_flat", "sell_fee_bps"}
EXEC_KEYS = {"fill", "allow_short", "allow_fractional", "max_positions", "liquidate_at_end", "risk_free_rate"}
RISK_KEYS = {"stop_loss", "take_profit", "trailing_stop", "max_hold_bars", "min_hold_bars"}
SIZING_KEYS = {"mode", "value", "risk_per_trade", "atr_window", "atr_mult", "target_vol", "vol_window", "max_weight"}
RULE_KEYS = {"entry", "exit", "short_entry", "short_exit", "filter"}
SIZING_MODES = {"equal_weight", "full_equity", "fixed_percent", "fixed_value", "fixed_shares",
                "atr_risk", "volatility_target"}
REBALANCE = {"every_bar", "daily", "weekly", "monthly", "quarterly"}


class SpecError(ValueError):
    """Raised for a malformed spec, with a message aimed at whoever wrote it."""


def _check_keys(mapping: dict, allowed: set[str], where: str) -> None:
    for key in mapping:
        if key not in allowed:
            close = difflib.get_close_matches(str(key), sorted(allowed), n=3, cutoff=0.6)
            hint = f" Did you mean {close[0]!r}?" if close else f" Allowed: {sorted(allowed)}"
            raise SpecError(f"unknown key {key!r} in {where}.{hint}")


def _as_dict(value, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SpecError(f"{where} must be a mapping, got {type(value).__name__}")
    return value


@dataclass
class Spec:
    """A parsed, validated strategy specification."""

    name: str = "Unnamed strategy"
    description: str = ""
    symbols: list[str] = field(default_factory=list)
    start: str | None = None
    end: str | None = None
    interval: str = "day"
    cash: float = 10_000.0
    benchmark: str | None = "SPY"
    fees: dict = field(default_factory=dict)
    execution: dict = field(default_factory=dict)
    risk: dict = field(default_factory=dict)
    sizing: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    rebalance: str = "every_bar"
    #: Extra bars loaded before ``start`` so indicators are warm on day one.
    warmup: int = 250
    source_path: str | None = None

    # ---------------------------------------------------------------- parsing
    @classmethod
    def from_dict(cls, raw: dict, source_path: str | None = None) -> "Spec":
        if not isinstance(raw, dict):
            raise SpecError("a strategy spec must be a YAML/JSON mapping at the top level")
        _check_keys(raw, TOP_LEVEL, "the spec")

        symbols = raw.get("symbols") or raw.get("universe") or raw.get("symbol")
        if symbols is None:
            raise SpecError("spec is missing 'symbols' (e.g. symbols: [AAPL, MSFT])")
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.replace(",", " ").split() if s.strip()]
        symbols = [str(s).strip().upper() for s in symbols if str(s).strip()]
        if not symbols:
            raise SpecError("'symbols' is empty")

        rules = _as_dict(raw.get("rules"), "'rules'")
        _check_keys(rules, RULE_KEYS, "'rules'")
        if not rules.get("entry") and not rules.get("short_entry"):
            raise SpecError("spec needs at least rules.entry (or rules.short_entry for a short strategy)")

        fees = _as_dict(raw.get("fees") or raw.get("costs"), "'fees'")
        _check_keys(fees, FEE_KEYS, "'fees'")
        execution = _as_dict(raw.get("execution"), "'execution'")
        _check_keys(execution, EXEC_KEYS, "'execution'")
        risk = _as_dict(raw.get("risk"), "'risk'")
        _check_keys(risk, RISK_KEYS, "'risk'")
        sizing = _as_dict(raw.get("sizing"), "'sizing'")
        _check_keys(sizing, SIZING_KEYS, "'sizing'")
        params = _as_dict(raw.get("params"), "'params'")

        mode = str(sizing.get("mode", "equal_weight")).lower()
        if mode not in SIZING_MODES:
            raise SpecError(f"sizing.mode must be one of {sorted(SIZING_MODES)}, got {mode!r}")
        rebalance = str(raw.get("rebalance", "every_bar")).lower()
        if rebalance not in REBALANCE:
            raise SpecError(f"rebalance must be one of {sorted(REBALANCE)}, got {rebalance!r}")
        fill = str(execution.get("fill", "next_open")).lower()
        if fill not in ("next_open", "close", "same_bar", "same_close"):
            raise SpecError("execution.fill must be 'next_open' or 'close'")

        benchmark = raw.get("benchmark", "SPY")
        if benchmark in (False, "none", "None", ""):
            benchmark = None

        return cls(
            name=str(raw.get("name") or "Unnamed strategy"),
            description=str(raw.get("description") or raw.get("notes") or ""),
            symbols=symbols,
            start=str(raw["start"]) if raw.get("start") else None,
            end=str(raw["end"]) if raw.get("end") else None,
            interval=str(raw.get("interval", "day")),
            cash=float(raw.get("cash", raw.get("initial_cash", 10_000.0))),
            benchmark=str(benchmark).upper() if benchmark else None,
            fees=fees, execution=execution, risk=risk, sizing=sizing,
            rules=rules, params=params, rebalance=rebalance,
            warmup=max(int(raw.get("warmup") if raw.get("warmup") is not None else 250), 0),
            source_path=source_path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "Spec":
        path = Path(path)
        if not path.exists():
            raise SpecError(f"spec file not found: {path}")
        text = path.read_text()
        if path.suffix.lower() == ".json":
            raw = json.loads(text)
        else:
            import yaml
            raw = yaml.safe_load(text)
        return cls.from_dict(raw, source_path=str(path))

    # ------------------------------------------------------------ conversion
    def run_config(self) -> RunConfig:
        return RunConfig(
            cash=self.cash,
            costs=Costs(
                slippage_bps=float(self.fees.get("slippage_bps", 5.0)),
                commission_bps=float(self.fees.get("commission_bps", 0.0)),
                commission_per_share=float(self.fees.get("commission_per_share", 0.0)),
                commission_flat=float(self.fees.get("commission_flat", 0.0)),
                sell_fee_bps=float(self.fees.get("sell_fee_bps", 0.0)),
            ),
            fill=str(self.execution.get("fill", "next_open")).lower(),
            allow_short=bool(self.execution.get("allow_short", bool(self.rules.get("short_entry")))),
            allow_fractional=bool(self.execution.get("allow_fractional", True)),
            max_positions=self.execution.get("max_positions"),
            stop_loss=self.risk.get("stop_loss"),
            take_profit=self.risk.get("take_profit"),
            trailing_stop=self.risk.get("trailing_stop"),
            liquidate_at_end=bool(self.execution.get("liquidate_at_end", True)),
            interval=self.interval,
            risk_free_rate=float(self.execution.get("risk_free_rate", 0.0)),
        )

    def strategy(self) -> "SpecStrategy":
        return SpecStrategy(self)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description, "symbols": self.symbols,
            "start": self.start, "end": self.end, "interval": self.interval,
            "cash": self.cash, "benchmark": self.benchmark, "fees": self.fees,
            "execution": self.execution, "risk": self.risk, "sizing": self.sizing,
            "rules": self.rules, "params": self.params, "rebalance": self.rebalance,
            "warmup": self.warmup,
        }


_REBALANCE_FREQ = {"weekly": "W", "monthly": "M", "quarterly": "Q"}


class SpecStrategy(Strategy):
    """Executes a :class:`Spec`. Rules are evaluated once, vectorised, at start."""

    def __init__(self, spec: Spec, **overrides):
        self.spec = spec
        super().__init__(**{**spec.params, **overrides})
        self.name = spec.name
        self.description = spec.description
        self._signals: dict[str, dict[str, pd.Series]] = {}
        self._size: dict[str, pd.Series] = {}
        self._act: np.ndarray | None = None

    # -------------------------------------------------------------- lifecycle
    def on_start(self, ctx) -> None:
        engine = ctx._engine
        rules = self.spec.rules
        for symbol in ctx.symbols:
            frame = engine.frames[symbol]
            signals = {}
            for key in ("entry", "exit", "short_entry", "short_exit", "filter"):
                if rules.get(key):
                    signals[key] = expr_mod.evaluate_bool(rules[key], frame, self.params)
            if "filter" in signals:
                for key in ("entry", "short_entry"):
                    if key in signals:
                        signals[key] = signals[key] & signals["filter"]
            self._signals[symbol] = signals
            self._size[symbol] = self._size_series(frame, len(ctx.symbols))
        self._act = self._rebalance_mask(engine.index)

    def _rebalance_mask(self, index: pd.DatetimeIndex) -> np.ndarray:
        freq = _REBALANCE_FREQ.get(self.spec.rebalance)
        if freq is None:  # every_bar / daily
            return np.ones(len(index), dtype=bool)
        periods = index.to_period(freq)
        mask = np.zeros(len(index), dtype=bool)
        mask[0] = True
        mask[1:] = periods[1:] != periods[:-1]
        return mask

    def _size_series(self, frame: pd.DataFrame, n_symbols: int) -> pd.Series:
        """Target weight per bar for one symbol, given the sizing block."""
        sizing = self.spec.sizing
        mode = str(sizing.get("mode", "equal_weight")).lower()
        max_weight = float(sizing.get("max_weight", 1.0))
        slots = int(self.spec.execution.get("max_positions") or n_symbols) or 1

        if mode == "equal_weight":
            weights = pd.Series(1.0 / max(slots, 1), index=frame.index)
        elif mode == "full_equity":
            weights = pd.Series(1.0, index=frame.index)
        elif mode == "fixed_percent":
            weights = pd.Series(float(sizing.get("value", 1.0 / max(slots, 1))), index=frame.index)
        elif mode == "fixed_value":
            weights = pd.Series(float(sizing.get("value", 1000.0)), index=frame.index)  # dollars
        elif mode == "fixed_shares":
            weights = pd.Series(float(sizing.get("value", 1.0)), index=frame.index)     # shares
        elif mode == "atr_risk":
            window = int(sizing.get("atr_window", 14))
            mult = float(sizing.get("atr_mult", 2.0))
            risk = float(sizing.get("risk_per_trade", 0.01))
            atr_values = atr_ind(frame["high"], frame["low"], frame["close"], window)
            stop_distance = (mult * atr_values / frame["close"]).replace(0.0, np.nan)
            weights = (risk / stop_distance).clip(upper=max_weight).fillna(0.0)
        elif mode == "volatility_target":
            window = int(sizing.get("vol_window", 20))
            target = float(sizing.get("target_vol", 0.15))
            realised = frame["close"].pct_change().rolling(window).std() * np.sqrt(252)
            weights = (target / realised.replace(0.0, np.nan)).clip(upper=max_weight).fillna(0.0)
        else:  # pragma: no cover - guarded in Spec.from_dict
            weights = pd.Series(1.0 / max(slots, 1), index=frame.index)

        if mode in ("equal_weight", "full_equity", "fixed_percent", "atr_risk", "volatility_target"):
            weights = weights.clip(upper=max_weight)
        return weights

    # --------------------------------------------------------------- per bar
    def on_bar(self, ctx) -> None:
        i = ctx.i
        act = bool(self._act[i]) if self._act is not None else True
        mode = str(self.spec.sizing.get("mode", "equal_weight")).lower()
        max_hold = self.spec.risk.get("max_hold_bars")
        min_hold = int(self.spec.risk.get("min_hold_bars") or 0)

        for symbol in ctx.symbols:
            signals = self._signals.get(symbol, {})
            if not ctx.has_data(symbol):
                continue
            qty = ctx.qty(symbol)
            held = ctx.bars_held(symbol)

            if qty != 0 and max_hold and held >= int(max_hold):
                ctx.close(symbol, reason="max_hold")
                continue
            if qty != 0 and held < min_hold:
                continue

            def fires(key: str) -> bool:
                series = signals.get(key)
                return bool(series.iat[i]) if series is not None else False

            if qty > 0 and fires("exit"):
                # A bar that exits a long and signals a short reverses in one
                # order - closing first would let the short signal expire.
                if act and fires("short_entry"):
                    self._enter(ctx, symbol, i, mode, direction=-1, reason="reverse_short")
                else:
                    ctx.close(symbol, reason="exit_rule")
                continue
            if qty < 0 and fires("short_exit"):
                if act and fires("entry"):
                    self._enter(ctx, symbol, i, mode, direction=1, reason="reverse_long")
                else:
                    ctx.close(symbol, reason="short_exit_rule")
                continue

            if not act:
                continue

            if qty == 0 and fires("entry"):
                self._enter(ctx, symbol, i, mode, direction=1)
            elif qty == 0 and fires("short_entry"):
                self._enter(ctx, symbol, i, mode, direction=-1)
            elif qty != 0 and mode in ("atr_risk", "volatility_target") and act:
                self._enter(ctx, symbol, i, mode, direction=1 if qty > 0 else -1, reason="resize")

    def _enter(self, ctx, symbol: str, i: int, mode: str, direction: int, reason: str = "entry") -> None:
        size = float(self._size[symbol].iat[i])
        if size != size or size <= 0:
            return
        if mode == "fixed_value":
            ctx.order_target_value(symbol, direction * size, reason=reason)
        elif mode == "fixed_shares":
            ctx.order_target_shares(symbol, direction * size, reason=reason)
        else:
            ctx.order_target_percent(symbol, direction * size, reason=reason)
