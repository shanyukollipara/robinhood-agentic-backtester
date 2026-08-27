"""Equal-weight buy and hold - the baseline every strategy should beat."""

from ..strategy import Strategy


class BuyAndHold(Strategy):
    name = "Buy and hold"
    description = "Buys an equal-weight basket on the first bar and never trades again."

    def on_bar(self, ctx):
        if ctx.i != 0:
            return
        tradable = [s for s in ctx.symbols if ctx.has_data(s)]
        if not tradable:
            return
        for symbol in tradable:
            ctx.order_target_percent(symbol, 1.0 / len(tradable), reason="initial_buy")
