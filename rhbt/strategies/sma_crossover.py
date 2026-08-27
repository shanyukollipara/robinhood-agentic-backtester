"""Classic moving-average crossover (the "golden cross")."""

from ..indicators import sma
from ..strategy import Strategy


class SmaCrossover(Strategy):
    name = "SMA crossover"
    description = "Long while the fast moving average is above the slow one."
    params = {"fast": 50, "slow": 200}

    def on_start(self, ctx):
        self._fast, self._slow = {}, {}
        for symbol in ctx.symbols:
            closes = ctx._engine.frames[symbol]["close"]
            self._fast[symbol] = sma(closes, self.params["fast"])
            self._slow[symbol] = sma(closes, self.params["slow"])

    def on_bar(self, ctx):
        weight = 1.0 / max(len(ctx.symbols), 1)
        for symbol in ctx.symbols:
            fast = self._fast[symbol].iat[ctx.i]
            slow = self._slow[symbol].iat[ctx.i]
            if fast != fast or slow != slow:
                continue
            if fast > slow and ctx.is_flat(symbol):
                ctx.order_target_percent(symbol, weight, reason="fast_above_slow")
            elif fast < slow and ctx.is_long(symbol):
                ctx.close(symbol, reason="fast_below_slow")
