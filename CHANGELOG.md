# Changelog

All notable changes to this project will be documented in this file.

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