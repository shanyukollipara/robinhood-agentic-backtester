# Live results

Every strategy in [`examples/`](../examples) re-run against fresh market data on **2026-09-08 00:24 UTC**. Regenerated daily by [`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - these numbers move because the market moved, not because anything was tuned.

| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |
|---|---|---|---|---|---|---|---|---|---|---|
| [ATR Breakout](../examples/atr_breakout.yaml) | `QQQ` | 2012-01-03 | 56.32% | 3.09% | -8.51% | -2.34% | 0.74 | 68 | 50.0% | QQQ 1330.56% |
| [Golden Cross](../examples/golden_cross.yaml) | `SPY` | 2010-01-04 | 319.32% | 8.98% | -33.72% | -12.49% | 0.69 | 8 | 75.0% | SPY 810.62% |
| [Monthly Momentum](../examples/monthly_momentum.yaml) | `AAPL AMZN GOOGL META MSFT NVDA` | 2015-01-02 | 719.43% | 19.75% | -25.46% | -12.80% | 1.05 | 140 | 47.1% | SPY 353.89% |
| [RSI Dip Buyer](../examples/rsi_dip_buyer.yaml) | `IWM QQQ SPY` | 2012-01-03 | 40.71% | 2.36% | -17.90% | -7.97% | 0.45 | 369 | 71.0% | SPY 677.52% |

## Last 6 months, month by month

Return and the worst peak-to-trough fall *inside* each month.

### ATR Breakout

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +2.68% | -0.31% | -4.43% | $30,814.37 |
| 2026-05 | +3.50% | -0.85% | -1.61% | $31,891.62 |
| 2026-06 | -1.06% | -2.05% | -2.05% | $31,554.19 |
| 2026-07 | +0.00% | 0.00% | -1.44% | $31,554.19 |
| 2026-08 | -0.92% | -1.12% | -2.54% | $31,263.42 |
| 2026-09 | +0.00% | 0.00% | -2.34% | $31,263.42 |

### Golden Cross

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +10.51% | -0.85% | -7.68% | $39,045.68 |
| 2026-05 | +5.26% | -1.93% | -1.93% | $41,100.49 |
| 2026-06 | -1.03% | -4.49% | -4.49% | $40,677.46 |
| 2026-07 | +0.03% | -3.38% | -3.72% | $40,691.63 |
| 2026-08 | +2.68% | -1.96% | -1.96% | $41,782.14 |
| 2026-09 | +0.36% | -0.44% | -2.07% | $41,932.20 |

### Monthly Momentum

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.00% | 0.00% | -11.78% | $234,659.90 |
| 2026-05 | +2.69% | -1.91% | -11.92% | $240,972.87 |
| 2026-06 | -12.80% | -11.65% | -21.24% | $210,126.79 |
| 2026-07 | -2.64% | -6.89% | -23.08% | $204,582.17 |
| 2026-08 | -0.78% | -4.38% | -25.46% | $202,985.23 |
| 2026-09 | +0.92% | -1.16% | -23.69% | $204,857.83 |

### RSI Dip Buyer

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.57% | 0.00% | -1.00% | $13,829.02 |
| 2026-05 | +0.62% | -0.16% | -0.48% | $13,915.31 |
| 2026-06 | -0.19% | -1.96% | -2.12% | $13,888.22 |
| 2026-07 | +0.83% | -1.92% | -1.92% | $14,002.91 |
| 2026-08 | -0.06% | -0.67% | -0.80% | $13,994.04 |
| 2026-09 | +0.55% | -0.25% | -0.37% | $14,070.75 |

---

Full history of every daily run: [`history.csv`](history.csv). Per-strategy metrics: the `.json` files beside it. Interactive tearsheets are rebuilt into [`reports/`](../reports).

A backtest is a simulation over historical prices, not advice, and not a promise about the future. See the disclaimer in the [README](../README.md).