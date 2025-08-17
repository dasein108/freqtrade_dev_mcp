#!/usr/bin/env python3
"""Main MCP server implementation for Freqtrade."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src directory to path when running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    LoggingLevel,
    LoggingMessageNotification
)

# Use conditional imports to support both module and script execution
try:
    from .config import Config, load_config
    from .commands import (
        DownloadCandlesCommand,
        BacktestStrategyCommand,
        HyperoptStrategyCommand,
        ListResultsCommand,
        GetResultCommand,
        CreateUserdirCommand,
        CreateConfigCommand,
        CreateStrategyCommand,
        CreateStrategyWireframeCommand,
        ExtractBacktestDataCommand,
        ExtractHyperoptDataCommand,
        SearchResultsCommand,
    )
    from .utils.date_parser import parse_natural_date
    from .utils.logger import setup_logging
except ImportError:
    # Absolute imports for direct script execution
    from config import Config, load_config
    from commands import (
        DownloadCandlesCommand,
        BacktestStrategyCommand,
        HyperoptStrategyCommand,
        ListResultsCommand,
        GetResultCommand,
        CreateUserdirCommand,
        CreateConfigCommand,
        CreateStrategyCommand,
        CreateStrategyWireframeCommand,
        ExtractBacktestDataCommand,
        ExtractHyperoptDataCommand,
        SearchResultsCommand,
    )
    from utils.date_parser import parse_natural_date
    from utils.logger import setup_logging

logger = logging.getLogger(__name__)


class FreqtradeMCPServer:
    """MCP Server for Freqtrade operations."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize the Freqtrade MCP server."""
        try:
            self.config = config or load_config()
            self.server = Server("freqtrade-mcp")
            self.commands = self._initialize_commands()
            self._setup_handlers()
        except Exception as e:
            print(f"Server initialization failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            raise

    async def send_log_message(self, level: LoggingLevel, message: str, data: Optional[Dict] = None):
        """Send MCP-safe log message."""
        try:
            # Check if we have an active request context and session
            if (hasattr(self.server, 'request_context') and 
                self.server.request_context and 
                hasattr(self.server.request_context, 'session') and
                self.server.request_context.session):
                
                await self.server.request_context.session.send_log_message(
                    level=level,
                    data=message,
                    logger=data.get("logger", "freqtrade-mcp") if data else "freqtrade-mcp"
                )
            else:
                # No active session, use file logging
                logger.info(f"[{level}] {message}")
        except Exception as e:
            # Fallback to file logging if MCP logging fails
            logger.info(f"[{level}] {message} (MCP logging failed: {e})")

    async def log_info(self, message: str, **kwargs):
        """Log info message via MCP."""
        await self.send_log_message(LoggingLevel.INFO, message, kwargs)

    async def log_warning(self, message: str, **kwargs):
        """Log warning message via MCP."""
        await self.send_log_message(LoggingLevel.WARNING, message, kwargs)

    async def log_error(self, message: str, **kwargs):
        """Log error message via MCP."""
        await self.send_log_message(LoggingLevel.ERROR, message, kwargs)

    def _initialize_commands(self) -> Dict[str, Any]:
        """Initialize all available commands."""
        try:
            return {
                "download_candles": DownloadCandlesCommand(self.config, self),
                "backtest_strategy": BacktestStrategyCommand(self.config, self),
                "hyperopt_strategy": HyperoptStrategyCommand(self.config, self),
                "list_results": ListResultsCommand(self.config, self),
                "get_result": GetResultCommand(self.config, self),
                "create_userdir": CreateUserdirCommand(self.config, self),
                "create_config": CreateConfigCommand(self.config, self),
                "create_strategy": CreateStrategyCommand(self.config, self),
                "create_strategy_wireframe": CreateStrategyWireframeCommand(self.config, self),
                "extract_backtest_data": ExtractBacktestDataCommand(self.config, self),
                "extract_hyperopt_data": ExtractHyperoptDataCommand(self.config, self),
                "search_results": SearchResultsCommand(self.config, self),
            }
        except Exception as e:
            print(f"Failed to initialize commands: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            raise

    def _setup_handlers(self):
        """Set up server handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools."""
            tools = []
            
            tools.append(Tool(
                name="download_candles",
                description="Download historical candle data for specified pairs and timeframes",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pairs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of trading pairs or 'top15' for top market cap coins"
                        },
                        "timeframes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of timeframes (5m,15m,30m,1h,4h,1d) or 'all'"
                        },
                        "date_range": {
                            "type": "string",
                            "description": "Natural language date range (e.g., 'last year', 'september', 'last 3 months')"
                        },
                        "exchange": {
                            "type": "string",
                            "description": "Exchange name (default: binance)",
                            "default": "binance"
                        }
                    },
                    "required": ["pairs", "timeframes", "date_range"]
                }
            ))
            
            tools.append(Tool(
                name="backtest_strategy",
                description="Run backtest for a strategy with specified parameters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "strategy_name": {
                            "type": "string",
                            "description": "Name of the strategy to backtest"
                        },
                        "pairs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Trading pairs to test"
                        },
                        "timerange": {
                            "type": "string",
                            "description": "Natural language date range for backtesting"
                        },
                        "stake_amount": {
                            "type": "number",
                            "description": "Amount to stake per trade",
                            "default": 100
                        },
                        "enable_protections": {
                            "type": "boolean",
                            "description": "Enable trading protections",
                            "default": False
                        },
                        "export_trades": {
                            "type": "boolean",
                            "description": "Export detailed trade data",
                            "default": True
                        },
                        "export_signals": {
                            "type": "boolean",
                            "description": "Export entry/exit signals",
                            "default": True
                        }
                    },
                    "required": ["strategy_name", "pairs", "timerange"]
                }
            ))
            
            tools.append(Tool(
                name="hyperopt_strategy",
                description="Run hyperparameter optimization for a strategy",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "strategy_name": {
                            "type": "string",
                            "description": "Name of the strategy to optimize"
                        },
                        "pairs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Trading pairs for optimization"
                        },
                        "timerange": {
                            "type": "string",
                            "description": "Natural language date range"
                        },
                        "epochs": {
                            "type": "integer",
                            "description": "Number of optimization epochs",
                            "default": 100
                        },
                        "spaces": {
                            "type": "string",
                            "description": "Spaces to optimize (all, buy, sell, roi, stoploss)",
                            "default": "all"
                        },
                        "loss_function": {
                            "type": "string",
                            "description": "Loss function to use",
                            "default": "ShortTradeDurHyperOptLoss"
                        }
                    },
                    "required": ["strategy_name", "pairs", "timerange"]
                }
            ))
            
            tools.append(Tool(
                name="list_results",
                description="List available backtest and hyperopt results",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "result_type": {
                            "type": "string",
                            "enum": ["backtest", "hyperopt", "all"],
                            "description": "Type of results to list",
                            "default": "all"
                        },
                        "strategy": {
                            "type": "string",
                            "description": "Filter by strategy name"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 20
                        }
                    }
                }
            ))
            
            tools.append(Tool(
                name="get_result",
                description="Retrieve a specific result by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "result_id": {
                            "type": "string",
                            "description": "ID of the result to retrieve"
                        },
                        "include_metadata": {
                            "type": "boolean",
                            "description": "Include metadata in response",
                            "default": True
                        }
                    },
                    "required": ["result_id"]
                }
            ))
            
            tools.append(Tool(
                name="create_userdir",
                description="Create a new Freqtrade user directory structure with sample files",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "userdir": {
                            "type": "string",
                            "description": "Path where to create the user directory"
                        },
                        "reset": {
                            "type": "boolean",
                            "description": "Reset user directory if it already exists",
                            "default": False
                        }
                    },
                    "required": ["userdir"]
                }
            ))
            
            tools.append(Tool(
                name="create_config",
                description="Create a new Freqtrade configuration file from template",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_path": {
                            "type": "string",
                            "description": "Path where to save the configuration file",
                            "default": "config.json"
                        },
                        "template": {
                            "type": "string",
                            "enum": ["default", "conservative", "aggressive", "advanced"],
                            "description": "Configuration template to use",
                            "default": "default"
                        },
                        "exchange": {
                            "type": "string",
                            "description": "Exchange name (e.g., 'binance', 'kraken')"
                        },
                        "stake_currency": {
                            "type": "string",
                            "description": "Stake currency (e.g., 'USDT', 'BTC')"
                        },
                        "stake_amount": {
                            "type": "number",
                            "description": "Amount to stake per trade"
                        },
                        "max_open_trades": {
                            "type": "integer",
                            "description": "Maximum number of concurrent trades"
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Enable dry run mode (paper trading)"
                        },
                        "trading_mode": {
                            "type": "string",
                            "enum": ["spot", "futures", "margin"],
                            "description": "Trading mode"
                        },
                        "pairs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of trading pairs"
                        }
                    },
                    "required": ["config_path"]
                }
            ))
            
            tools.append(Tool(
                name="create_strategy",
                description="Create a new Freqtrade trading strategy from template",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "strategy_name": {
                            "type": "string",
                            "description": "Name of the strategy class and file"
                        },
                        "strategy_path": {
                            "type": "string",
                            "description": "Custom path for strategy file (optional)"
                        },
                        "template": {
                            "type": "string",
                            "enum": ["basic", "trend", "mean_reversion", "scalping", "advanced"],
                            "description": "Strategy template to use",
                            "default": "basic"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Primary timeframe for the strategy",
                            "default": "5m"
                        },
                        "indicators": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of technical indicators to include"
                        },
                        "can_short": {
                            "type": "boolean",
                            "description": "Whether the strategy can short sell",
                            "default": False
                        },
                        "minimal_roi": {
                            "type": "object",
                            "description": "ROI table configuration"
                        },
                        "stoploss": {
                            "type": "number",
                            "description": "Stop loss percentage (negative value)",
                            "default": -0.10
                        },
                        "trailing_stop": {
                            "type": "boolean",
                            "description": "Enable trailing stop",
                            "default": False
                        },
                        "description": {
                            "type": "string",
                            "description": "Strategy description"
                        }
                    },
                    "required": ["strategy_name"]
                }
            ))
            
            tools.append(Tool(
                name="create_strategy_wireframe",
                description="Create minimal strategy wireframe for maximum LLM flexibility",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "strategy_name": {
                            "type": "string",
                            "description": "Name of the strategy class and file"
                        },
                        "strategy_path": {
                            "type": "string",
                            "description": "Custom path for strategy file (optional)"
                        },
                        "style": {
                            "type": "string",
                            "enum": ["minimal", "guided", "structured"],
                            "description": "Wireframe style - minimal for max flexibility, guided for hints, structured for advanced features",
                            "default": "minimal"
                        },
                        "include_comments": {
                            "type": "boolean",
                            "description": "Include TODO comments and guidance",
                            "default": True
                        },
                        "include_examples": {
                            "type": "boolean",
                            "description": "Include example code snippets",
                            "default": False
                        },
                        "description": {
                            "type": "string",
                            "description": "Strategy description to include in docstring"
                        }
                    },
                    "required": ["strategy_name"]
                }
            ))
            
            tools.append(Tool(
                name="extract_backtest_data",
                description="Extract and analyze data from backtest result .zip files",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "result_path": {
                            "type": "string",
                            "description": "Path to the backtest result .zip file"
                        },
                        "include_trades": {
                            "type": "boolean",
                            "description": "Include individual trade data",
                            "default": True
                        },
                        "include_performance": {
                            "type": "boolean",
                            "description": "Include performance metrics",
                            "default": True
                        },
                        "include_strategy_code": {
                            "type": "boolean",
                            "description": "Include strategy source code",
                            "default": False
                        },
                        "include_config": {
                            "type": "boolean",
                            "description": "Include configuration used",
                            "default": False
                        },
                        "include_market_data": {
                            "type": "boolean",
                            "description": "Include market change data",
                            "default": False
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["summary", "detailed", "raw"],
                            "description": "Level of detail in output",
                            "default": "summary"
                        }
                    },
                    "required": ["result_path"]
                }
            ))
            
            tools.append(Tool(
                name="extract_hyperopt_data",
                description="Extract and analyze data from hyperopt result .fthypt files",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "hyperopt_path": {
                            "type": "string",
                            "description": "Path to the hyperopt result .fthypt file"
                        },
                        "include_trials": {
                            "type": "boolean",
                            "description": "Include individual trial data",
                            "default": True
                        },
                        "include_best_params": {
                            "type": "boolean",
                            "description": "Include best parameter combinations",
                            "default": True
                        },
                        "include_parameter_ranges": {
                            "type": "boolean",
                            "description": "Include parameter space analysis",
                            "default": True
                        },
                        "include_convergence": {
                            "type": "boolean",
                            "description": "Include optimization convergence analysis",
                            "default": True
                        },
                        "max_trials": {
                            "type": "integer",
                            "description": "Maximum number of trials to include (for performance)"
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["summary", "detailed", "raw"],
                            "description": "Level of detail in output",
                            "default": "summary"
                        }
                    },
                    "required": ["hyperopt_path"]
                }
            ))
            
            tools.append(Tool(
                name="search_results",
                description="Search and filter backtest and hyperopt results with advanced criteria",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Free text search query"
                        },
                        "result_type": {
                            "type": "string",
                            "enum": ["all", "backtest", "hyperopt"],
                            "description": "Type of results to search",
                            "default": "all"
                        },
                        "strategy_name": {
                            "type": "string",
                            "description": "Filter by strategy name"
                        },
                        "min_profit": {
                            "type": "number",
                            "description": "Minimum profit percentage"
                        },
                        "max_drawdown": {
                            "type": "number",
                            "description": "Maximum drawdown percentage"
                        },
                        "min_trades": {
                            "type": "integer",
                            "description": "Minimum number of trades"
                        },
                        "min_winrate": {
                            "type": "number",
                            "description": "Minimum win rate (0-1)"
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Start date filter (YYYY-MM-DD)"
                        },
                        "date_to": {
                            "type": "string",
                            "description": "End date filter (YYYY-MM-DD)"
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["date", "profit", "winrate", "trades", "drawdown"],
                            "description": "Sort criteria",
                            "default": "date"
                        },
                        "sort_order": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "Sort direction",
                            "default": "desc"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 20
                        },
                        "include_summary": {
                            "type": "boolean",
                            "description": "Include performance summaries",
                            "default": True
                        },
                        "rebuild_index": {
                            "type": "boolean",
                            "description": "Force rebuild of search index",
                            "default": False
                        }
                    }
                }
            ))
            
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a tool with given arguments."""
            try:
                if name not in self.commands:
                    error_result = {
                        "error": f"Unknown tool: {name}",
                        "success": False
                    }
                    return [TextContent(
                        type="text",
                        text=json.dumps(error_result, indent=2)
                    )]
                
                command = self.commands[name]
                result = await command.execute(**arguments)
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                error_result = {
                    "error": str(e),
                    "success": False,
                    "tool": name
                }
                return [TextContent(
                    type="text",
                    text=json.dumps(error_result, indent=2)
                )]

    async def run(self):
        """Run the MCP server."""
        # For MCP protocol, we need to be careful with logging
        # Set up logging to file only when running as MCP server
        import tempfile
        import os
        
        # Create a temporary log file for MCP mode
        log_file = os.path.join(tempfile.gettempdir(), "freqtrade_mcp.log")
        
        # Set up file-only logging for MCP mode
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Set up root logger with file handler only
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.handlers.clear()
        
        # Only use file handler for MCP mode to avoid stdout/stderr interference
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Quiet some noisy loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("freqtrade").setLevel(logging.WARNING)
        logging.getLogger("ccxt").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.WARNING)
        
        logger.info(f"Starting Freqtrade MCP Server (logs: {log_file})")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """Main entry point."""
    try:
        # Clear any existing logging handlers to prevent stdout/stderr interference
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        server = FreqtradeMCPServer()
        asyncio.run(server.run())
        
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()