"""The backtest engine: an explicit bar-by-bar loop with no look-ahead.

Order of operations on each bar ``i``:

1. Fill orders queued on bar ``i-1`` at bar ``i``'s open (default ``fill: next_open``).
2. Check stop-loss / take-profit / trailing-stop against bar ``i``'s high and low.
3. Mark the portfolio to bar ``i``'s close and record equity.
4. Call ``strategy.on_bar(ctx)``, which may queue orders for bar ``i+1``.

``fill: close`` instead executes queued orders at the same bar's close. That is
optimistic - you are trading on a price you only knew at the bell - so the
default is ``next_open``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .portfolio import Costs, Portfolio
from .strategy import Context, Order, Strategy

_PERIODS = {"day": 252, "week": 52, "month": 12, "hour": 1638, "minute": 98280}


@dataclass
class RunConfig:
    """Everything about *how* the backtest runs (as opposed to what it trades)."""

    cash: float = 10_000.0
    costs: Costs = field(default_factory=Costs)
    fill: str = "next_open"          # "next_open" | "close"
    allow_short: bool = False
    allow_fractional: bool = True
    max_positions: int | None = None
    stop_loss: float | None = None       # fraction, e.g. 0.08 == -8%
    take_profit: float | None = None
    trailing_stop: float | None = None
    liquidate_at_end: bool = True
    interval: str = "day"
    risk_free_rate: float = 0.0          # annualised, for Sharpe

    @property
    def periods_per_year(self) -> int:
        return _PERIODS.get(str(self.interval).lower(), 252)


class BacktestResult:
    """Everything a run produced: curves, trades, metrics."""

    def __init__(self, *, equity: pd.Series, cash: pd.Series, exposure: pd.Series,
                 positions: pd.Series, trades: pd.DataFrame, fills: list,
                 config: RunConfig, strategy_name: str, params: dict,
                 symbols: list[str], logs: list, benchmark: pd.Series | None = None,
                 benchmark_symbol: str | None = None, meta: dict | None = None):
        self.equity = equity
        self.cash = cash
        self.exposure = exposure
        self.positions = positions
        self.trades = trades
        self.fills = fills
        self.config = config
        self.strategy_name = strategy_name
        self.params = params
        self.symbols = symbols
        self.logs = logs
        self.benchmark = benchmark
        self.benchmark_symbol = benchmark_symbol
        self.meta = meta or {}
        self._metrics: dict | None = None
        self._monthly: pd.DataFrame | None = None

    @property
    def metrics(self) -> dict:
        from .metrics import compute_metrics
        if self._metrics is None:
            self._metrics = compute_metrics(
                self.equity,
                trades=self.trades,
                periods_per_year=self.config.periods_per_year,
                risk_free_rate=self.config.risk_free_rate,
                exposure=self.exposure,
                benchmark=self.benchmark,
            )
        return self._metrics

    @property
    def monthly(self) -> pd.DataFrame:
        """Per-month return, drawdown and equity table - the headline output."""
        from .metrics import monthly_table
        if self._monthly is None:
            self._monthly = monthly_table(self.equity, benchmark=self.benchmark)
        return self._monthly

    def drawdown(self) -> pd.Series:
        from .metrics import drawdown_series
        return drawdown_series(self.equity)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "params": self.params,
            "symbols": self.symbols,
            "start": str(self.equity.index[0].date()) if len(self.equity) else None,
            "end": str(self.equity.index[-1].date()) if len(self.equity) else None,
            "initial_cash": self.config.cash,
            "final_equity": float(self.equity.iloc[-1]) if len(self.equity) else self.config.cash,
            "metrics": self.metrics,
            "monthly": [
                {"month": str(idx), **{k: (None if pd.isna(v) else float(v)) for k, v in row.items()}}
                for idx, row in self.monthly.iterrows()
            ],
            "trades": self.trades.to_dict(orient="records"),
            "meta": self.meta,
        }


class Backtest:
    """Runs one :class:`~rhbt.strategy.Strategy` over one set of price frames."""

    def __init__(self, frames: dict[str, pd.DataFrame], strategy: Strategy,
                 config: RunConfig | None = None, benchmark: pd.DataFrame | None = None,
                 benchmark_symbol: str | None = None, trade_from=None):
        if not frames:
            raise ValueError("no price data supplied")
        self.config = config or RunConfig()
        self.strategy = strategy
        self.symbols = sorted(frames)
        self.index = self._union_index(frames)
        self.frames = {sym: self._align(frame) for sym, frame in frames.items()}
        self._arrays = {
            sym: {col: frame[col].to_numpy(dtype=float) for col in ("open", "high", "low", "close", "volume")}
            for sym, frame in self.frames.items()
        }
        self.portfolio = Portfolio(
            cash=self.config.cash,
            costs=self.config.costs,
            allow_short=self.config.allow_short,
            allow_fractional=self.config.allow_fractional,
        )
        self.ctx = Context(self)
        self.risk_overrides: dict[str, dict] = {}
        self._peak_price: dict[str, float] = {}
        self._i = 0
        self._benchmark_frame = benchmark
        self._benchmark_symbol = benchmark_symbol
        # Bars before this index exist only to warm up indicators - the
        # strategy never sees them as tradable bars.
        self._start_i = 0
        if trade_from is not None and len(self.index):
            self._start_i = int(self.index.searchsorted(pd.Timestamp(trade_from)))
            self._start_i = min(max(self._start_i, 0), max(len(self.index) - 1, 0))

    # ------------------------------------------------------------------ data
    @staticmethod
    def _union_index(frames: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
        index = None
        for frame in frames.values():
            index = frame.index if index is None else index.union(frame.index)
        return pd.DatetimeIndex(index).sort_values()

    def _align(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.reindex(self.index)
        # A missing bar (holiday for one listing, say) carries the last price
        # forward so the position is still marked, but trades nothing new.
        out[["open", "high", "low", "close"]] = out[["open", "high", "low", "close"]].ffill()
        out["volume"] = out["volume"].fillna(0.0)
        return out

    def value(self, symbol: str, column: str, i: int) -> float:
        arr = self._arrays.get(symbol, {}).get(column)
        if arr is None or i < 0 or i >= len(arr):
            return float("nan")
        return float(arr[i])

    def current_prices(self, i: int | None = None, column: str = "close") -> dict[str, float]:
        i = self._i if i is None else i
        return {sym: self.value(sym, column, i) for sym in self.symbols}

    # ------------------------------------------------------------- execution
    def _resolve(self, order: Order, price: float, equity: float) -> float:
        """Turn an order into a signed share delta at ``price``."""
        if price != price or price <= 0:
            return 0.0
        current = self.portfolio.qty(order.symbol)
        kind, amount = order.kind, order.amount

        if kind == "close":
            return -current
        if kind == "target_percent":
            return (amount * equity / price) - current
        if kind == "target_value":
            return (amount / price) - current
        if kind == "target_shares":
            return amount - current
        if kind == "percent":
            return amount * equity / price
        if kind == "value":
            return amount / price
        if kind == "shares":
            return amount
        return 0.0

    def _apply_constraints(self, symbol: str, delta: float) -> float:
        current = self.portfolio.qty(symbol)
        target = current + delta
        if not self.config.allow_short and target < 0:
            target = 0.0
            delta = target - current
        if self.config.max_positions is not None and abs(current) < 1e-12 and abs(target) > 1e-12:
            open_count = sum(1 for p in self.portfolio.positions.values() if p.is_open)
            if open_count >= self.config.max_positions:
                return 0.0
        return delta

    def _execute_queue(self, orders: list[Order], i: int, column: str) -> None:
        if not orders:
            return
        prices = self.current_prices(i, column)
        equity = self.portfolio.equity(self.current_prices(i, "close"))
        date = self.index[i]
        # Sells first so their proceeds fund the buys on the same bar.
        resolved = []
        for order in orders:
            price = prices.get(order.symbol, float("nan"))
            delta = self._resolve(order, price, equity)
            if abs(delta) > 1e-9:
                resolved.append((delta, order, price))
        for delta, order, price in sorted(resolved, key=lambda item: item[0]):
            # Constraints are re-checked here, not at resolve time, so that
            # limits like max_positions see the fills already done this bar.
            delta = self._apply_constraints(order.symbol, delta)
            if abs(delta) <= 1e-9:
                continue
            self.portfolio.execute(order.symbol, delta, price, date, i, order.reason)
            if abs(self.portfolio.qty(order.symbol)) < 1e-12:
                self._peak_price.pop(order.symbol, None)
                self.risk_overrides.pop(order.symbol, None)

    def _risk_for(self, symbol: str, key: str) -> float | None:
        override = self.risk_overrides.get(symbol, {}).get(key)
        return override if override is not None else getattr(self.config, key)

    def _check_risk_exits(self, i: int) -> None:
        """Intrabar stop-loss / take-profit / trailing-stop checks."""
        date = self.index[i]
        for symbol in list(self.portfolio.positions):
            pos = self.portfolio.position(symbol)
            if not pos.is_open:
                continue
            high, low = self.value(symbol, "high", i), self.value(symbol, "low", i)
            open_ = self.value(symbol, "open", i)
            if high != high or low != low or pos.avg_price <= 0:
                continue
            long = pos.qty > 0
            stop = self._risk_for(symbol, "stop_loss")
            take = self._risk_for(symbol, "take_profit")
            trail = self._risk_for(symbol, "trailing_stop")

            peak = self._peak_price.get(symbol)
            if trail:
                peak = high if peak is None else (max(peak, high) if long else min(peak, low))
                self._peak_price[symbol] = peak

            exit_price, reason = None, ""
            if stop:
                level = pos.avg_price * (1 - stop) if long else pos.avg_price * (1 + stop)
                if (long and low <= level) or (not long and high >= level):
                    exit_price = min(open_, level) if long else max(open_, level)
                    reason = "stop_loss"
            if exit_price is None and trail and peak is not None:
                level = peak * (1 - trail) if long else peak * (1 + trail)
                if (long and low <= level) or (not long and high >= level):
                    exit_price = min(open_, level) if long else max(open_, level)
                    reason = "trailing_stop"
            if exit_price is None and take:
                level = pos.avg_price * (1 + take) if long else pos.avg_price * (1 - take)
                if (long and high >= level) or (not long and low <= level):
                    exit_price = max(open_, level) if long else min(open_, level)
                    reason = "take_profit"

            if exit_price is not None and exit_price == exit_price:
                self.portfolio.execute(symbol, -pos.qty, float(exit_price), date, i, reason)
                self._peak_price.pop(symbol, None)
                self.risk_overrides.pop(symbol, None)

    # ------------------------------------------------------------------- run
    def run(self) -> BacktestResult:
        n = len(self.index)
        start_i = self._start_i
        equity = np.empty(n, dtype=float)
        cash = np.empty(n, dtype=float)
        exposure = np.empty(n, dtype=float)
        positions = np.empty(n, dtype=float)

        fill_at_close = str(self.config.fill).lower() in ("close", "same_close", "same_bar")
        pending: list[Order] = []

        self._i = start_i
        self.strategy.on_start(self.ctx)
        pending.extend(self.ctx.orders)
        self.ctx.orders.clear()

        for i in range(start_i, n):
            self._i = i
            if pending and not fill_at_close:
                self._execute_queue(pending, i, "open")
                pending = []
            self._check_risk_exits(i)

            closes = self.current_prices(i, "close")
            for symbol in self.symbols:
                self.portfolio.update_excursions(symbol, closes.get(symbol, float("nan")))

            self.strategy.on_bar(self.ctx)
            new_orders = list(self.ctx.orders)
            self.ctx.orders.clear()

            if fill_at_close and new_orders:
                self._execute_queue(new_orders, i, "close")
                new_orders = []
            pending = new_orders

            closes = self.current_prices(i, "close")
            equity[i] = self.portfolio.equity(closes)
            cash[i] = self.portfolio.cash
            exposure[i] = self.portfolio.exposure(closes)
            positions[i] = sum(1 for p in self.portfolio.positions.values() if p.is_open)

        self._i = n - 1
        self.strategy.on_finish(self.ctx)
        if self.config.liquidate_at_end and n:
            self.portfolio.close_all(self.current_prices(n - 1, "close"), self.index[-1], n - 1)
            equity[n - 1] = self.portfolio.equity(self.current_prices(n - 1, "close"))
            cash[n - 1] = self.portfolio.cash

        window = self.index[start_i:]
        equity_series = pd.Series(equity[start_i:], index=window, name="equity")
        benchmark_series = self._build_benchmark(equity_series)

        return BacktestResult(
            equity=equity_series,
            cash=pd.Series(cash[start_i:], index=window, name="cash"),
            exposure=pd.Series(exposure[start_i:], index=window, name="exposure"),
            positions=pd.Series(positions[start_i:], index=window, name="positions"),
            trades=self.portfolio.trade_frame(),
            fills=self.portfolio.fills,
            config=self.config,
            strategy_name=self.strategy.name or type(self.strategy).__name__,
            params=dict(self.strategy.params),
            symbols=self.symbols,
            logs=list(self.ctx.logs),
            benchmark=benchmark_series,
            benchmark_symbol=self._benchmark_symbol,
            meta={
                "bars": int(len(window)),
                "warmup_bars": int(start_i),
                "fees_paid": round(self.portfolio.total_fees, 2),
                "slippage_cost": round(self.portfolio.total_slippage, 2),
                "fills": len(self.portfolio.fills),
                "fill_model": self.config.fill,
                "interval": self.config.interval,
            },
        )

    def _build_benchmark(self, equity: pd.Series) -> pd.Series | None:
        """Buy-and-hold equity for the benchmark symbol, on the same axis."""
        if self._benchmark_frame is None or self._benchmark_frame.empty:
            return None
        closes = self._benchmark_frame["close"].reindex(self.index).ffill().bfill()
        closes = closes.iloc[self._start_i:]
        if closes.isna().all() or closes.iloc[0] <= 0:
            return None
        return (closes / closes.iloc[0] * self.config.cash).rename("benchmark")
