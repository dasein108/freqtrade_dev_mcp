# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Security
- File-writing tools are confined to `FREQTRADE_MCP_PATH`; `create_userdir(reset=True)` only deletes an existing Freqtrade user directory (must contain `strategies/`) and never the root
- Strategy names must be valid Python identifiers; result IDs are validated before file lookup (prevents path traversal)
- `extract_hyperopt_data` no longer unpickles legacy `.fthypt` files
- Tool errors no longer return tracebacks or call arguments to the client (still logged server-side)
- Removed hardcoded user-specific paths

### Fixed
- `run_server.py` failed to start (`attempted relative import beyond top-level package`); it now imports `src` as a package
- Server logged to stdout, corrupting the MCP stdio stream; console logging now goes to stderr, log dir is anchored to the project (temp-dir fallback)
- Strategy agent crashed calling the removed `read_candles` tool; it now reads the cache file returned by `download_candles`
- `download_candles` passed no `--datadir` / data format, so freqtrade wrote feather files under `user_data/data/<exchange>/` that were never found; futures file paths corrected
- `create_strategy*` wrote to `./strategies` of the server's working directory instead of the configured strategies directory
- Freqtrade path auto-detection looked for a folder named `freqtrade_mcp`; it now uses the working directory or its parent if it has `user_data/`
- Removed ineffective pydantic `env_prefix`; `run()` no longer wipes the logging handlers set at startup
- `scripts/check_imports.py` and `tests/test_utils.py` imports fixed

### Changed
- Documentation moved into `docs/` (`tools-reference.md`, `developer-guide.md`, `strategy-agent.md`, `agent-architecture.md`); historical fix notes moved to `docs/dev-notes/`
- `test_imports.py` moved to `scripts/check_imports.py`
- README rewritten: accurate tool list, install/config instructions, strategy agent usage
- Project links point to https://github.com/dasein108/freqtrade_dev_mcp; Discord references removed
- `pyproject.toml`: Python >=3.11 (required by freqtrade 2025.7), status Alpha, new `agent` optional-dependency group
- Example client configs point to `run_server.py`
- Code formatted with black (line length 100) and linted clean with ruff; ruff config moved to the `lint` section

### Removed
- Dead `download_candles` package path (imported `download_pair_history` / `get_exchange_class`, neither of which exists in freqtrade 2025.7, so the CLI path always ran)
- Unused `src/utils/logger.py`
- Log files, `__pycache__`, test cache pickles and local Claude settings from version control (now in `.gitignore`)

## [1.0.0] - 2024-08-17

### Added
- Initial release of Freqtrade MCP Server
- Model Context Protocol (MCP) server implementation for Freqtrade
- Natural language date parsing support
- Five core commands: download_candles, backtest_strategy, hyperopt_strategy, list_results, get_result
- CoinGecko integration for top market cap coin selection
- MCP-safe logging with real-time updates in Claude Desktop
- Package-based and CLI-based freqtrade execution modes
- Comprehensive configuration management
- Structured result storage with metadata
- Export functionality for trades and signals

### Features
- **Data Management**: Download historical candle data with natural language dates
- **Backtesting**: Execute strategy backtests with detailed analysis
- **Hyperparameter Optimization**: Optimize strategy parameters across multiple dimensions
- **Natural Language Support**: "last year", "Q1 2024", "march to june", etc.
- **Top Coin Selection**: Automatic selection by market cap using CoinGecko API
- **Result Management**: Store, retrieve, and analyze backtest/hyperopt results
- **MCP Integration**: Real-time logging and status updates

### Technical Details
- Python 3.8+ support
- Freqtrade package integration with CLI fallback
- Async/await architecture for better performance
- Comprehensive error handling and logging
- Type hints and proper documentation
- Test suite with pytest
- Code quality tools (ruff, black, mypy)

### Documentation
- Complete README with quick start guide
- Configuration examples for Claude Desktop and Claude Code
- API documentation for all commands
- Troubleshooting guide
- Development setup instructions