import numpy as np
import pandas as pd
import pytest

from rhbt.engine import Backtest, RunConfig
from rhbt.portfolio import Costs
from rhbt.strategy import Strategy
from rhbt.strategies import BuyAndHold
from tests.conftest import make_frame

NO_COST = RunConfig(cash=10_000, costs=Costs(slippage_bps=0))


def test_buy_and_hold_tracks_the_underlying(ramp):
    result = Backtest({"X": ramp}, BuyAndHold(), NO_COST).run()
    price_return = ramp["close"].iloc[-1] / ramp["open"].iloc[1] - 1
    # Bought at bar 1's open (signalled on bar 0), liquidated at the last close.
    assert result.metrics["total_return"] == pytest.approx(price_return, rel=1e-6)


def test_orders_cannot_use_the_bar_they_were_signalled_on(ramp):
    class PeekAtTheClose(Strategy):
        def on_bar(self, ctx):
            if ctx.i == 0:
                ctx.buy("X", percent=1.0)

    result = Backtest({"X": ramp}, PeekAtTheClose(), NO_COST).run()
    fill = result.fills[0]
    assert fill.date == ramp.index[1]
    assert fill.price == pytest.approx(ramp["open"].iloc[1])


def test_close_fill_model_uses_the_same_bar(ramp):
    class BuyOnBarZero(Strategy):
        def on_bar(self, ctx):
            if ctx.i == 0:
                ctx.buy("X", percent=1.0)

    config = RunConfig(cash=10_000, costs=Costs(slippage_bps=0), fill="close")
    result = Backtest({"X": ramp}, BuyOnBarZero(), config).run()
    assert result.fills[0].date == ramp.index[0]
    assert result.fills[0].price == pytest.approx(ramp["close"].iloc[0])


def test_history_never_shows_the_future(ramp):
    seen = []

    class Recorder(Strategy):
        def on_bar(self, ctx):
            seen.append(ctx.history("X").index[-1])

    Backtest({"X": ramp}, Recorder(), NO_COST).run()
    assert seen == list(ramp.index)


def test_stop_loss_exits_on_the_breaking_bar():
    index = pd.bdate_range("2020-01-01", periods=6)
    close = pd.Series([100, 100, 100, 80, 80, 80], index=index, dtype=float)
    frame = pd.DataFrame({"open": close, "high": close, "low": close,
                          "close": close, "volume": 1e6}, index=index)

    class Buyer(Strategy):
        def on_bar(self, ctx):
            if ctx.i == 0:
                ctx.buy("X", percent=1.0)

    config = RunConfig(cash=10_000, costs=Costs(slippage_bps=0), stop_loss=0.10)
    result = Backtest({"X": frame}, Buyer(), config).run()
    assert result.trades["exit_reason"].iloc[0] == "stop_loss"
    assert result.trades["exit_date"].iloc[0] == str(index[3].date())


def test_take_profit_exits_on_the_breaking_bar(ramp):
    class Buyer(Strategy):
        def on_bar(self, ctx):
            if ctx.i == 0:
                ctx.buy("X", percent=1.0)

    config = RunConfig(cash=10_000, costs=Costs(slippage_bps=0), take_profit=0.05)
    result = Backtest({"X": ramp}, Buyer(), config).run()
    assert result.trades["exit_reason"].iloc[0] == "take_profit"
    assert result.trades["return_pct"].iloc[0] >= 4.9


def test_shorting_is_refused_unless_enabled(ramp):
    class Shorter(Strategy):
        def on_bar(self, ctx):
            if ctx.i == 0:
                ctx.order_target_percent("X", -1.0)

    result = Backtest({"X": ramp}, Shorter(), NO_COST).run()
    assert result.trades.empty
    assert result.equity.iloc[-1] == pytest.approx(10_000)


def test_max_positions_caps_concurrent_holdings():
    frames = {name: make_frame(seed=i, periods=200) for i, name in enumerate("ABCD")}

    class BuyEverything(Strategy):
        def on_bar(self, ctx):
            if ctx.i == 0:
                for symbol in ctx.symbols:
                    ctx.order_target_percent(symbol, 0.25)

    config = RunConfig(cash=10_000, costs=Costs(slippage_bps=0), max_positions=2)
    result = Backtest(frames, BuyEverything(), config).run()
    assert result.positions.max() == 2


def test_warmup_bars_are_not_traded_or_recorded():
    frame = make_frame(seed=9, periods=300)
    trade_from = frame.index[100]

    class BuyOnFirstVisibleBar(Strategy):
        def on_bar(self, ctx):
            if ctx.i == ctx._engine._start_i:
                ctx.buy("X", percent=1.0)

    result = Backtest({"X": frame}, BuyOnFirstVisibleBar(), NO_COST,
                      trade_from=trade_from).run()
    assert result.equity.index[0] == trade_from
    assert len(result.equity) == 200
    assert result.meta["warmup_bars"] == 100


def test_costs_reduce_returns(ramp):
    free = Backtest({"X": ramp}, BuyAndHold(), NO_COST).run()
    pricey = Backtest({"X": ramp}, BuyAndHold(),
                      RunConfig(cash=10_000, costs=Costs(slippage_bps=50))).run()
    assert pricey.metrics["total_return"] < free.metrics["total_return"]


def test_everything_is_liquidated_at_the_end(ramp):
    result = Backtest({"X": ramp}, BuyAndHold(), NO_COST).run()
    assert result.equity.iloc[-1] == pytest.approx(result.cash.iloc[-1])
    assert result.trades["exit_reason"].iloc[-1] == "end_of_backtest"
