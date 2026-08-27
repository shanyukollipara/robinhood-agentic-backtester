# Live results

Every strategy in [`examples/`](../examples) re-run against fresh market data on **2026-08-27 05:35 UTC**. Regenerated daily by [`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - these numbers move because the market moved, not because anything was tuned.

| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |
|---|---|---|---|---|---|---|---|---|---|---|
| [ATR Breakout](../examples/atr_breakout.yaml) | `QQQ` | 2012-01-03 | 56.32% | 3.10% | -8.51% | -2.34% | 0.74 | 68 | 50.0% | QQQ 1315.46% |
| [Golden Cross](../examples/golden_cross.yaml) | `SPY` | 2010-01-04 | 317.08% | 8.96% | -33.72% | -12.49% | 0.68 | 8 | 75.0% | SPY 805.76% |
| [Monthly Momentum](../examples/monthly_momentum.yaml) | `AAPL AMZN GOOGL META MSFT NVDA` | 2015-01-02 | 704.71% | 19.61% | -25.46% | -12.80% | 1.04 | 139 | 46.8% | SPY 351.46% |
| [RSI Dip Buyer](../examples/rsi_dip_buyer.yaml) | `IWM QQQ SPY` | 2012-01-03 | 39.40% | 2.29% | -17.90% | -7.97% | 0.44 | 367 | 70.8% | SPY 673.37% |

## Last 6 months, month by month

Return and the worst peak-to-trough fall *inside* each month.

### ATR Breakout

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | +0.00% | 0.00% | -4.43% | $30,010.30 |
| 2026-04 | +2.68% | -0.31% | -4.43% | $30,814.35 |
| 2026-05 | +3.50% | -0.85% | -1.61% | $31,891.60 |
| 2026-06 | -1.06% | -2.05% | -2.05% | $31,554.17 |
| 2026-07 | +0.00% | 0.00% | -1.44% | $31,554.17 |
| 2026-08 | -0.92% | -1.12% | -2.54% | $31,263.40 |

### Golden Cross

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | -4.94% | -7.68% | -10.96% | $35,333.79 |
| 2026-04 | +10.51% | -0.85% | -7.68% | $39,045.70 |
| 2026-05 | +5.26% | -1.93% | -1.93% | $41,100.51 |
| 2026-06 | -1.03% | -4.49% | -4.49% | $40,677.48 |
| 2026-07 | +0.03% | -3.38% | -3.72% | $40,691.64 |
| 2026-08 | +2.50% | -1.96% | -1.96% | $41,708.45 |

### Monthly Momentum

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | -1.49% | -1.01% | -11.78% | $234,659.88 |
| 2026-04 | +0.00% | 0.00% | -11.78% | $234,659.88 |
| 2026-05 | +2.69% | -1.91% | -11.92% | $240,972.85 |
| 2026-06 | -12.80% | -11.65% | -21.24% | $210,126.77 |
| 2026-07 | -2.64% | -6.89% | -23.08% | $204,582.15 |
| 2026-08 | -1.66% | -4.38% | -25.46% | $201,177.56 |

### RSI Dip Buyer

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-03 | -0.39% | -2.06% | -2.06% | $13,750.13 |
| 2026-04 | +0.57% | 0.00% | -1.00% | $13,829.05 |
| 2026-05 | +0.62% | -0.16% | -0.48% | $13,915.35 |
| 2026-06 | -0.19% | -1.96% | -2.12% | $13,888.25 |
| 2026-07 | +0.83% | -1.92% | -1.92% | $14,002.95 |
| 2026-08 | -0.45% | -0.67% | -0.80% | $13,939.87 |

---

Full history of every daily run: [`history.csv`](history.csv). Per-strategy metrics: the `.json` files beside it. Interactive tearsheets are rebuilt into [`reports/`](../reports).

A backtest is a simulation over historical prices, not advice, and not a promise about the future. See the disclaimer in the [README](../README.md).