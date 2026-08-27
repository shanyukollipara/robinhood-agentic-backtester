"""Reference strategies. Copy one as a starting point for your own."""

from .buy_and_hold import BuyAndHold
from .sma_crossover import SmaCrossover
from .rsi_mean_reversion import RsiMeanReversion

BUILTIN = {
    "buy_and_hold": BuyAndHold,
    "sma_crossover": SmaCrossover,
    "rsi_mean_reversion": RsiMeanReversion,
}

__all__ = ["BuyAndHold", "SmaCrossover", "RsiMeanReversion", "BUILTIN"]
