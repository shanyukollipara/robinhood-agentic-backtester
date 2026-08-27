"""Self-contained HTML tearsheet: no CDNs, no JS libraries, works offline."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .metrics import drawdown_series, period_table

_CSS = """
:root {
  --bg: #ffffff; --panel: #f7f8fa; --border: #e3e6ea; --text: #14181d;
  --muted: #667085; --accent: #0b8f5a; --accent-soft: #e6f5ee;
  --neg: #c0392b; --neg-soft: #fdecea; --pos: #0b8f5a; --bench: #8a93a3;
  --grid: #eceff3;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e1116; --panel: #161b22; --border: #262c36; --text: #e6edf3;
    --muted: #8b949e; --accent: #3fb950; --accent-soft: #10261a;
    --neg: #f85149; --neg-soft: #2a1414; --pos: #3fb950; --bench: #6e7681;
    --grid: #1e242c;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 32px 20px 80px; }
h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.02em; }
h2 { font-size: 17px; margin: 40px 0 12px; letter-spacing: -0.01em; }
.sub { color: var(--muted); font-size: 14px; margin: 0 0 6px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0 0; }
.tag { background: var(--panel); border: 1px solid var(--border); border-radius: 999px;
  padding: 3px 10px; font-size: 12px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 22px; }
.kpi { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.kpi .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi .value { font-size: 21px; font-weight: 600; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi .note { color: var(--muted); font-size: 11px; margin-top: 2px; }
.pos { color: var(--pos); } .neg { color: var(--neg); }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 6px 9px; border-bottom: 1px solid var(--border); white-space: nowrap; }
th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.05em; position: sticky; top: 0; background: var(--panel); }
td:first-child, th:first-child { text-align: left; }
tbody tr:hover { background: var(--bg); }
.scroll { max-height: 460px; overflow-y: auto; }
.legend { display: flex; gap: 16px; font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
.heat td { text-align: center; font-size: 12px; padding: 5px 6px; border: 1px solid var(--border); }
.foot { color: var(--muted); font-size: 12px; margin-top: 44px; border-top: 1px solid var(--border); padding-top: 16px; }
.foot code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
details { margin-top: 10px; } summary { cursor: pointer; color: var(--muted); font-size: 13px; }
pre { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 12px;
  overflow-x: auto; font-size: 12px; }
svg { display: block; width: 100%; height: auto; }
"""


def _fmt_pct(value, digits: int = 2, sign: bool = False) -> str:
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "-"
    prefix = "+" if sign and value > 0 else ""
    return f"{prefix}{value * 100:.{digits}f}%"


def _fmt_num(value, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "-"
    return f"{value:,.{digits}f}"


def _fmt_money(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    return f"${value:,.2f}"


def _cls(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return "pos" if value > 0 else ("neg" if value < 0 else "")


# ----------------------------------------------------------------- charting
def _epoch(index) -> np.ndarray:
    """Seconds since the epoch, independent of the index's datetime unit."""
    return pd.DatetimeIndex(index).to_numpy(dtype="datetime64[s]").astype("int64")


def _path(series: pd.Series, x0, x1, y0, y1, lo, hi, width, height, pad_l, pad_t) -> str:
    span = (hi - lo) or 1.0
    xspan = (x1 - x0) or 1
    points = []
    for stamp, value in series.items():
        if value != value:
            continue
        px = pad_l + (stamp - x0) / xspan * width
        py = pad_t + (1 - (value - lo) / span) * height
        points.append(f"{px:.2f},{py:.2f}")
    return "M" + " L".join(points) if points else ""


def _line_chart(series_map: dict[str, tuple[pd.Series, str]], height: int = 240,
                fill_first: bool = False, log: bool = False, zero_line: bool = False) -> str:
    valid = {k: v for k, v in series_map.items() if v[0] is not None and len(v[0].dropna()) > 1}
    if not valid:
        return "<p class='sub'>not enough data to chart</p>"
    width, pad_l, pad_r, pad_t, pad_b = 1000, 62, 12, 12, 26
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b

    prepared = {}
    for label, (series, color) in valid.items():
        s = series.dropna()
        if log:
            s = s[s > 0]
            s = np.log10(s)
        prepared[label] = (s, color)

    all_values = pd.concat([s for s, _ in prepared.values()])
    lo, hi = float(all_values.min()), float(all_values.max())
    if zero_line:
        hi = max(hi, 0.0)
    pad = (hi - lo) * 0.06 or abs(hi) * 0.06 or 1.0
    lo, hi = lo - pad, hi + pad

    index = pd.DatetimeIndex(
        np.unique(np.concatenate([pd.DatetimeIndex(s.index).to_numpy() for s, _ in prepared.values()]))
    )
    x0, x1 = int(_epoch(index).min()), int(_epoch(index).max())

    parts = [f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img">']
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + frac * plot_h
        value = hi - frac * (hi - lo)
        shown = (10 ** value) if log else value
        label = f"{shown:,.0f}" if abs(shown) >= 10 else f"{shown:,.2f}"
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)">{label}</text>')

    for i, (label, (series, color)) in enumerate(prepared.items()):
        d = _path(pd.Series(series.to_numpy(), index=_epoch(series.index)),
                  x0, x1, 0, 0, lo, hi, plot_w, plot_h, pad_l, pad_t)
        if not d:
            continue
        if fill_first and i == 0:
            base = pad_t + plot_h
            parts.append(f'<path d="{d} L{pad_l + plot_w:.2f},{base:.2f} L{pad_l:.2f},{base:.2f} Z" fill="{color}" opacity="0.10"/>')
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>')

    ticks = index
    n_ticks = min(6, len(ticks))
    for k in range(n_ticks):
        stamp = ticks[int(k * (len(ticks) - 1) / max(n_ticks - 1, 1))]
        px = pad_l + (int(_epoch([stamp])[0]) - x0) / ((x1 - x0) or 1) * plot_w
        parts.append(f'<text x="{px:.1f}" y="{height - 8}" text-anchor="middle" font-size="11" fill="var(--muted)">{stamp.date()}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _underwater_chart(equity: pd.Series, height: int = 170) -> str:
    dd = drawdown_series(equity) * 100.0
    if len(dd) < 2:
        return "<p class='sub'>not enough data to chart</p>"
    width, pad_l, pad_r, pad_t, pad_b = 1000, 62, 12, 12, 26
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    lo, hi = float(dd.min()) * 1.08 - 0.5, 0.0
    epochs = _epoch(dd.index)
    x0, x1 = int(epochs.min()), int(epochs.max())
    d = _path(pd.Series(dd.to_numpy(), index=epochs), x0, x1, 0, 0, lo, hi, plot_w, plot_h, pad_l, pad_t)
    base = pad_t + (1 - (0 - lo) / ((hi - lo) or 1)) * plot_h
    parts = [f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img">']
    for frac in (0, 0.33, 0.66, 1.0):
        y = pad_t + frac * plot_h
        value = hi - frac * (hi - lo)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="var(--grid)"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)">{value:.1f}%</text>')
    parts.append(f'<path d="{d} L{pad_l + plot_w:.2f},{base:.2f} L{pad_l:.2f},{base:.2f} Z" fill="var(--neg)" opacity="0.16"/>')
    parts.append(f'<path d="{d}" fill="none" stroke="var(--neg)" stroke-width="1.5"/>')
    parts.append("</svg>")
    return "".join(parts)


_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _heatmap(monthly: pd.DataFrame, column: str = "return_pct") -> str:
    if monthly.empty:
        return ""
    values = monthly[column]
    scale = max(abs(values.min()), abs(values.max()), 1e-9)
    grid: dict[int, dict[int, float]] = {}
    for key, value in values.items():
        year, month = int(str(key)[:4]), int(str(key)[5:7])
        grid.setdefault(year, {})[month] = float(value)

    head = "".join(f"<th>{name}</th>" for name in _MONTH_NAMES)
    rows = []
    for year in sorted(grid):
        cells = []
        for month in range(1, 13):
            value = grid[year].get(month)
            if value is None:
                cells.append("<td style='opacity:.25'>-</td>")
                continue
            alpha = min(abs(value) / scale, 1.0) * 0.72
            color = "var(--pos)" if value > 0 else "var(--neg)"
            style = f"background: color-mix(in srgb, {color} {alpha * 100:.0f}%, transparent);"
            cells.append(f"<td style=\"{style}\">{value:+.1f}</td>")
        total = sum(grid[year].values())
        rows.append(f"<tr><td class='mono'>{year}</td>{''.join(cells)}"
                    f"<td class='{_cls(total)}'><b>{total:+.1f}</b></td></tr>")
    return (f"<div class='card'><table class='heat'><thead><tr><th>Year</th>{head}<th>Sum</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>")


# ------------------------------------------------------------------ tables
def _monthly_table_html(monthly: pd.DataFrame, has_benchmark: bool) -> str:
    if monthly.empty:
        return "<p class='sub'>no monthly data</p>"
    columns = [
        ("Month", lambda idx, row: f"<span class='mono'>{idx}</span>"),
        ("Return", lambda idx, row: f"<span class='{_cls(row['return_pct'])}'>{row['return_pct']:+.2f}%</span>"),
        ("Max DD in mo", lambda idx, row: f"<span class='neg'>{row['month_dd_pct']:.2f}%</span>" if row["month_dd_pct"] < 0 else "0.00%"),
        ("DD vs ATH", lambda idx, row: f"<span class='neg'>{row['dd_from_peak_pct']:.2f}%</span>" if row["dd_from_peak_pct"] < -0.005 else "0.00%"),
        ("DD at end", lambda idx, row: f"{row['dd_end_pct']:.2f}%"),
        ("End equity", lambda idx, row: _fmt_money(row["end_equity"])),
    ]
    if has_benchmark and "benchmark_return_pct" in monthly.columns:
        columns.insert(2, ("Bench", lambda idx, row: f"<span class='{_cls(row.get('benchmark_return_pct'))}'>{row['benchmark_return_pct']:+.2f}%</span>"))
    if "trades" in monthly.columns:
        columns.append(("Trades", lambda idx, row: f"{int(row['trades'])}"))

    head = "".join(f"<th>{html.escape(name)}</th>" for name, _ in columns)
    body = []
    for idx, row in monthly.iterrows():
        cells = "".join(f"<td>{fn(idx, row)}</td>" for _, fn in columns)
        body.append(f"<tr>{cells}</tr>")
    return (f"<div class='card scroll'><table><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table></div>")


def _yearly_table_html(equity: pd.Series) -> str:
    table = period_table(equity, "Y")
    if table.empty:
        return ""
    rows = "".join(
        f"<tr><td class='mono'>{idx}</td>"
        f"<td class='{_cls(row['return_pct'])}'>{row['return_pct']:+.2f}%</td>"
        f"<td class='neg'>{row['max_dd_pct']:.2f}%</td>"
        f"<td>{_fmt_money(row['end_equity'])}</td></tr>"
        for idx, row in table.iterrows()
    )
    return ("<div class='card'><table><thead><tr><th>Year</th><th>Return</th>"
            "<th>Max drawdown</th><th>End equity</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>")


def _trades_table_html(trades: pd.DataFrame, limit: int = 500) -> str:
    if trades is None or len(trades) == 0:
        return "<p class='sub'>This strategy never opened a position. Check that the entry rule can actually fire over this date range.</p>"
    shown = trades.tail(limit)
    head = ("<tr><th>#</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Entry px</th>"
            "<th>Exit</th><th>Exit px</th><th>Qty</th><th>P&amp;L</th><th>Return</th>"
            "<th>Bars</th><th>MAE</th><th>Exit reason</th></tr>")
    rows = []
    offset = len(trades) - len(shown)
    for i, (_, t) in enumerate(shown.iterrows(), start=offset + 1):
        rows.append(
            f"<tr><td>{i}</td><td class='mono'>{html.escape(str(t['symbol']))}</td>"
            f"<td>{html.escape(str(t['side']))}</td><td class='mono'>{t['entry_date']}</td>"
            f"<td>{_fmt_num(t['entry_price'])}</td><td class='mono'>{t['exit_date']}</td>"
            f"<td>{_fmt_num(t['exit_price'])}</td><td>{_fmt_num(t['qty'], 4)}</td>"
            f"<td class='{_cls(t['pnl'])}'>{_fmt_money(t['pnl'])}</td>"
            f"<td class='{_cls(t['return_pct'])}'>{t['return_pct']:+.2f}%</td>"
            f"<td>{int(t['bars_held'])}</td><td class='neg'>{t['mae_pct']:.2f}%</td>"
            f"<td>{html.escape(str(t['exit_reason']))}</td></tr>"
        )
    note = f"<p class='sub'>Showing the last {limit} of {len(trades)} trades.</p>" if len(trades) > limit else ""
    return (f"{note}<div class='card scroll'><table><thead>{head}</thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>")


def _kpis(result) -> str:
    m = result.metrics
    items = [
        ("Total return", _fmt_pct(m.get("total_return"), 2, True), _cls(m.get("total_return")),
         f"{_fmt_money(m.get('initial_equity'))} &rarr; {_fmt_money(m.get('final_equity'))}"),
        ("CAGR", _fmt_pct(m.get("cagr"), 2, True), _cls(m.get("cagr")), f"over {m.get('years', 0)} years"),
        ("Max drawdown", _fmt_pct(m.get("max_drawdown"), 2), "neg",
         f"{m.get('trough_date') or '-'} &middot; {m.get('longest_drawdown_days', 0)}d underwater"),
        ("Worst month", _fmt_pct(m.get("worst_month"), 2, True), "neg",
         f"worst in-month DD {_fmt_pct(m.get('worst_month_drawdown'), 2)}"),
        ("Sharpe", _fmt_num(m.get("sharpe")), "", f"sortino {_fmt_num(m.get('sortino'))}"),
        ("Calmar", _fmt_num(m.get("calmar")), "", f"vol {_fmt_pct(m.get('volatility'), 1)}"),
        ("Win rate", _fmt_pct(m.get("win_rate"), 1), "", f"{m.get('trades', 0)} trades"),
        ("Profit factor", _fmt_num(m.get("profit_factor")), "",
         f"expectancy {_fmt_money(m.get('expectancy'))}/trade"),
        ("Monthly win rate", _fmt_pct(m.get("monthly_win_rate"), 1), "",
         f"{m.get('positive_months', 0)} up / {m.get('negative_months', 0)} down"),
        ("Avg exposure", _fmt_pct(m.get("avg_exposure"), 1), "",
         f"cost of trading {_fmt_money(result.meta.get('slippage_cost', 0) + result.meta.get('fees_paid', 0))}"),
    ]
    if "benchmark_total_return" in m:
        items.append((f"vs {result.benchmark_symbol}", _fmt_pct(m.get("alpha_annual"), 2, True),
                      _cls(m.get("alpha_annual")),
                      f"bench {_fmt_pct(m.get('benchmark_total_return'), 1, True)} &middot; beta {_fmt_num(m.get('beta'))}"))
    cells = "".join(
        f"<div class='kpi'><div class='label'>{html.escape(label)}</div>"
        f"<div class='value {cls}'>{value}</div><div class='note'>{note}</div></div>"
        for label, value, cls, note in items
    )
    return f"<div class='kpis'>{cells}</div>"


def _stats_table(result) -> str:
    m = result.metrics
    groups = [
        ("Returns", [
            ("Total return", _fmt_pct(m.get("total_return"), 2, True)),
            ("CAGR", _fmt_pct(m.get("cagr"), 2, True)),
            ("Best month", _fmt_pct(m.get("best_month"), 2, True)),
            ("Worst month", _fmt_pct(m.get("worst_month"), 2, True)),
            ("Best bar", _fmt_pct(m.get("best_day"), 2, True)),
            ("Worst bar", _fmt_pct(m.get("worst_day"), 2, True)),
        ]),
        ("Risk", [
            ("Max drawdown", _fmt_pct(m.get("max_drawdown"), 2)),
            ("Avg drawdown", _fmt_pct(m.get("avg_drawdown"), 2)),
            ("Worst in-month drawdown", _fmt_pct(m.get("worst_month_drawdown"), 2)),
            ("Avg in-month drawdown", _fmt_pct(m.get("avg_month_drawdown"), 2)),
            ("Longest drawdown", f"{m.get('longest_drawdown_days', 0)} days"),
            ("Recovery from worst DD", f"{m.get('recovery_days')} days" if m.get("recovery_days") is not None else "not recovered"),
            ("Annualised volatility", _fmt_pct(m.get("volatility"), 2)),
            ("Ulcer index", _fmt_num(m.get("ulcer_index"))),
            ("Daily VaR 95%", _fmt_pct(m.get("var_95"), 2)),
            ("Daily CVaR 95%", _fmt_pct(m.get("cvar_95"), 2)),
        ]),
        ("Risk-adjusted", [
            ("Sharpe", _fmt_num(m.get("sharpe"))),
            ("Sortino", _fmt_num(m.get("sortino"))),
            ("Calmar", _fmt_num(m.get("calmar"))),
            ("Beta", _fmt_num(m.get("beta")) if "beta" in m else "-"),
            ("Alpha (annual)", _fmt_pct(m.get("alpha_annual"), 2, True) if "alpha_annual" in m else "-"),
            ("Information ratio", _fmt_num(m.get("information_ratio")) if "information_ratio" in m else "-"),
        ]),
        ("Trades", [
            ("Round trips", str(m.get("trades", 0))),
            ("Win rate", _fmt_pct(m.get("win_rate"), 1)),
            ("Avg win", _fmt_money(m.get("avg_win"))),
            ("Avg loss", _fmt_money(m.get("avg_loss"))),
            ("Payoff ratio", _fmt_num(m.get("payoff_ratio"))),
            ("Profit factor", _fmt_num(m.get("profit_factor"))),
            ("Expectancy / trade", _fmt_money(m.get("expectancy"))),
            ("Largest win", _fmt_money(m.get("largest_win"))),
            ("Largest loss", _fmt_money(m.get("largest_loss"))),
            ("Avg bars held", _fmt_num(m.get("avg_bars_held"), 1)),
            ("Max consecutive wins", str(m.get("max_consecutive_wins", 0))),
            ("Max consecutive losses", str(m.get("max_consecutive_losses", 0))),
            ("Avg MAE / MFE", f"{_fmt_num(m.get('avg_mae_pct'))}% / {_fmt_num(m.get('avg_mfe_pct'))}%"),
        ]),
    ]
    blocks = []
    for title, rows in groups:
        body = "".join(f"<tr><td>{html.escape(label)}</td><td>{value}</td></tr>" for label, value in rows)
        blocks.append(f"<div class='card'><table><thead><tr><th>{title}</th><th></th></tr></thead><tbody>{body}</tbody></table></div>")
    return ("<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px'>"
            + "".join(blocks) + "</div>")


def render_html(result, title: str | None = None, spec: dict | None = None) -> str:
    """Build the full tearsheet as one HTML string."""
    m = result.metrics
    name = title or result.strategy_name
    monthly = result.monthly

    series_map = {"Strategy": (result.equity, "var(--accent)")}
    if result.benchmark is not None:
        series_map[f"{result.benchmark_symbol} buy & hold"] = (result.benchmark, "var(--bench)")

    legend = "".join(
        f"<span><span class='swatch' style='background:{color}'></span>{html.escape(label)}</span>"
        for label, (_, color) in series_map.items()
    )
    tags = "".join(
        f"<span class='tag'>{html.escape(str(text))}</span>" for text in [
            f"symbols: {', '.join(result.symbols)}",
            f"{m.get('start')} to {m.get('end')}",
            f"{result.meta.get('bars', 0)} bars",
            f"fill: {result.meta.get('fill_model')}",
            f"interval: {result.meta.get('interval')}",
        ] + [f"{k}={v}" for k, v in (result.params or {}).items()]
    )

    spec_block = ""
    if spec:
        spec_block = ("<details><summary>Strategy spec used for this run</summary>"
                      f"<pre>{html.escape(json.dumps(spec, indent=2, default=str))}</pre></details>")

    logs_block = ""
    if result.logs:
        rows = "".join(
            f"<tr><td class='mono'>{pd.Timestamp(stamp).date()}</td><td style='text-align:left'>{html.escape(msg)}</td></tr>"
            for stamp, msg in result.logs[-300:]
        )
        logs_block = ("<h2>Strategy log</h2><div class='card scroll'><table><thead><tr><th>Date</th>"
                      f"<th style='text-align:left'>Message</th></tr></thead><tbody>{rows}</tbody></table></div>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(name)} - rhbt backtest</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
  <h1>{html.escape(name)}</h1>
  <p class="sub">{html.escape(result.description if hasattr(result, 'description') else '')}</p>
  <p class="sub">Backtest generated by <span class="mono">rhbt</span> on {datetime.now():%Y-%m-%d %H:%M}</p>
  <div class="tags">{tags}</div>
  {_kpis(result)}

  <h2>Equity curve</h2>
  <div class="card"><div class="legend">{legend}</div>{_line_chart(series_map, 260, fill_first=True)}</div>

  <h2>Drawdown (underwater)</h2>
  <div class="card">{_underwater_chart(result.equity)}</div>

  <h2>Monthly returns (%)</h2>
  {_heatmap(monthly)}

  <h2>Month-by-month detail</h2>
  <p class="sub"><b>Max DD in month</b> is the worst peak-to-trough fall inside that month.
  <b>DD vs all-time high</b> measures the same month against the highest equity ever reached.</p>
  {_monthly_table_html(monthly, result.benchmark is not None)}

  <h2>Yearly summary</h2>
  {_yearly_table_html(result.equity)}

  <h2>All statistics</h2>
  {_stats_table(result)}

  <h2>Trade log</h2>
  {_trades_table_html(result.trades)}
  {logs_block}

  <div class="foot">
    <p><b>How to read this.</b> Orders signalled on a bar are filled at the
    <span class="mono">{result.meta.get('fill_model')}</span> price, so no decision uses information it
    could not have had. Slippage of {result.config.costs.slippage_bps:g} bps always works against the fill,
    plus {result.config.costs.commission_bps:g} bps commission. Across
    {result.meta.get('fills', 0)} fills that cost {_fmt_money(result.meta.get('slippage_cost', 0))} in slippage
    and {_fmt_money(result.meta.get('fees_paid', 0))} in commissions.</p>
    <p><b>What this is not.</b> A backtest is a simulation on historical prices. It ignores dividends unless
    your data is adjusted for them, assumes every order fills at the modelled price, and cannot know about
    borrow costs, halts, or your own behaviour in a drawdown. Past results do not predict future returns.
    This is software for research, not investment advice.</p>
    {spec_block}
  </div>
</div></body></html>"""


def write_report(result, path: str | Path, title: str | None = None,
                 spec: dict | None = None) -> Path:
    """Render the tearsheet and write it to ``path``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(result, title=title, spec=spec), encoding="utf-8")
    return path
