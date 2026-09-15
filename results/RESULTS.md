# Live results

Every strategy in [`examples/`](../examples) re-run against fresh market data on **2026-09-15 00:36 UTC**. Regenerated daily by [`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - these numbers move because the market moved, not because anything was tuned.

| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |
|---|---|---|---|---|---|---|---|---|---|---|
| [ATR Breakout](../examples/atr_breakout.yaml) | `QQQ` | 2012-01-03 | 57.90% | 3.16% | -7.58% | -2.34% | 0.75 | 67 | 50.7% | QQQ 1322.44% |
| [Golden Cross](../examples/golden_cross.yaml) | `SPY` | 2010-01-04 | 316.11% | 8.92% | -33.72% | -12.49% | 0.68 | 8 | 75.0% | SPY 803.65% |
| [Monthly Momentum](../examples/monthly_momentum.yaml) | `AAPL AMZN GOOGL META MSFT NVDA` | 2015-01-02 | 710.40% | 19.60% | -25.46% | -12.80% | 1.04 | 140 | 46.4% | SPY 350.41% |
| [RSI Dip Buyer](../examples/rsi_dip_buyer.yaml) | `IWM QQQ SPY` | 2012-01-03 | 40.20% | 2.33% | -17.90% | -7.97% | 0.45 | 372 | 70.4% | SPY 671.57% |

## Last 6 months, month by month

Return and the worst peak-to-trough fall *inside* each month.

### ATR Breakout

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +2.68% | -0.31% | -4.43% | $31,125.45 |
| 2026-05 | +3.50% | -0.85% | -1.61% | $32,213.58 |
| 2026-06 | -1.06% | -2.05% | -2.05% | $31,872.73 |
| 2026-07 | +0.00% | 0.00% | -1.44% | $31,872.73 |
| 2026-08 | -0.92% | -1.12% | -2.54% | $31,579.03 |
| 2026-09 | +0.00% | 0.00% | -2.34% | $31,579.03 |

### Golden Cross

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +10.51% | -0.85% | -7.68% | $39,045.66 |
| 2026-05 | +5.26% | -1.93% | -1.93% | $41,100.47 |
| 2026-06 | -1.03% | -4.49% | -4.49% | $40,677.44 |
| 2026-07 | +0.03% | -3.38% | -3.72% | $40,691.60 |
| 2026-08 | +2.68% | -1.96% | -1.96% | $41,782.12 |
| 2026-09 | -0.41% | -1.98% | -2.58% | $41,610.96 |

### Monthly Momentum

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.00% | 0.00% | -11.78% | $234,660.19 |
| 2026-05 | +2.69% | -1.91% | -11.92% | $240,973.17 |
| 2026-06 | -12.80% | -11.65% | -21.24% | $210,127.05 |
| 2026-07 | -2.64% | -6.89% | -23.08% | $204,582.42 |
| 2026-08 | -0.78% | -4.38% | -25.46% | $202,985.48 |
| 2026-09 | -0.19% | -3.10% | -24.50% | $202,599.11 |

### RSI Dip Buyer

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.57% | 0.00% | -1.00% | $13,829.06 |
| 2026-05 | +0.62% | -0.16% | -0.48% | $13,915.35 |
| 2026-06 | -0.19% | -1.96% | -2.12% | $13,888.25 |
| 2026-07 | +0.83% | -1.92% | -1.92% | $14,002.95 |
| 2026-08 | -0.06% | -0.67% | -0.80% | $13,994.07 |
| 2026-09 | +0.18% | -0.62% | -0.62% | $14,019.54 |

---

Full history of every daily run: [`history.csv`](history.csv). Per-strategy metrics: the `.json` files beside it. Interactive tearsheets are rebuilt into [`reports/`](../reports).

A backtest is a simulation over historical prices, not advice, and not a promise about the future. See the disclaimer in the [README](../README.md).