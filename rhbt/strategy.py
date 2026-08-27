"""The strategy API: subclass :class:`Strategy` and implement ``on_bar``.

Everything a strategy needs arrives through the context object::

    from rhbt import Strategy

    class GoldenCross(Strategy):
        params = {"fast": 50, "slow": 200}

        def on_bar(self, ctx):
            for sym in ctx.symbols:
                closes = ctx.history(sym)["close"]
                if len(closes) < self.params["slow"]:
                    continue
                fast = closes.rolling(self.params["fast"]).mean().iloc[-1]
                slow = closes.rolling(self.params["slow"]).mean().iloc[-1]
                if fast > slow and not ctx.is_long(sym):
                    ctx.order_target_percent(sym, 1.0 / len(ctx.symbols))
                elif fast < slow and ctx.is_long(sym):
                    ctx.close(sym)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class Order:
    """A queued order. Sizing is resolved at fill time, not at queue time."""

    symbol: str
    kind: str                     # "target_percent" | "target_value" | "shares" | "close"
    amount: float = 0.0
    reason: str = ""
    limit: float | None = None


class Context:
    """Read-only market state plus the order-entry API, handed to ``on_bar``."""

    def __init__(self, engine):
        self._engine = engine
        self.orders: list[Order] = []
        self.logs: list[tuple[Any, str]] = []
        self.state: dict[str, Any] = {}

    # ------------------------------------------------------------------ time
    @property
    def i(self) -> int:
        """Index of the current bar (0-based)."""
        return self._engine._i

    @property
    def date(self) -> pd.Timestamp:
        """Timestamp of the current bar."""
        return self._engine.index[self._engine._i]

    @property
    def symbols(self) -> list[str]:
        return self._engine.symbols

    @property
    def params(self) -> dict:
        return self._engine.strategy.params

    # ----------------------------------------------------------------- price
    def _field(self, symbol: str, column: str) -> float:
        return self._engine.value(symbol, column, self._engine._i)

    def price(self, symbol: str) -> float:
        """Close of the current bar."""
        return self._field(symbol, "close")

    def open(self, symbol: str) -> float:
        return self._field(symbol, "open")

    def high(self, symbol: str) -> float:
        return self._field(symbol, "high")

    def low(self, symbol: str) -> float:
        return self._field(symbol, "low")

    def close_price(self, symbol: str) -> float:
        return self._field(symbol, "close")

    def volume(self, symbol: str) -> float:
        return self._field(symbol, "volume")

    def history(self, symbol: str, bars: int | None = None) -> pd.DataFrame:
        """Price history up to *and including* the current bar. Never peeks ahead."""
        frame = self._engine.frames[symbol].iloc[: self._engine._i + 1]
        return frame if bars is None else frame.iloc[-int(bars):]

    def has_data(self, symbol: str) -> bool:
        price = self.price(symbol)
        return price == price and price > 0

    # ------------------------------------------------------------- portfolio
    @property
    def cash(self) -> float:
        return self._engine.portfolio.cash

    @property
    def equity(self) -> float:
        return self._engine.portfolio.equity(self._engine.current_prices())

    @property
    def initial_cash(self) -> float:
        return self._engine.portfolio.initial_cash

    def position(self, symbol: str):
        return self._engine.portfolio.position(symbol)

    def qty(self, symbol: str) -> float:
        return self._engine.portfolio.qty(symbol)

    def is_long(self, symbol: str) -> bool:
        return self.qty(symbol) > 0

    def is_short(self, symbol: str) -> bool:
        return self.qty(symbol) < 0

    def is_flat(self, symbol: str) -> bool:
        return abs(self.qty(symbol)) < 1e-12

    def open_positions(self) -> list[str]:
        return [s for s, p in self._engine.portfolio.positions.items() if p.is_open]

    def weight(self, symbol: str) -> float:
        equity = self.equity
        if equity <= 0:
            return 0.0
        price = self.price(symbol)
        if price != price:
            return 0.0
        return self.qty(symbol) * price / equity

    def entry_price(self, symbol: str) -> float | None:
        pos = self.position(symbol)
        return pos.avg_price if pos.is_open else None

    def bars_held(self, symbol: str) -> int:
        entry = self._engine.portfolio._entry_bar.get(symbol)
        return 0 if entry is None else self._engine._i - entry

    # ---------------------------------------------------------------- orders
    def order_target_percent(self, symbol: str, percent: float, reason: str = "signal") -> None:
        """Rebalance ``symbol`` to ``percent`` of equity (1.0 == 100%, -0.5 == short)."""
        self.orders.append(Order(symbol, "target_percent", float(percent), reason))

    def order_target_value(self, symbol: str, value: float, reason: str = "signal") -> None:
        """Rebalance ``symbol`` to a dollar exposure."""
        self.orders.append(Order(symbol, "target_value", float(value), reason))

    def order_target_shares(self, symbol: str, shares: float, reason: str = "signal") -> None:
        """Rebalance ``symbol`` to an absolute share count."""
        self.orders.append(Order(symbol, "target_shares", float(shares), reason))

    def buy(self, symbol: str, percent: float | None = None, value: float | None = None,
            shares: float | None = None, reason: str = "buy") -> None:
        """Add to a position. Defaults to spending all remaining cash."""
        if shares is not None:
            self.orders.append(Order(symbol, "shares", abs(float(shares)), reason))
        elif value is not None:
            self.orders.append(Order(symbol, "value", abs(float(value)), reason))
        else:
            self.orders.append(Order(symbol, "percent", abs(float(percent if percent is not None else 1.0)), reason))

    def sell(self, symbol: str, percent: float | None = None, value: float | None = None,
             shares: float | None = None, reason: str = "sell") -> None:
        """Reduce (or short) a position."""
        if shares is not None:
            self.orders.append(Order(symbol, "shares", -abs(float(shares)), reason))
        elif value is not None:
            self.orders.append(Order(symbol, "value", -abs(float(value)), reason))
        else:
            self.orders.append(Order(symbol, "percent", -abs(float(percent if percent is not None else 1.0)), reason))

    def close(self, symbol: str, reason: str = "exit") -> None:
        """Flatten the position in ``symbol``."""
        self.orders.append(Order(symbol, "close", 0.0, reason))

    def close_all(self, reason: str = "exit") -> None:
        for symbol in self.open_positions():
            self.close(symbol, reason)

    def cancel_orders(self) -> None:
        self.orders.clear()

    # ------------------------------------------------------------------ risk
    def set_stop_loss(self, symbol: str, percent: float) -> None:
        """Per-position stop, as a fraction below entry (0.08 == 8%)."""
        self._engine.risk_overrides.setdefault(symbol, {})["stop_loss"] = float(percent)

    def set_take_profit(self, symbol: str, percent: float) -> None:
        self._engine.risk_overrides.setdefault(symbol, {})["take_profit"] = float(percent)

    def set_trailing_stop(self, symbol: str, percent: float) -> None:
        self._engine.risk_overrides.setdefault(symbol, {})["trailing_stop"] = float(percent)

    # ------------------------------------------------------------------- log
    def log(self, message: str) -> None:
        """Record a dated note; notes show up in the HTML report."""
        self.logs.append((self.date, str(message)))


class Strategy:
    """Base class for hand-written strategies."""

    #: Human-readable name shown in the report.
    name: str | None = None
    #: Default parameters; override per run with ``--param key=value``.
    params: dict[str, Any] = {}
    #: Optional description shown in the report header.
    description: str = ""

    def __init__(self, **overrides):
        merged = dict(type(self).params or {})
        merged.update({k: v for k, v in overrides.items() if v is not None})
        self.params = merged
        self.name = type(self).name or type(self).__name__

    def on_start(self, ctx: Context) -> None:
        """Called once before the first bar."""

    def on_bar(self, ctx: Context) -> None:
        """Called once per bar, after prices for that bar are known."""
        raise NotImplementedError("a strategy must implement on_bar()")

    def on_finish(self, ctx: Context) -> None:
        """Called once after the last bar, before final liquidation."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.name} {self.params}>"
