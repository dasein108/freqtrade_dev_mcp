# Freqtrade Dev MCP

MCP server that exposes [Freqtrade](https://www.freqtrade.io/) strategy development tools (data download, backtesting, hyperopt, result analysis) to LLM clients like Claude Desktop and Claude Code. It ships with a LangGraph agent that uses the same tools to generate, optimize and evaluate strategies on its own.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)](#project-status)

> Independent project, not affiliated with the Freqtrade team. For research and education. Backtest results do not predict live performance. Never trade real funds with a strategy you have not reviewed yourself.

## What's inside

| Component | Path | Purpose |
|-----------|------|---------|
| MCP server | [`src/`](src/) | stdio MCP server with 12 Freqtrade tools |
| Strategy agent | [`strategy_agent/`](strategy_agent/) | LangGraph workflow: idea → code → hyperopt → backtest → analysis → rewrite |
| Examples | [`examples/`](examples/) | Claude Desktop / Claude Code configs, usage scripts |
| Docs | [`docs/`](docs/) | Tool reference, developer guide, agent docs |
| Tests | [`tests/`](tests/) | Unit and integration tests (pytest) |

## MCP tools

| Group | Tool | What it does |
|-------|------|--------------|
| Setup | `create_userdir` | Create a Freqtrade `user_data` directory |
| | `create_config` | Generate a config from a template (`default`, `conservative`, `aggressive`, `advanced`) |
| Strategy | `create_strategy` | Generate a strategy from a template (`basic`, `trend`, `mean_reversion`, `scalping`, `advanced`) |
| | `create_strategy_wireframe` | Generate a minimal skeleton for an LLM to fill in |
| Data & runs | `download_candles` | Download OHLCV data; accepts natural-language ranges (`"last 3 months"`) and `top15` by market cap (CoinGecko) |
| | `backtest_strategy` | Run a backtest, optionally exporting trades and signals |
| | `hyperopt_strategy` | Run hyperparameter optimization |
| Analysis | `extract_backtest_data` | Parse a backtest `.zip` into metrics, trades, per-pair / per-hour stats |
| | `extract_hyperopt_data` | Parse a `.fthypt` file into best params, parameter ranges, convergence |
| | `search_results` | Filter indexed results by profit, drawdown, win rate, trades, dates (SQLite index) |
| | `list_results` / `get_result` | Browse and fetch saved results |

Full parameter reference: [`docs/tools-reference.md`](docs/tools-reference.md).

## Requirements

- Python 3.11+ (required by `freqtrade>=2025.7`)
- A Freqtrade installation with a `user_data/` directory
- `freqtrade` on `PATH` for backtest/hyperopt runs
- For the agent: an API key for one of the supported LLM providers

## Installation

```bash
git clone https://github.com/dasein108/freqtrade_dev_mcp.git
cd freqtrade_dev_mcp

# MCP server only
uv pip install -e .

# MCP server + strategy agent
uv pip install -e ".[agent]"

# Development tools
uv pip install -e ".[agent,dev]"
```

`pip install -r requirements.txt` also works and installs everything, agent included.

## Configuration

The server reads `~/.config/freqtrade-mcp/config.json` if present, then applies environment overrides:

| Variable | Meaning | Default |
|----------|---------|---------|
| `FREQTRADE_MCP_PATH` | Freqtrade root (contains `user_data/`) | `~/freqtrade` |
| `FREQTRADE_MCP_EXCHANGE` | Default exchange | `binance` |
| `FREQTRADE_MCP_COINGECKO_KEY` | CoinGecko API key (optional) | none |
| `FREQTRADE_MCP_LOG_LEVEL` | Log level | `INFO` |

File-writing tools (`create_userdir`, `create_config`, `create_strategy*`) only accept paths inside `FREQTRADE_MCP_PATH`; relative paths resolve against it. New strategies go to `user_data/strategies/` by default, where backtest and hyperopt look for them.

Example config file:

```json
{
  "freqtrade_path": "/path/to/freqtrade",
  "default_exchange": "binance",
  "default_stake_amount": 100.0,
  "default_epochs": 100
}
```

## Connecting an MCP client

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "freqtrade": {
      "command": "/absolute/path/to/python",
      "args": ["/absolute/path/to/freqtrade_dev_mcp/run_server.py"],
      "env": {
        "FREQTRADE_MCP_PATH": "/absolute/path/to/freqtrade"
      }
    }
  }
}
```

Restart Claude Desktop afterwards.

### Claude Code

```bash
claude mcp add freqtrade -e FREQTRADE_MCP_PATH=/absolute/path/to/freqtrade \
  -- /absolute/path/to/python /absolute/path/to/freqtrade_dev_mcp/run_server.py
```

More examples in [`examples/`](examples/).

## Typical workflow

Ask your MCP client in plain language; it maps the request to tool calls like these:

```python
download_candles(pairs=["BTC/USDT", "ETH/USDT"], timeframes=["1h"], date_range="last 6 months")
create_strategy_wireframe(strategy_name="EmaTrend", style="guided",
                          description="EMA crossover trend follower")
backtest_strategy(strategy_name="EmaTrend", pairs=["BTC/USDT", "ETH/USDT"], timerange="last 3 months")
hyperopt_strategy(strategy_name="EmaTrend", pairs=["BTC/USDT", "ETH/USDT"],
                  timerange="last 6 months", epochs=200, spaces="buy sell")
extract_hyperopt_data(hyperopt_path="/path/to/EmaTrend.fthypt", output_format="summary")
search_results(result_type="backtest", min_profit=5, max_drawdown=15, sort_by="profit")
```

To limit overfitting, validate on a time range that hyperopt never saw (walk-forward).

## Strategy agent

The agent runs the full loop without a human in the middle:

```
generate idea → write strategy code → download data → hyperopt → backtest → analyze
      ↑                                                                    │
      └──────────────── rewrite if below profit threshold ─────────────────┘
```

Set up `.env` (see [`.env.example`](.env.example)):

```bash
LLM_MODEL=openai/gpt-4o-mini       # provider/model: openai, anthropic, deepseek, groq, together, ...
LLM_API_KEY=...
# optional
LLM_TEMPERATURE=0.3
MAX_ITERATIONS=3
HYPEROPT_EPOCHS=100
MIN_PROFIT_THRESHOLD=5.0
```

Run it:

```bash
python run_strategy_agent.py \
  --symbols BTC/USDT:USDT ETH/USDT:USDT \
  --timeframes 1h \
  --max-iterations 3 \
  --hyperopt-epochs 100 \
  --min-profit 5.0
```

Details: [`docs/strategy-agent.md`](docs/strategy-agent.md) and [`docs/agent-architecture.md`](docs/agent-architecture.md).

## Project structure

```
freqtrade_dev_mcp/
├── src/                     # MCP server
│   ├── commands/            # One module per tool (BaseCommand subclasses)
│   ├── models/              # Pydantic response models shared with the agent
│   ├── utils/               # Date parsing, CoinGecko, logging helpers
│   ├── config.py            # Config file + env loading
│   └── server.py            # Tool registration and dispatch
├── strategy_agent/          # LangGraph agent
│   ├── nodes/               # data_fetcher, strategy_generator, hyperopt_runner, result_analyzer
│   ├── prompts/             # LLM prompt templates
│   ├── agent.py             # Graph definition
│   ├── mcp_client.py        # stdio MCP client
│   └── llm_client.py        # Multi-provider LLM factory (instructor)
├── tests/                   # unit/ and integration/
├── examples/                # Client configs and scripts
├── scripts/                 # Maintenance scripts
├── docs/                    # Documentation (dev-notes/ = historical fix logs)
├── run_server.py            # MCP server entry point
└── run_strategy_agent.py    # Agent CLI
```

## Development

```bash
make install-dev   # install deps
make test          # pytest
make lint          # ruff
make format        # black + ruff --fix
make type-check    # mypy
```

Server logs go to stderr and `logs/mcp_server_*.log` (falls back to `$TMPDIR/freqtrade_mcp_logs/` if `logs/` is not writable). Agent logs go to `logs/strategy_*.log` (plain text and JSON). `python scripts/check_imports.py` does a quick import sanity check.

## Documentation

- [Tools reference](docs/tools-reference.md): every tool, parameter and response
- [Developer guide](docs/developer-guide.md): architecture, data models, adding tools, testing
- [Strategy agent](docs/strategy-agent.md): agent usage, configuration, workflow
- [Agent architecture](docs/agent-architecture.md): original LangGraph design notes
- [Tests](tests/README.md): how the test suite is organized
- [Changelog](CHANGELOG.md)

## Project status

Alpha. Tool interfaces and response schemas may still change. See [open issues](https://github.com/dasein108/freqtrade_dev_mcp/issues) for known problems.

## Contributing

1. Branch from `dev`.
2. Add tests for new behavior (`pytest`).
3. Run `make lint type-check test`.
4. Open a pull request against `dev`.

Coding conventions live in [`CLAUDE.md`](CLAUDE.md).

## Support

- Bugs, questions and feature requests: [GitHub Issues](https://github.com/dasein108/freqtrade_dev_mcp/issues)

## License

MIT. See [LICENSE](LICENSE).
