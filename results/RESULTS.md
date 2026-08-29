# Live results

Every strategy in [`examples/`](../examples) re-run against fresh market data on **2026-08-29 03:42 UTC**. Regenerated daily by [`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - these numbers move because the market moved, not because anything was tuned.

| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |
|---|---|---|---|---|---|---|---|---|---|---|
| [ATR Breakout](../examples/atr_breakout.yaml) | `QQQ` | 2012-01-03 | 56.32% | 3.10% | -8.51% | -2.34% | 0.74 | 68 | 50.0% | QQQ 1325.52% |
| [Golden Cross](../examples/golden_cross.yaml) | `SPY` | 2010-01-04 | 318.86% | 8.99% | -33.72% | -12.49% | 0.69 | 8 | 75.0% | SPY 809.63% |
| [Monthly Momentum](../examples/monthly_momentum.yaml) | `AAPL AMZN GOOGL META MSFT NVDA` | 2015-01-02 | 720.67% | 19.80% | -25.46% | -12.80% | 1.05 | 139 | 46.8% | SPY 353.39% |
| [RSI Dip Buyer](../examples/rsi_dip_buyer.yaml) | `IWM QQQ SPY` | 2012-01-03 | 39.94% | 2.32% | -17.90% | -7.97% | 0.45 | 367 | 70.8% | SPY 676.67% |

## Last 6 months, month by month

Return and the worst peak-to-trough fall *inside* each month.

### ATR Breakout

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | +0.00% | 0.00% | -4.43% | $30,010.39 |
| 2026-04 | +2.68% | -0.31% | -4.43% | $30,814.45 |
| 2026-05 | +3.50% | -0.85% | -1.61% | $31,891.70 |
| 2026-06 | -1.06% | -2.05% | -2.05% | $31,554.27 |
| 2026-07 | +0.00% | 0.00% | -1.44% | $31,554.27 |
| 2026-08 | -0.92% | -1.12% | -2.54% | $31,263.50 |

### Golden Cross

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | -4.94% | -7.68% | -10.96% | $35,333.75 |
| 2026-04 | +10.51% | -0.85% | -7.68% | $39,045.65 |
| 2026-05 | +5.26% | -1.93% | -1.93% | $41,100.46 |
| 2026-06 | -1.03% | -4.49% | -4.49% | $40,677.43 |
| 2026-07 | +0.03% | -3.38% | -3.72% | $40,691.59 |
| 2026-08 | +2.94% | -1.96% | -1.96% | $41,886.43 |

### Monthly Momentum

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | -1.49% | -1.01% | -11.78% | $234,659.78 |
| 2026-04 | +0.00% | 0.00% | -11.78% | $234,659.78 |
| 2026-05 | +2.69% | -1.91% | -11.92% | $240,972.74 |
| 2026-06 | -12.80% | -11.65% | -21.24% | $210,126.68 |
| 2026-07 | -2.64% | -6.89% | -23.08% | $204,582.06 |
| 2026-08 | +0.29% | -4.38% | -25.46% | $205,166.83 |

### RSI Dip Buyer

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | -0.39% | -2.06% | -2.06% | $13,750.15 |
| 2026-04 | +0.57% | 0.00% | -1.00% | $13,829.08 |
| 2026-05 | +0.62% | -0.16% | -0.48% | $13,915.37 |
| 2026-06 | -0.19% | -1.96% | -2.12% | $13,888.27 |
| 2026-07 | +0.83% | -1.92% | -1.92% | $14,002.97 |
| 2026-08 | -0.06% | -0.67% | -0.80% | $13,994.16 |

---

Full history of every daily run: [`history.csv`](history.csv). Per-strategy metrics: the `.json` files beside it. Interactive tearsheets are rebuilt into [`reports/`](../reports).

A backtest is a simulation over historical prices, not advice, and not a promise about the future. See the disclaimer in the [README](../README.md).