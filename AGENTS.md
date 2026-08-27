# Instructions for AI agents

You are reading this because someone cloned this repo and asked you to backtest
a trading strategy. This file tells you exactly how to do that. Follow it
literally; do not invent your own workflow.

Your job has four steps:

1. **Set the repo up** (once per machine).
2. **Translate** the user's strategy into a spec file - faithfully, to the dime.
3. **Run** it with the `rhbt` CLI.
4. **Explain** the numbers, honestly, including the monthly drawdowns.

---

## 1. Setup

Run this once, from the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[data]"
```

Then use `.venv/bin/rhbt` (or activate the venv) for every command below.
Verify it works:

```bash
.venv/bin/rhbt --help
.venv/bin/rhbt examples
```

## 2. Get price data

There are two sources and you should prefer the first.

**A. Robinhood Trading MCP (preferred if the user has it connected).**
This repo has no Robinhood credentials and never will - *you* are the one
connected to the MCP. Call `get_equity_historicals` yourself, then pipe the raw
JSON response straight into the cache:

```bash
.venv/bin/rhbt data import --symbol AAPL --interval day --file bars.json
```

Use `adjustment_type: "split"` (the default) and `interval: "day"` for anything
longer than a few months. The importer accepts the response as-is - a bare list
of bars, `{"results": [...]}`, or a per-symbol object. If the payload does not
name the symbol, pass `--symbol`.

**B. yfinance fallback (no account needed).**
If you skip the import, `rhbt` downloads daily bars automatically the first time
it needs a ticker and caches them under `data/cache/`. This is what makes the
repo work for people who have not connected anything.

Do not mix the two sources for the same ticker - the adjustments differ. Run
`rhbt data clear --symbol X` before switching.

Check what is cached at any time:

```bash
.venv/bin/rhbt data list
```

## 3. Write the spec

A strategy is a YAML file. Write it to `strategies/<name>.yaml` (create the
folder if needed) so the user keeps it. This is the whole format:

```yaml
name: RSI Dip Buyer                 # shown on the report
description: >                      # write the user's own words here
  Buy SPY when the 2-day RSI drops under 10 while price is above the
  200-day average; sell when RSI recovers past 60 or an 8% stop hits.

symbols: [SPY, QQQ]                 # required
start: 2015-01-01                   # optional; defaults to all available data
end: 2025-12-31                     # optional
interval: day                       # day | week | month | hour | minute
cash: 10000                         # starting capital
benchmark: SPY                      # or `none`
warmup: 250                         # bars loaded before `start` to warm indicators
rebalance: every_bar                # every_bar | weekly | monthly | quarterly

params:                             # any name here is usable inside the rules
  lookback: 2
  oversold: 10

rules:
  entry: "rsi(close, lookback) < oversold and close > sma(close, 200)"
  exit:  "rsi(close, lookback) > 60"
  filter: "volume > 1000000"        # optional; ANDed onto every entry
  short_entry: "..."                # optional; enables shorting
  short_exit: "..."                 # optional

sizing:
  mode: equal_weight                # equal_weight | full_equity | fixed_percent
                                    # | fixed_value | fixed_shares | atr_risk
                                    # | volatility_target
  value: 0.25                       # meaning depends on mode
  max_weight: 0.5
  risk_per_trade: 0.01              # atr_risk only
  atr_window: 14                    # atr_risk only
  atr_mult: 2.0                     # atr_risk only
  target_vol: 0.15                  # volatility_target only

risk:
  stop_loss: 0.08                   # 8% below entry
  take_profit: 0.25
  trailing_stop: 0.15
  max_hold_bars: 20
  min_hold_bars: 0

fees:
  slippage_bps: 5                   # always works against the fill
  commission_bps: 0                 # Robinhood equities are commission-free
  commission_per_share: 0
  commission_flat: 0

execution:
  fill: next_open                   # next_open (default, honest) | close
  allow_short: false
  allow_fractional: true
  max_positions: 3
  liquidate_at_end: true
```

Rules are ordinary expressions over `open`, `high`, `low`, `close`, `volume`
(plus `price`, `typical`, `returns`, `bar`, `day`, `month`, `year`,
`dayofweek`) and the indicator library. `and`, `or`, `not` work element-wise.
Run this to see every function and its signature:

```bash
.venv/bin/rhbt indicators
.venv/bin/rhbt schema        # the same information as JSON
```

Check the spec before running it - this catches typos without downloading data:

```bash
.venv/bin/rhbt validate strategies/my_strategy.yaml
```

### Translating faithfully

The user's description is the specification. Reproduce it exactly:

- Keep their numbers. If they say a 21-day average, use 21, not 20.
- Put every number they mention into `params:` so they can sweep it later.
- Copy their own wording into `description:`.
- If something is genuinely ambiguous, **ask one question** rather than guessing.
  ("Sell everything, or just that position?" "8% from entry or from the high?")
- If you must assume something, say so in the chat and write it in `description:`.
- Never quietly add a filter, a stop, or a position limit they did not ask for.
  Suggest it after the first run instead.

Common translations:

| They say | You write |
|---|---|
| "when the 50-day crosses above the 200-day" | `crossover(sma(close, 50), sma(close, 200))` |
| "while the 50-day is above the 200-day" | `sma(close, 50) > sma(close, 200)` |
| "RSI below 30" | `rsi(close, 14) < 30` |
| "buy the dip: down 5% in a week" | `roc(close, 5) < -0.05` |
| "breaks out to a 20-day high" | `close > donchian_high(high, 20)` |
| "above its 200-day trend" | `close > sma(close, 200)` |
| "MACD turns positive" | `crossover(macd(close), macd_signal(close))` |
| "when it is 2 standard deviations below the mean" | `zscore(close, 20) < -2` |
| "volatility is low" | `atr(high, low, close, 14) / close < 0.02` |
| "hold for 10 days then sell" | `risk: {max_hold_bars: 10}` |
| "risk 1% per trade" | `sizing: {mode: atr_risk, risk_per_trade: 0.01}` |
| "rebalance monthly" | `rebalance: monthly` |
| "all in on one name" | `sizing: {mode: full_equity}` |

If the logic genuinely cannot be written as an expression - it needs state,
ranking across symbols, or multi-leg bookkeeping - write a Python strategy
instead. Copy `examples/custom_strategy.py`, subclass `Strategy`, implement
`on_bar(self, ctx)`, and run it with
`rhbt run --strategy path/to/file.py:ClassName --symbols ...`.
The `ctx` API is documented in `rhbt/strategy.py`.

## 4. Run it

```bash
.venv/bin/rhbt run strategies/my_strategy.yaml
```

Useful flags: `--offline` (cache only), `--refresh` (re-download),
`--json out.json` (machine-readable results for you to read),
`--report reports/name.html`, `--all-months`, `--param fast=20` (override),
`--open` (open the report in a browser).

To test parameter sensitivity - always worth doing before anyone believes a
result:

```bash
.venv/bin/rhbt sweep strategies/my_strategy.yaml --param lookback=2,3,5 --param oversold=5,10,20
```

Read the JSON output rather than re-deriving numbers yourself. Never compute
returns or drawdowns by hand and never state a figure the tool did not print.

## 5. Explain the results

Report at minimum: total return and CAGR, max drawdown and how long it lasted,
the worst month and its in-month drawdown, Sharpe, number of trades and win
rate, and how it compares to the benchmark. Point the user at the HTML report
for the full month-by-month table.

Two different monthly drawdown numbers appear, and you should not confuse them:

- **Max DD in month** - the worst peak-to-trough fall *inside* that calendar
  month. The peak resets on the 1st.
- **DD vs ATH** - how far below the all-time equity high the account got during
  that month.

Be honest about what a backtest is worth:

- A strategy with 6 trades has not been tested, it has been anecdote-fitted.
- If a sweep shows the result collapsing when a parameter moves by one, say so.
- The default `fill: next_open` is deliberate. Do not switch to `fill: close`
  to make results look better - that trades on a price the strategy only knew
  at the bell.
- Dividends are included only when the data source adjusts for them (the
  yfinance fallback does; Robinhood `adjustment_type: split` does not).
- Say plainly that this is a simulation, not advice, and that you are not a
  licensed financial advisor.

## What not to do

- Do not place real trades. This repo backtests; it never sends an order.
  If the user asks you to trade, that is a separate decision they make
  themselves in their broker.
- Do not edit `rhbt/` to make a strategy look better.
- Do not fabricate bars, fill gaps by hand, or extend a series past its data.
- Do not report a metric the tool did not produce.
