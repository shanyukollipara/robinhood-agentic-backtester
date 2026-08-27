"""Buy oversold dips, sell back into strength."""

from ..indicators import rsi, sma
from ..strategy import Strategy


class RsiMeanReversion(Strategy):
    name = "RSI mean reversion"
    description = "Buys when RSI drops below the entry level while price is above its long trend filter."
    params = {"rsi_window": 2, "entry_level": 10, "exit_level": 60, "trend_window": 200}

    def on_start(self, ctx):
        self._rsi, self._trend = {}, {}
        for symbol in ctx.symbols:
            closes = ctx._engine.frames[symbol]["close"]
            self._rsi[symbol] = rsi(closes, self.params["rsi_window"])
            self._trend[symbol] = sma(closes, self.params["trend_window"])

    def on_bar(self, ctx):
        weight = 1.0 / max(len(ctx.symbols), 1)
        for symbol in ctx.symbols:
            value = self._rsi[symbol].iat[ctx.i]
            trend = self._trend[symbol].iat[ctx.i]
            price = ctx.price(symbol)
            if value != value or price != price:
                continue
            above_trend = trend != trend or price > trend
            if ctx.is_flat(symbol) and value < self.params["entry_level"] and above_trend:
                ctx.order_target_percent(symbol, weight, reason="oversold")
            elif ctx.is_long(symbol) and value > self.params["exit_level"]:
                ctx.close(symbol, reason="rsi_recovered")
