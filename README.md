# Robinhood Agentic Backtester

**Describe a trading strategy to your AI agent in plain English. Get a full
backtest - monthly drawdowns, tearsheet, trade log - running locally on your
machine.**

You do not write code. You do not learn a DSL. You clone this repo, point your
agent at it, and say what your strategy is. The agent translates it into a spec
file, runs it against real price data, and hands you an HTML report.

The backtest engine itself is deterministic Python. No LLM decides your fills,
your fees, or your drawdown numbers - it only writes the strategy file.

---

## Quickstart

```bash
git clone https://github.com/shanyukollipara/robinhood-agentic-backtester.git
cd robinhood-agentic-backtester
python3 -m venv .venv
.venv/bin/pip install -e ".[data]"
```

Try a bundled example - no account, no API key, no configuration:

```bash
.venv/bin/rhbt run examples/golden_cross.yaml --open
```

```
------------------------------------------------------------------------------
  Golden Cross   [SPY]
  2010-01-04 to 2026-08-26  (4184 bars, 16.6 years)
  params: fast=50, slow=200
------------------------------------------------------------------------------
  Start equity          $10,000.00    Total return            +317.08%
  Final equity          $41,708.45    CAGR                      +8.96%
  Max drawdown             -33.72%    Longest DD              693 days
  Worst month              -12.49%    Worst in-month DD        -28.32%
  Sharpe                      0.68    Sortino                     0.94
  Calmar                      0.27    Volatility                14.02%
  Trades                         8    Win rate                   75.0%
  Profit factor              11.25    Expectancy             $3,963.56
  Avg exposure               80.0%    Slippage cost             $161.63
  SPY return              +805.76%    Alpha (annual)            -5.20%
------------------------------------------------------------------------------

  Monthly performance and drawdown
  Month        Return   Max DD in mo   DD vs ATH     End equity
  2024-10      -0.99%         -3.30%      -3.30%      39,884.11
  2024-11       5.73%         -1.36%      -0.65%      42,169.30
  ...
```

Plus `reports/golden_cross.html`: equity curve, underwater plot, a monthly
returns heatmap, the month-by-month drawdown table, every statistic, and the
full trade log - one self-contained file you can email to anyone.

## Using it with your AI agent

This is the point of the repo. Any MCP-capable agent works - Claude Code,
Claude Desktop, ChatGPT, Codex, Cursor, Grok.

**1. Connect the Robinhood Trading MCP** (optional but recommended - it gives
your agent your broker's own price data). Robinhood's setup instructions per
platform are at the link they give you; for Claude Code it is:

```bash
claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading
```

then `/mcp` and authenticate. Without this, the repo falls back to free
yfinance data, so everything still works.

**2. Point your agent at the repo** and just describe the strategy:

> "Clone this repo and backtest this for me: buy SPY whenever the 2-day RSI
> drops below 10 while it's still above its 200-day moving average, sell when
> RSI gets back over 60, cut anything that loses 8%. Start from 2015, $10k."

The agent reads [AGENTS.md](AGENTS.md) - the operating manual it needs - writes
`strategies/rsi_dip_buyer.yaml`, runs it, and explains the results.

**3. Iterate in plain English.** "What if I hold at most 5 days?" "Try it on
QQQ too." "Does it still work with a 3-day RSI?" Each is one edit and one rerun.

The agent never places a trade. This repo backtests; it does not touch your
account.

## What you get

Every run produces:

**Headline metrics** - total return, CAGR, max drawdown (with the dates and how
long it took to recover), Sharpe, Sortino, Calmar, volatility, Ulcer index,
VaR/CVaR, exposure, and the cost of trading.

**Month-by-month detail** - this is the table most backtesters skip:

| Column | Meaning |
|---|---|
| Return | The month's return, chained from the previous month's close |
| Max DD in month | Worst peak-to-trough fall *inside* that calendar month |
| DD vs ATH | How far below the all-time equity high you got during the month |
| DD at end | Where you stood versus the high on the last day of the month |
| Benchmark | Same month, buy-and-hold |

**Trade log** - every round trip with entry, exit, P&L, bars held, exit reason,
and MAE/MFE (how far it went against you before it worked, and vice versa).

**Yearly summary**, a **monthly returns heatmap**, and a JSON export
(`--json out.json`) if you want to do your own analysis.

## Writing strategies yourself

You do not need an agent. A strategy is a YAML file:

```yaml
name: RSI Dip Buyer
symbols: [SPY, QQQ]
start: 2015-01-01
cash: 10000

params:
  lookback: 2
  oversold: 10

rules:
  entry: "rsi(close, lookback) < oversold and close > sma(close, 200)"
  exit:  "rsi(close, lookback) > 60"

risk:
  stop_loss: 0.08

sizing:
  mode: equal_weight
```

Rules are plain expressions over `open`, `high`, `low`, `close`, `volume` and
a library of ~30 indicators (`sma`, `ema`, `rsi`, `macd`, `atr`, `bb_upper`,
`adx`, `zscore`, `donchian_high`, `crossover`, ...). Run `rhbt indicators` to
list them all with signatures. Expressions are parsed and sandboxed - no
imports, no attribute access, no file system.

Or skip straight to the terminal:

```bash
rhbt run --symbols SPY --entry "rsi(close,2) < 10" --exit "rsi(close,2) > 60" --start 2015-01-01
```

For anything a single expression cannot express - cross-sectional ranking,
custom state, multi-leg logic - write Python. Copy `examples/custom_strategy.py`:

```python
from rhbt import Strategy

class MyStrategy(Strategy):
    params = {"window": 20}

    def on_bar(self, ctx):
        for symbol in ctx.symbols:
            closes = ctx.history(symbol)["close"]        # never sees the future
            if closes.iloc[-1] > closes.rolling(self.params["window"]).mean().iloc[-1]:
                ctx.order_target_percent(symbol, 0.5)
            else:
                ctx.close(symbol)
```

```bash
rhbt run --strategy my_strategy.py --symbols SPY,QQQ --start 2018-01-01
```

## Commands

| Command | What it does |
|---|---|
| `rhbt run <spec.yaml>` | Run a backtest, print the summary, write the report |
| `rhbt run --symbols SPY --entry "..." --exit "..."` | Run without a spec file |
| `rhbt run --strategy file.py:Class --symbols ...` | Run a Python strategy |
| `rhbt sweep <spec.yaml> --param fast=20,50,100` | Grid-search parameters, ranked |
| `rhbt validate <spec.yaml>` | Check a spec compiles, without downloading data |
| `rhbt data import --symbol AAPL < bars.json` | Load Robinhood MCP historicals |
| `rhbt data fetch SPY QQQ --start 2015-01-01` | Download bars into the cache |
| `rhbt data list` / `rhbt data clear` | Inspect / empty the cache |
| `rhbt indicators` / `rhbt schema` | Reference output (also for agents) |
| `rhbt examples` | List the bundled example strategies |

## How the engine works

On every bar, in this order:

1. Orders signalled on the **previous** bar fill at **this** bar's open.
2. Stop-loss, take-profit and trailing stops are checked against this bar's
   high and low.
3. The portfolio is marked to this bar's close and equity is recorded.
4. Your strategy runs and may queue orders - for the next bar.

That ordering is the whole point: a signal can never be filled at a price it
had not yet seen. `execution.fill: close` is available if you want same-bar
fills, but the default is `next_open` because it is the honest one.

Other defaults: slippage of 5 bps always works against you, commissions are
zero (Robinhood equities are commission-free), fractional shares are allowed,
cash cannot go negative, positions are liquidated on the last bar, and 250 bars
of history are loaded *before* your start date so a 200-day average is already
warm on day one.

## Data

Price data resolves in this order:

1. **Local cache** (`data/cache/`) - CSVs, one per symbol and interval.
2. **Robinhood Trading MCP** - your agent calls `get_equity_historicals` and
   pipes the response into `rhbt data import`. The repo holds no credentials
   and makes no Robinhood calls itself.
3. **yfinance** - automatic fallback so anyone can clone and run immediately.

Set `RHBT_DATA_DIR` to move the cache. Use `--offline` to forbid all network
access, `--refresh` to re-download.

## Development

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
```

The test suite is offline and deterministic - it generates synthetic prices
rather than hitting any API.

Contributions welcome, especially: more indicators, options and crypto support,
walk-forward and Monte Carlo analysis, and portfolio-level position sizing.

## Disclaimer

This is research software, not investment advice, and its authors are not
licensed financial advisors. A backtest is a simulation over historical prices:
it assumes your orders fill at modelled prices, ignores borrow costs, halts and
taxes, includes dividends only when the underlying data is adjusted for them,
and cannot model how you would actually behave in a 30% drawdown. Past results
do not predict future returns. Nothing here places a trade for you, and nothing
here should be the only reason you place one yourself.

MIT licensed. See [LICENSE](LICENSE).
