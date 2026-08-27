"""Cash, positions, fills and the round-trip trade log."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class Costs:
    """Transaction cost model. Robinhood equities are commission-free, so the
    defaults only charge slippage - but the knobs are here for realism."""

    slippage_bps: float = 5.0
    commission_bps: float = 0.0
    commission_per_share: float = 0.0
    commission_flat: float = 0.0
    #: SEC + FINRA style fee on sells, in basis points of notional.
    sell_fee_bps: float = 0.0

    def fill_price(self, price: float, qty: float) -> float:
        """Slippage always works against you."""
        drift = self.slippage_bps / 10_000.0
        return price * (1.0 + drift) if qty > 0 else price * (1.0 - drift)

    def commission(self, price: float, qty: float) -> float:
        notional = abs(qty) * price
        fee = (
            notional * self.commission_bps / 10_000.0
            + abs(qty) * self.commission_per_share
            + (self.commission_flat if qty != 0 else 0.0)
        )
        if qty < 0:
            fee += notional * self.sell_fee_bps / 10_000.0
        return fee


@dataclass
class Position:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0

    @property
    def is_open(self) -> bool:
        return abs(self.qty) > 1e-12

    @property
    def side(self) -> str:
        return "long" if self.qty > 0 else ("short" if self.qty < 0 else "flat")

    def market_value(self, price: float) -> float:
        return self.qty * price

    def unrealized(self, price: float) -> float:
        return (price - self.avg_price) * self.qty


@dataclass
class Fill:
    date: pd.Timestamp
    symbol: str
    qty: float
    price: float
    commission: float
    reason: str = ""

    @property
    def notional(self) -> float:
        return self.qty * self.price


@dataclass
class Trade:
    """A completed round trip: from flat, to a position, back to flat."""

    symbol: str
    side: str
    entry_date: pd.Timestamp
    entry_price: float
    qty: float
    exit_date: pd.Timestamp | None = None
    exit_price: float = 0.0
    pnl: float = 0.0
    fees: float = 0.0
    return_pct: float = 0.0
    bars_held: int = 0
    exit_reason: str = ""
    mae_pct: float = 0.0   # worst adverse excursion while open
    mfe_pct: float = 0.0   # best favourable excursion while open
    _cost_basis: float = field(default=0.0, repr=False)
    _peak_qty: float = field(default=0.0, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_date": None if self.entry_date is None else str(pd.Timestamp(self.entry_date).date()),
            "entry_price": round(self.entry_price, 4),
            "exit_date": None if self.exit_date is None else str(pd.Timestamp(self.exit_date).date()),
            "exit_price": round(self.exit_price, 4),
            "qty": round(self.qty, 6),
            "pnl": round(self.pnl, 2),
            "fees": round(self.fees, 2),
            "return_pct": round(self.return_pct * 100, 3),
            "bars_held": self.bars_held,
            "mae_pct": round(self.mae_pct * 100, 3),
            "mfe_pct": round(self.mfe_pct * 100, 3),
            "exit_reason": self.exit_reason,
        }


class Portfolio:
    """Tracks cash, open positions, fills and closed trades."""

    def __init__(self, cash: float = 10_000.0, costs: Costs | None = None,
                 allow_short: bool = False, allow_fractional: bool = True):
        self.initial_cash = float(cash)
        self.cash = float(cash)
        self.costs = costs or Costs()
        self.allow_short = allow_short
        self.allow_fractional = allow_fractional
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []
        self.trades: list[Trade] = []
        self.total_fees = 0.0
        self.total_slippage = 0.0
        self._open: dict[str, Trade] = {}
        self._entry_bar: dict[str, int] = {}

    # ------------------------------------------------------------------ state
    def position(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position(symbol))

    def qty(self, symbol: str) -> float:
        return self.position(symbol).qty

    def market_value(self, prices: dict[str, float]) -> float:
        total = 0.0
        for symbol, pos in self.positions.items():
            price = prices.get(symbol)
            if price is not None and pos.is_open and price == price:
                total += pos.market_value(price)
        return total

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + self.market_value(prices)

    def exposure(self, prices: dict[str, float]) -> float:
        equity = self.equity(prices)
        if equity <= 0:
            return 0.0
        gross = sum(
            abs(pos.market_value(prices[pos.symbol]))
            for pos in self.positions.values()
            if pos.is_open and prices.get(pos.symbol) == prices.get(pos.symbol) and pos.symbol in prices
        )
        return gross / equity

    # ------------------------------------------------------------- execution
    def execute(self, symbol: str, qty: float, price: float, date, bar_index: int,
                reason: str = "") -> Fill | None:
        """Buy (qty > 0) or sell (qty < 0) at ``price`` plus costs. Returns the fill."""
        if qty == 0 or price != price or price <= 0:
            return None
        if not self.allow_fractional:
            qty = float(int(qty))
            if qty == 0:
                return None

        fill_price = self.costs.fill_price(price, qty)
        commission = self.costs.commission(fill_price, qty)
        pos = self.position(symbol)

        # Affordability check on buys (cash may not go negative without margin).
        if qty > 0:
            cost = qty * fill_price + commission
            if cost > self.cash + 1e-9:
                affordable = max(0.0, (self.cash - commission) / fill_price)
                if not self.allow_fractional:
                    affordable = float(int(affordable))
                if affordable <= 0:
                    return None
                qty = affordable
                commission = self.costs.commission(fill_price, qty)

        prev_qty = pos.qty
        new_qty = prev_qty + qty

        # Realised P&L on the portion that reduces or closes the position.
        realised = 0.0
        if prev_qty != 0 and (prev_qty > 0) != (qty > 0):
            closing = min(abs(qty), abs(prev_qty))
            direction = 1.0 if prev_qty > 0 else -1.0
            realised = (fill_price - pos.avg_price) * closing * direction

        if prev_qty == 0 or (prev_qty > 0) == (qty > 0):
            total = prev_qty + qty
            pos.avg_price = ((pos.avg_price * prev_qty) + (fill_price * qty)) / total if total != 0 else 0.0
        elif abs(new_qty) < 1e-12:
            new_qty = 0.0
        elif (new_qty > 0) != (prev_qty > 0):
            pos.avg_price = fill_price  # flipped side

        self.cash -= qty * fill_price + commission
        self.total_fees += commission
        self.total_slippage += abs(fill_price - price) * abs(qty)
        pos.qty = 0.0 if abs(new_qty) < 1e-12 else new_qty

        fill = Fill(pd.Timestamp(date), symbol, qty, fill_price, commission, reason)
        self.fills.append(fill)
        self._record(symbol, prev_qty, qty, fill_price, commission, realised, date, bar_index, reason)
        return fill

    def _start_trade(self, symbol: str, qty: float, price: float, commission: float,
                     date, bar_index: int) -> None:
        trade = Trade(
            symbol=symbol,
            side="long" if qty > 0 else "short",
            entry_date=pd.Timestamp(date),
            entry_price=price,
            qty=abs(qty),
        )
        trade._cost_basis = abs(qty) * price
        trade._peak_qty = abs(qty)
        trade.fees += commission
        self._open[symbol] = trade
        self._entry_bar[symbol] = bar_index

    def _finish_trade(self, symbol: str, trade: Trade, price: float, date,
                      bar_index: int, reason: str) -> None:
        trade.exit_date = pd.Timestamp(date)
        trade.exit_price = price
        trade.qty = trade._peak_qty
        basis = trade._cost_basis or 1.0
        trade.pnl -= trade.fees
        trade.return_pct = trade.pnl / basis
        trade.bars_held = max(0, bar_index - self._entry_bar.get(symbol, bar_index))
        trade.exit_reason = reason
        self.trades.append(trade)
        self._open.pop(symbol, None)
        self._entry_bar.pop(symbol, None)

    def _record(self, symbol, prev_qty, qty, price, commission, realised,
                date, bar_index, reason) -> None:
        """Maintain the round-trip trade log."""
        trade = self._open.get(symbol)
        pos = self.position(symbol)

        if trade is None:
            if qty != 0:
                self._start_trade(symbol, qty, price, commission, date, bar_index)
            return

        trade.fees += commission
        trade.pnl += realised

        if (trade.side == "long") == (qty > 0):        # scaling into the same side
            trade.qty += abs(qty)
            trade._cost_basis += abs(qty) * price
            trade._peak_qty = max(trade._peak_qty, trade.qty)
            trade.entry_price = trade._cost_basis / trade.qty if trade.qty else price
            return

        flipped = abs(pos.qty) > 1e-12 and prev_qty != 0 and (pos.qty > 0) != (prev_qty > 0)
        if abs(pos.qty) < 1e-12 or flipped:
            self._finish_trade(symbol, trade, price, date, bar_index, reason)
            if flipped:                                 # the reversal opens a new trade
                self._start_trade(symbol, pos.qty, price, 0.0, date, bar_index)
        else:                                           # partial exit, still open
            trade.qty = abs(pos.qty)

    def update_excursions(self, symbol: str, price: float) -> None:
        """Track MAE/MFE for the currently open trade on ``symbol``."""
        trade = self._open.get(symbol)
        if trade is None or price != price or trade.entry_price <= 0:
            return
        move = (price - trade.entry_price) / trade.entry_price
        if trade.side == "short":
            move = -move
        trade.mfe_pct = max(trade.mfe_pct, move)
        trade.mae_pct = min(trade.mae_pct, move)

    def close_all(self, prices: dict[str, float], date, bar_index: int,
                  reason: str = "end_of_backtest") -> None:
        for symbol in list(self.positions):
            pos = self.positions[symbol]
            price = prices.get(symbol)
            if pos.is_open and price is not None and price == price:
                self.execute(symbol, -pos.qty, price, date, bar_index, reason)

    def trade_frame(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(columns=[
                "symbol", "side", "entry_date", "entry_price", "exit_date", "exit_price",
                "qty", "pnl", "fees", "return_pct", "bars_held", "mae_pct", "mfe_pct",
                "exit_reason",
            ])
        return pd.DataFrame([t.as_dict() for t in self.trades])
