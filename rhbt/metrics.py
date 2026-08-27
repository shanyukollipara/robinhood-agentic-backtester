"""Performance statistics, including the monthly return / drawdown table.

Two different drawdown numbers are reported per month, because people mean
different things by "monthly drawdown":

``month_dd_pct``
    Worst peak-to-trough decline that happened *inside* that calendar month.
    The peak resets on the first bar of the month.
``dd_from_peak_pct``
    Worst drawdown during the month measured against the all-time equity high,
    i.e. how deep underwater the account got that month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_TRADING_DAYS = 252


def _clean(equity: pd.Series) -> pd.Series:
    series = pd.Series(equity).astype(float).dropna()
    return series[~series.index.duplicated(keep="last")].sort_index()


def returns_series(equity: pd.Series) -> pd.Series:
    """Bar-over-bar simple returns."""
    return _clean(equity).pct_change().fillna(0.0)


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Drawdown from the running all-time high, as a negative fraction."""
    series = _clean(equity)
    peak = series.cummax()
    return (series / peak.replace(0.0, np.nan) - 1.0).fillna(0.0)


def max_drawdown(equity: pd.Series) -> float:
    dd = drawdown_series(equity)
    return float(dd.min()) if len(dd) else 0.0


def _years(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 0.0
    return max((index[-1] - index[0]).days / 365.25, 1e-9)


def cagr(equity: pd.Series) -> float:
    series = _clean(equity)
    if len(series) < 2 or series.iloc[0] <= 0:
        return 0.0
    years = _years(series.index)
    if years <= 0:
        return 0.0
    growth = series.iloc[-1] / series.iloc[0]
    if growth <= 0:
        return -1.0
    return float(growth ** (1.0 / years) - 1.0)


def sharpe(equity: pd.Series, periods_per_year: int = _TRADING_DAYS,
           risk_free_rate: float = 0.0) -> float:
    rets = returns_series(equity)
    if len(rets) < 2:
        return 0.0
    excess = rets - (risk_free_rate / periods_per_year)
    std = excess.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def sortino(equity: pd.Series, periods_per_year: int = _TRADING_DAYS,
            risk_free_rate: float = 0.0) -> float:
    rets = returns_series(equity)
    if len(rets) < 2:
        return 0.0
    excess = rets - (risk_free_rate / periods_per_year)
    downside = excess[excess < 0]
    dd_std = np.sqrt((downside ** 2).sum() / len(excess)) if len(downside) else 0.0
    if dd_std == 0 or not np.isfinite(dd_std):
        return 0.0
    return float(excess.mean() / dd_std * np.sqrt(periods_per_year))


def volatility(equity: pd.Series, periods_per_year: int = _TRADING_DAYS) -> float:
    rets = returns_series(equity)
    if len(rets) < 2:
        return 0.0
    return float(rets.std(ddof=1) * np.sqrt(periods_per_year))


def ulcer_index(equity: pd.Series) -> float:
    dd = drawdown_series(equity) * 100.0
    if not len(dd):
        return 0.0
    return float(np.sqrt((dd ** 2).mean()))


def drawdown_details(equity: pd.Series) -> dict:
    """Depth, dates and duration of the worst drawdown."""
    series = _clean(equity)
    if len(series) < 2:
        return {"max_drawdown": 0.0, "peak_date": None, "trough_date": None,
                "recovery_date": None, "drawdown_days": 0, "recovery_days": None,
                "longest_drawdown_days": 0}
    dd = drawdown_series(series)
    trough = dd.idxmin()
    peak = series.loc[:trough].idxmax()
    after = series.loc[trough:]
    peak_value = series.loc[peak]
    recovered = after[after >= peak_value]
    recovery = recovered.index[0] if len(recovered) else None

    underwater = dd < -1e-12
    longest, run_start = 0, None
    for stamp, wet in underwater.items():
        if wet and run_start is None:
            run_start = stamp
        elif not wet and run_start is not None:
            longest = max(longest, (stamp - run_start).days)
            run_start = None
    if run_start is not None:
        longest = max(longest, (underwater.index[-1] - run_start).days)

    return {
        "max_drawdown": float(dd.min()),
        "peak_date": str(pd.Timestamp(peak).date()),
        "trough_date": str(pd.Timestamp(trough).date()),
        "recovery_date": str(pd.Timestamp(recovery).date()) if recovery is not None else None,
        "drawdown_days": int((trough - peak).days),
        "recovery_days": int((recovery - trough).days) if recovery is not None else None,
        "longest_drawdown_days": int(longest),
    }


def monthly_table(equity: pd.Series, benchmark: pd.Series | None = None,
                  trades: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per calendar month: return, both drawdown flavours, equity."""
    series = _clean(equity)
    if series.empty:
        return pd.DataFrame()

    running_peak = series.cummax()
    dd_from_ath = series / running_peak.replace(0.0, np.nan) - 1.0
    keys = series.index.to_period("M")

    rows = []
    prev_close = float(series.iloc[0])
    first_month = True
    for month, chunk in series.groupby(keys):
        start_equity = float(chunk.iloc[0]) if first_month else prev_close
        end_equity = float(chunk.iloc[-1])
        month_peak = chunk.cummax()
        month_dd = float((chunk / month_peak.replace(0.0, np.nan) - 1.0).min())
        row = {
            "start_equity": start_equity,
            "end_equity": end_equity,
            "return_pct": (end_equity / start_equity - 1.0) * 100.0 if start_equity else np.nan,
            "month_dd_pct": month_dd * 100.0,
            "dd_from_peak_pct": float(dd_from_ath.loc[chunk.index].min()) * 100.0,
            "dd_end_pct": float(dd_from_ath.loc[chunk.index[-1]]) * 100.0,
        }
        if benchmark is not None and len(benchmark):
            bench = _clean(benchmark).reindex(series.index).ffill()
            bench_chunk = bench.loc[chunk.index].dropna()
            if len(bench_chunk):
                b_start = float(bench.loc[:chunk.index[0]].iloc[-2]) if (
                    not first_month and len(bench.loc[:chunk.index[0]]) >= 2
                ) else float(bench_chunk.iloc[0])
                row["benchmark_return_pct"] = (
                    (float(bench_chunk.iloc[-1]) / b_start - 1.0) * 100.0 if b_start else np.nan
                )
        if trades is not None and len(trades) and "exit_date" in trades.columns:
            exits = pd.to_datetime(trades["exit_date"], errors="coerce").dt.to_period("M")
            month_trades = trades[exits == month]
            row["trades"] = int(len(month_trades))
            row["trade_pnl"] = float(month_trades["pnl"].sum()) if len(month_trades) else 0.0
        rows.append((str(month), row))
        prev_close = end_equity
        first_month = False

    frame = pd.DataFrame([r for _, r in rows], index=[m for m, _ in rows])
    frame.index.name = "month"
    return frame


def period_table(equity: pd.Series, freq: str = "Y") -> pd.DataFrame:
    """Same idea as :func:`monthly_table`, at an arbitrary frequency ("Y", "Q")."""
    series = _clean(equity)
    if series.empty:
        return pd.DataFrame()
    keys = series.index.to_period(freq)
    dd_ath = drawdown_series(series)
    rows = []
    prev_close = float(series.iloc[0])
    first = True
    for period, chunk in series.groupby(keys):
        start_equity = float(chunk.iloc[0]) if first else prev_close
        end_equity = float(chunk.iloc[-1])
        peak = chunk.cummax()
        rows.append((str(period), {
            "return_pct": (end_equity / start_equity - 1.0) * 100.0 if start_equity else np.nan,
            "max_dd_pct": float((chunk / peak.replace(0.0, np.nan) - 1.0).min()) * 100.0,
            "dd_from_peak_pct": float(dd_ath.loc[chunk.index].min()) * 100.0,
            "end_equity": end_equity,
        }))
        prev_close, first = end_equity, False
    frame = pd.DataFrame([r for _, r in rows], index=[p for p, _ in rows])
    frame.index.name = "period"
    return frame


def _trade_stats(trades: pd.DataFrame | None) -> dict:
    empty = {
        "trades": 0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "profit_factor": 0.0, "expectancy": 0.0, "payoff_ratio": 0.0,
        "largest_win": 0.0, "largest_loss": 0.0, "avg_bars_held": 0.0,
        "max_consecutive_wins": 0, "max_consecutive_losses": 0,
        "gross_profit": 0.0, "gross_loss": 0.0, "avg_trade_return_pct": 0.0,
        "avg_mae_pct": 0.0, "avg_mfe_pct": 0.0,
    }
    if trades is None or len(trades) == 0:
        return empty
    pnl = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0.0)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gross_profit, gross_loss = float(wins.sum()), float(-losses.sum())
    streak = best_win = best_loss = 0
    for value in pnl:
        if value > 0:
            streak = streak + 1 if streak > 0 else 1
            best_win = max(best_win, streak)
        elif value < 0:
            streak = streak - 1 if streak < 0 else -1
            best_loss = max(best_loss, -streak)
        else:
            streak = 0
    return {
        "trades": int(len(pnl)),
        "win_rate": float(len(wins) / len(pnl)) if len(pnl) else 0.0,
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else (
            float("inf") if gross_profit > 0 else 0.0),
        "expectancy": float(pnl.mean()),
        "payoff_ratio": float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else 0.0,
        "largest_win": float(pnl.max()),
        "largest_loss": float(pnl.min()),
        "avg_bars_held": float(pd.to_numeric(trades.get("bars_held", 0), errors="coerce").fillna(0).mean()),
        "max_consecutive_wins": int(best_win),
        "max_consecutive_losses": int(best_loss),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "avg_trade_return_pct": float(pd.to_numeric(trades.get("return_pct", 0), errors="coerce").fillna(0).mean()),
        "avg_mae_pct": float(pd.to_numeric(trades.get("mae_pct", 0), errors="coerce").fillna(0).mean()),
        "avg_mfe_pct": float(pd.to_numeric(trades.get("mfe_pct", 0), errors="coerce").fillna(0).mean()),
    }


def _benchmark_stats(equity: pd.Series, benchmark: pd.Series | None,
                     periods_per_year: int) -> dict:
    if benchmark is None or len(benchmark) < 2:
        return {}
    bench = _clean(benchmark).reindex(_clean(equity).index).ffill().bfill()
    strat_rets = returns_series(equity)
    bench_rets = bench.pct_change().fillna(0.0)
    bench_rets = bench_rets.reindex(strat_rets.index)
    mask = strat_rets.notna() & bench_rets.notna()
    if int(mask.sum()) < 3:
        return {}
    y, x = strat_rets[mask], bench_rets[mask]
    var = float(x.var(ddof=1))
    beta = float(np.cov(y, x, ddof=1)[0, 1] / var) if var > 0 else 0.0
    active = y - x
    tracking = float(active.std(ddof=1) * np.sqrt(periods_per_year))
    return {
        "benchmark_total_return": float(bench.iloc[-1] / bench.iloc[0] - 1.0),
        "benchmark_cagr": cagr(bench),
        "benchmark_max_drawdown": max_drawdown(bench),
        "benchmark_sharpe": sharpe(bench, periods_per_year),
        "alpha_annual": cagr(equity) - cagr(bench),
        "beta": beta,
        "correlation": float(y.corr(x)) if y.std() and x.std() else 0.0,
        "tracking_error": tracking,
        "information_ratio": float(active.mean() * periods_per_year / tracking) if tracking > 0 else 0.0,
    }


def compute_metrics(equity: pd.Series, trades: pd.DataFrame | None = None,
                    periods_per_year: int = _TRADING_DAYS, risk_free_rate: float = 0.0,
                    exposure: pd.Series | None = None,
                    benchmark: pd.Series | None = None) -> dict:
    """The full statistics block used by the CLI table, HTML report and JSON."""
    series = _clean(equity)
    if series.empty:
        return {}
    rets = returns_series(series)
    monthly = monthly_table(series)
    month_rets = monthly["return_pct"] / 100.0 if len(monthly) else pd.Series(dtype=float)
    details = drawdown_details(series)
    max_dd = details["max_drawdown"]
    annual = cagr(series)

    metrics = {
        "start": str(series.index[0].date()),
        "end": str(series.index[-1].date()),
        "years": round(_years(series.index), 2),
        "bars": int(len(series)),
        "initial_equity": float(series.iloc[0]),
        "final_equity": float(series.iloc[-1]),
        "total_return": float(series.iloc[-1] / series.iloc[0] - 1.0) if series.iloc[0] else 0.0,
        "cagr": annual,
        "volatility": volatility(series, periods_per_year),
        "sharpe": sharpe(series, periods_per_year, risk_free_rate),
        "sortino": sortino(series, periods_per_year, risk_free_rate),
        "calmar": float(annual / abs(max_dd)) if max_dd < 0 else 0.0,
        "max_drawdown": max_dd,
        "avg_drawdown": float(drawdown_series(series)[drawdown_series(series) < 0].mean() or 0.0),
        "ulcer_index": ulcer_index(series),
        "best_day": float(rets.max()) if len(rets) else 0.0,
        "worst_day": float(rets.min()) if len(rets) else 0.0,
        "var_95": float(np.percentile(rets, 5)) if len(rets) > 20 else 0.0,
        "cvar_95": float(rets[rets <= np.percentile(rets, 5)].mean()) if len(rets) > 20 else 0.0,
        "best_month": float(month_rets.max()) if len(month_rets) else 0.0,
        "worst_month": float(month_rets.min()) if len(month_rets) else 0.0,
        "worst_month_drawdown": float(monthly["month_dd_pct"].min() / 100.0) if len(monthly) else 0.0,
        "avg_month_drawdown": float(monthly["month_dd_pct"].mean() / 100.0) if len(monthly) else 0.0,
        "positive_months": int((month_rets > 0).sum()),
        "negative_months": int((month_rets < 0).sum()),
        "monthly_win_rate": float((month_rets > 0).mean()) if len(month_rets) else 0.0,
        "avg_exposure": float(pd.Series(exposure).astype(float).mean()) if exposure is not None and len(exposure) else 0.0,
    }
    metrics.update({k: v for k, v in details.items() if k != "max_drawdown"})
    metrics.update(_trade_stats(trades))
    metrics.update(_benchmark_stats(series, benchmark, periods_per_year))
    return metrics
