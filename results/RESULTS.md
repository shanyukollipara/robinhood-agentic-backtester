# Live results

Every strategy in [`examples/`](../examples) re-run against fresh market data on **2026-09-25 00:32 UTC**. Regenerated daily by [`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - these numbers move because the market moved, not because anything was tuned.

| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |
|---|---|---|---|---|---|---|---|---|---|---|
| [ATR Breakout](../examples/atr_breakout.yaml) | `QQQ` | 2012-01-03 | 56.26% | 3.08% | -8.51% | -2.34% | 0.74 | 69 | 49.3% | QQQ 1376.37% |
| [Golden Cross](../examples/golden_cross.yaml) | `SPY` | 2010-01-04 | 319.06% | 8.95% | -33.72% | -12.49% | 0.68 | 8 | 75.0% | SPY 810.06% |
| [Monthly Momentum](../examples/monthly_momentum.yaml) | `AAPL AMZN GOOGL META MSFT NVDA` | 2015-01-02 | 711.59% | 19.55% | -25.46% | -12.80% | 1.04 | 140 | 46.4% | SPY 353.61% |
| [RSI Dip Buyer](../examples/rsi_dip_buyer.yaml) | `IWM QQQ SPY` | 2012-01-03 | 40.06% | 2.31% | -17.90% | -7.97% | 0.45 | 372 | 70.7% | SPY 677.04% |

## Last 6 months, month by month

Return and the worst peak-to-trough fall *inside* each month.

### ATR Breakout

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +2.68% | -0.31% | -4.43% | $30,814.39 |
| 2026-05 | +3.50% | -0.85% | -1.61% | $31,891.65 |
| 2026-06 | -1.06% | -2.05% | -2.05% | $31,554.21 |
| 2026-07 | +0.00% | 0.00% | -1.44% | $31,554.21 |
| 2026-08 | -0.92% | -1.12% | -2.54% | $31,263.45 |
| 2026-09 | -0.04% | -0.33% | -2.38% | $31,251.34 |

### Golden Cross

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +10.51% | -0.85% | -7.68% | $39,045.65 |
| 2026-05 | +5.26% | -1.93% | -1.93% | $41,100.46 |
| 2026-06 | -1.03% | -4.49% | -4.49% | $40,677.43 |
| 2026-07 | +0.03% | -3.38% | -3.72% | $40,691.59 |
| 2026-08 | +2.68% | -1.96% | -1.96% | $41,782.10 |
| 2026-09 | +0.30% | -2.47% | -3.06% | $41,906.39 |

### Monthly Momentum

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.00% | 0.00% | -11.78% | $234,659.76 |
| 2026-05 | +2.69% | -1.91% | -11.92% | $240,972.73 |
| 2026-06 | -12.80% | -11.65% | -21.24% | $210,126.67 |
| 2026-07 | -2.64% | -6.89% | -23.08% | $204,582.05 |
| 2026-08 | -0.78% | -4.38% | -25.46% | $202,985.11 |
| 2026-09 | -0.04% | -3.10% | -24.50% | $202,896.93 |

### RSI Dip Buyer

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.57% | 0.00% | -1.00% | $13,829.01 |
| 2026-05 | +0.62% | -0.16% | -0.48% | $13,915.30 |
| 2026-06 | -0.19% | -1.96% | -2.12% | $13,888.20 |
| 2026-07 | +0.83% | -1.92% | -1.92% | $14,002.90 |
| 2026-08 | -0.06% | -0.67% | -0.80% | $13,994.02 |
| 2026-09 | +0.08% | -1.77% | -1.77% | $14,005.55 |

---

Full history of every daily run: [`history.csv`](history.csv). Per-strategy metrics: the `.json` files beside it. Interactive tearsheets are rebuilt into [`reports/`](../reports).

A backtest is a simulation over historical prices, not advice, and not a promise about the future. See the disclaimer in the [README](../README.md).