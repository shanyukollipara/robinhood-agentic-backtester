# Live results

Every strategy in [`examples/`](../examples) re-run against fresh market data on **2026-09-02 00:12 UTC**. Regenerated daily by [`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - these numbers move because the market moved, not because anything was tuned.

| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |
|---|---|---|---|---|---|---|---|---|---|---|
| [ATR Breakout](../examples/atr_breakout.yaml) | `QQQ` | 2012-01-03 | 57.90% | 3.16% | -7.58% | -2.34% | 0.75 | 67 | 50.7% | QQQ 1308.03% |
| [Golden Cross](../examples/golden_cross.yaml) | `SPY` | 2010-01-04 | 314.74% | 8.92% | -33.72% | -12.49% | 0.68 | 8 | 75.0% | SPY 800.68% |
| [Monthly Momentum](../examples/monthly_momentum.yaml) | `AAPL AMZN GOOGL META MSFT NVDA` | 2015-01-02 | 711.39% | 19.66% | -25.46% | -12.80% | 1.04 | 139 | 46.8% | SPY 348.93% |
| [RSI Dip Buyer](../examples/rsi_dip_buyer.yaml) | `IWM QQQ SPY` | 2012-01-03 | 39.67% | 2.31% | -17.90% | -7.97% | 0.45 | 368 | 70.7% | SPY 669.03% |

## Last 6 months, month by month

Return and the worst peak-to-trough fall *inside* each month.

### ATR Breakout

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +2.68% | -0.31% | -4.43% | $31,125.48 |
| 2026-05 | +3.50% | -0.85% | -1.61% | $32,213.61 |
| 2026-06 | -1.06% | -2.05% | -2.05% | $31,872.77 |
| 2026-07 | +0.00% | 0.00% | -1.44% | $31,872.77 |
| 2026-08 | -0.92% | -1.12% | -2.54% | $31,579.07 |
| 2026-09 | +0.00% | 0.00% | -2.34% | $31,579.07 |

### Golden Cross

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +10.51% | -0.85% | -7.68% | $39,045.69 |
| 2026-05 | +5.26% | -1.93% | -1.93% | $41,100.50 |
| 2026-06 | -1.03% | -4.49% | -4.49% | $40,677.47 |
| 2026-07 | +0.03% | -3.38% | -3.72% | $40,691.63 |
| 2026-08 | +2.68% | -1.96% | -1.96% | $41,782.14 |
| 2026-09 | -0.74% | 0.00% | -2.12% | $41,474.33 |

### Monthly Momentum

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.00% | 0.00% | -11.78% | $234,659.86 |
| 2026-05 | +2.69% | -1.91% | -11.92% | $240,972.84 |
| 2026-06 | -12.80% | -11.65% | -21.24% | $210,126.76 |
| 2026-07 | -2.64% | -6.89% | -23.08% | $204,582.14 |
| 2026-08 | -0.78% | -4.38% | -25.46% | $202,985.20 |
| 2026-09 | -0.07% | 0.00% | -23.74% | $202,848.10 |

### RSI Dip Buyer

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.57% | 0.00% | -1.00% | $13,829.06 |
| 2026-05 | +0.62% | -0.16% | -0.48% | $13,915.35 |
| 2026-06 | -0.19% | -1.96% | -2.12% | $13,888.26 |
| 2026-07 | +0.83% | -1.92% | -1.92% | $14,002.95 |
| 2026-08 | -0.06% | -0.67% | -0.80% | $13,994.07 |
| 2026-09 | -0.19% | 0.00% | -0.39% | $13,966.89 |

---

Full history of every daily run: [`history.csv`](history.csv). Per-strategy metrics: the `.json` files beside it. Interactive tearsheets are rebuilt into [`reports/`](../reports).

A backtest is a simulation over historical prices, not advice, and not a promise about the future. See the disclaimer in the [README](../README.md).