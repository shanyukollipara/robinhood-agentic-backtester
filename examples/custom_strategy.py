"""A hand-written strategy, for logic that a rule expression cannot express.

Run it with:

    rhbt run --strategy examples/custom_strategy.py --symbols SPY,QQQ --start 2015-01-01

Anything you can compute in Python is fair game here - just never look at
``ctx.history()`` beyond the current bar, which the engine already prevents.
"""

from rhbt import Strategy
from rhbt.indicators import atr, rsi, sma


class VolatilityScaledDipBuyer(Strategy):
    name = "Volatility-scaled dip buyer"
    description = "Buys dips, but sizes the position down when volatility is high."
    params = {"rsi_window": 3, "entry_level": 20, "exit_level": 65,
              "trend_window": 200, "target_vol": 0.15}

    def on_start(self, ctx):
        self.signals = {}
        for symbol in ctx.symbols:
            frame = ctx._engine.frames[symbol]
            close = frame["close"]
            self.signals[symbol] = {
                "rsi": rsi(close, self.params["rsi_window"]),
                "trend": sma(close, self.params["trend_window"]),
                "vol": close.pct_change().rolling(20).std() * (252 ** 0.5),
            }
        ctx.log(f"watching {len(ctx.symbols)} symbols")

    def on_bar(self, ctx):
        for symbol in ctx.symbols:
            series = self.signals[symbol]
            value = series["rsi"].iat[ctx.i]
            trend = series["trend"].iat[ctx.i]
            vol = series["vol"].iat[ctx.i]
            price = ctx.price(symbol)
            if value != value or vol != vol or price != price:
                continue

            if ctx.is_long(symbol):
                if value > self.params["exit_level"]:
                    ctx.close(symbol, reason="rsi_recovered")
                continue

            if value < self.params["entry_level"] and (trend != trend or price > trend):
                # Risk-parity-ish: smaller size when the name is jumpy.
                weight = min(self.params["target_vol"] / max(vol, 1e-6), 1.0) / len(ctx.symbols)
                ctx.order_target_percent(symbol, weight, reason="oversold")
                ctx.set_stop_loss(symbol, 0.10)
                ctx.log(f"{symbol}: RSI {value:.1f}, vol {vol:.1%}, weight {weight:.1%}")
