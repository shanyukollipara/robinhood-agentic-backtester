# Live results

Every strategy in [`examples/`](../examples) re-run against fresh market data on **2026-09-12 00:16 UTC**. Regenerated daily by [`.github/workflows/daily-backtest.yml`](../.github/workflows/daily-backtest.yml) - these numbers move because the market moved, not because anything was tuned.

| Strategy | Symbols | Since | Return | CAGR | Max DD | Worst month | Sharpe | Trades | Win rate | vs benchmark |
|---|---|---|---|---|---|---|---|---|---|---|
| [ATR Breakout](../examples/atr_breakout.yaml) | `QQQ` | 2012-01-03 | 56.32% | 3.09% | -8.51% | -2.34% | 0.74 | 68 | 50.0% | QQQ 1310.12% |
| [Golden Cross](../examples/golden_cross.yaml) | `SPY` | 2010-01-04 | 312.59% | 8.87% | -33.72% | -12.49% | 0.68 | 8 | 75.0% | SPY 796.01% |
| [Monthly Momentum](../examples/monthly_momentum.yaml) | `AAPL AMZN GOOGL META MSFT NVDA` | 2015-01-02 | 705.03% | 19.54% | -25.46% | -12.80% | 1.04 | 140 | 46.4% | SPY 346.60% |
| [RSI Dip Buyer](../examples/rsi_dip_buyer.yaml) | `IWM QQQ SPY` | 2012-01-03 | 40.71% | 2.35% | -17.90% | -7.97% | 0.45 | 369 | 71.0% | SPY 665.04% |

## Last 6 months, month by month

Return and the worst peak-to-trough fall *inside* each month.

### ATR Breakout

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +2.68% | -0.31% | -4.43% | $30,814.38 |
| 2026-05 | +3.50% | -0.85% | -1.61% | $31,891.63 |
| 2026-06 | -1.06% | -2.05% | -2.05% | $31,554.20 |
| 2026-07 | +0.00% | 0.00% | -1.44% | $31,554.20 |
| 2026-08 | -0.92% | -1.12% | -2.54% | $31,263.43 |
| 2026-09 | +0.00% | 0.00% | -2.34% | $31,263.43 |

### Golden Cross

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +10.51% | -0.85% | -7.68% | $39,045.64 |
| 2026-05 | +5.26% | -1.93% | -1.93% | $41,100.44 |
| 2026-06 | -1.03% | -4.49% | -4.49% | $40,677.41 |
| 2026-07 | +0.03% | -3.38% | -3.72% | $40,691.58 |
| 2026-08 | +2.68% | -1.96% | -1.96% | $41,782.09 |
| 2026-09 | -1.25% | -2.03% | -2.63% | $41,259.22 |

### Monthly Momentum

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.00% | 0.00% | -11.78% | $234,660.01 |
| 2026-05 | +2.69% | -1.91% | -11.92% | $240,972.98 |
| 2026-06 | -12.80% | -11.65% | -21.24% | $210,126.89 |
| 2026-07 | -2.64% | -6.89% | -23.08% | $204,582.26 |
| 2026-08 | -0.78% | -4.38% | -25.46% | $202,985.33 |
| 2026-09 | -0.85% | -3.10% | -24.50% | $201,256.45 |

### RSI Dip Buyer

| Month | Return | Max DD in month | DD vs all-time high | End equity |
|---|---|---|---|---|
| 2026-04 | +0.57% | 0.00% | -1.00% | $13,829.05 |
| 2026-05 | +0.62% | -0.16% | -0.48% | $13,915.35 |
| 2026-06 | -0.19% | -1.96% | -2.12% | $13,888.25 |
| 2026-07 | +0.83% | -1.92% | -1.92% | $14,002.95 |
| 2026-08 | -0.06% | -0.67% | -0.80% | $13,994.07 |
| 2026-09 | +0.55% | -0.25% | -0.37% | $14,070.78 |

---

Full history of every daily run: [`history.csv`](history.csv). Per-strategy metrics: the `.json` files beside it. Interactive tearsheets are rebuilt into [`reports/`](../reports).

A backtest is a simulation over historical prices, not advice, and not a promise about the future. See the disclaimer in the [README](../README.md).