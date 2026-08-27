import pandas as pd

from rhbt.portfolio import Costs, Portfolio


def test_buy_reduces_cash_and_opens_a_position():
    book = Portfolio(cash=10_000, costs=Costs(slippage_bps=0))
    book.execute("AAPL", 10, 100.0, pd.Timestamp("2020-01-02"), 0)
    assert book.cash == 9_000
    assert book.qty("AAPL") == 10


def test_slippage_always_works_against_you():
    costs = Costs(slippage_bps=100)          # 1%
    assert costs.fill_price(100.0, +1) == 101.0
    assert costs.fill_price(100.0, -1) == 99.0


def test_cash_never_goes_negative_without_margin():
    book = Portfolio(cash=1_000, costs=Costs(slippage_bps=0))
    book.execute("AAPL", 100, 100.0, pd.Timestamp("2020-01-02"), 0)   # wants $10k
    assert book.cash >= -1e-9
    assert book.qty("AAPL") == 10


def test_round_trip_is_logged_with_pnl():
    book = Portfolio(cash=10_000, costs=Costs(slippage_bps=0))
    book.execute("AAPL", 10, 100.0, pd.Timestamp("2020-01-02"), 0)
    book.execute("AAPL", -10, 110.0, pd.Timestamp("2020-01-10"), 6, reason="exit")
    assert len(book.trades) == 1
    trade = book.trades[0]
    assert trade.pnl == 100.0
    assert trade.exit_reason == "exit"
    assert round(trade.return_pct, 6) == 0.1
    assert trade.bars_held == 6
    assert book.qty("AAPL") == 0


def test_commission_is_charged_and_tracked():
    book = Portfolio(cash=10_000, costs=Costs(slippage_bps=0, commission_flat=1.0))
    book.execute("AAPL", 10, 100.0, pd.Timestamp("2020-01-02"), 0)
    assert book.cash == 8_999.0
    assert book.total_fees == 1.0


def test_scaling_in_averages_the_entry_price():
    book = Portfolio(cash=10_000, costs=Costs(slippage_bps=0))
    book.execute("AAPL", 10, 100.0, pd.Timestamp("2020-01-02"), 0)
    book.execute("AAPL", 10, 120.0, pd.Timestamp("2020-01-03"), 1)
    assert book.position("AAPL").avg_price == 110.0
    assert len(book.trades) == 0          # still open, not a round trip yet


def test_partial_exit_stays_open_until_flat():
    book = Portfolio(cash=10_000, costs=Costs(slippage_bps=0))
    book.execute("AAPL", 10, 100.0, pd.Timestamp("2020-01-02"), 0)
    book.execute("AAPL", -4, 110.0, pd.Timestamp("2020-01-03"), 1)
    assert not book.trades
    book.execute("AAPL", -6, 120.0, pd.Timestamp("2020-01-04"), 2)
    assert len(book.trades) == 1
    assert round(book.trades[0].pnl, 6) == round(4 * 10 + 6 * 20, 6)


def test_short_position_profits_when_price_falls():
    book = Portfolio(cash=10_000, costs=Costs(slippage_bps=0), allow_short=True)
    book.execute("AAPL", -10, 100.0, pd.Timestamp("2020-01-02"), 0)
    book.execute("AAPL", 10, 90.0, pd.Timestamp("2020-01-05"), 3)
    assert book.trades[0].side == "short"
    assert book.trades[0].pnl == 100.0


def test_reversing_closes_one_trade_and_opens_another():
    book = Portfolio(cash=10_000, costs=Costs(slippage_bps=0), allow_short=True)
    book.execute("AAPL", 10, 100.0, pd.Timestamp("2020-01-02"), 0)
    book.execute("AAPL", -20, 110.0, pd.Timestamp("2020-01-06"), 2, reason="reverse")
    assert len(book.trades) == 1
    assert book.trades[0].side == "long" and book.trades[0].pnl == 100.0
    assert book.qty("AAPL") == -10
    book.execute("AAPL", 10, 100.0, pd.Timestamp("2020-01-08"), 4, reason="cover")
    assert len(book.trades) == 2
    assert book.trades[1].side == "short" and book.trades[1].pnl == 100.0
