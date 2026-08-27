"""rhbt - the Robinhood Agentic Backtester.

Describe a trading strategy to your AI agent, let it write a spec against this
repo, run it locally, and get monthly drawdowns plus a full tearsheet.
"""

from .engine import Backtest, BacktestResult, RunConfig
from .portfolio import Costs, Portfolio, Position, Trade
from .runner import run_backtest, run_spec, run_spec_file
from .spec import Spec, SpecError, SpecStrategy
from .strategy import Context, Strategy

__version__ = "0.1.0"

__all__ = [
    "Backtest", "BacktestResult", "RunConfig", "Costs", "Portfolio", "Position",
    "Trade", "Spec", "SpecError", "SpecStrategy", "Strategy", "Context",
    "run_backtest", "run_spec", "run_spec_file", "__version__",
]
