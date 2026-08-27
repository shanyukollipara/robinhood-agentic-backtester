# rhbt - Robinhood Agentic Backtester

Read [AGENTS.md](AGENTS.md) before doing anything in this repo. It is the
complete operating manual for AI agents: how to set the project up, how to get
price data (via the Robinhood Trading MCP or the yfinance fallback), how to
translate a user's plain-English strategy into a spec file, how to run it, and
how to report the results honestly.

Quick reference:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[data]"
.venv/bin/rhbt schema            # the strategy spec format, as JSON
.venv/bin/rhbt indicators        # every function usable in a rule
.venv/bin/rhbt run strategies/my_strategy.yaml
```

Never place real trades from this repo. It backtests only.
