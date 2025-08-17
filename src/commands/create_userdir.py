"""Create userdir command implementation."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .base import BaseCommand, FREQTRADE_AVAILABLE
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand, FREQTRADE_AVAILABLE

# Import freqtrade modules for package-based functionality
if FREQTRADE_AVAILABLE:
    try:
        from freqtrade.configuration import Configuration
    except ImportError:
        FREQTRADE_AVAILABLE = False

logger = logging.getLogger(__name__)


class CreateUserdirCommand(BaseCommand):
    """Command to create a new Freqtrade user directory structure."""

    async def execute(
        self,
        userdir: str,
        reset: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute create userdir command.
        
        Args:
            userdir: Path where to create the user directory
            reset: Reset user directory if it already exists
            
        Returns:
            Command execution result with created directory structure
        """
        try:
            await self.mcp_log("info", f"Creating user directory at: {userdir}")
            
            userdir_path = Path(userdir).resolve()
            
            # Check if directory exists
            if userdir_path.exists() and not reset:
                return {
                    "command": "create_userdir",
                    "success": False,
                    "error": f"Directory {userdir_path} already exists. Use reset=True to overwrite.",
                    "userdir": str(userdir_path)
                }
            
            if FREQTRADE_AVAILABLE:
                # Use freqtrade package for better integration
                try:
                    result = await self._create_userdir_using_package(userdir_path, reset)
                    await self.mcp_log("info", "User directory created using freqtrade package")
                    return result
                except Exception as e:
                    await self.mcp_log("warning", f"Package-based creation failed, falling back to CLI: {e}")
            
            # Fallback to CLI mode
            result = await self._create_userdir_using_cli(userdir_path, reset)
            await self.mcp_log("info", "User directory created using CLI")
            return result
            
        except Exception as e:
            await self.mcp_log("error", f"Create userdir command failed: {e}")
            return {
                "command": "create_userdir",
                "success": False,
                "error": str(e),
                "userdir": userdir
            }

    async def _create_userdir_using_package(
        self, 
        userdir_path: Path, 
        reset: bool
    ) -> Dict[str, Any]:
        """Create userdir using freqtrade package functions."""
        import shutil
        
        # If reset is True and directory exists, remove it
        if reset and userdir_path.exists():
            await self.mcp_log("info", f"Resetting existing directory: {userdir_path}")
            shutil.rmtree(userdir_path)
        
        # Create the directory structure manually based on freqtrade structure
        directories_created = []
        files_created = []
        
        # Create main user directory
        userdir_path.mkdir(parents=True, exist_ok=True)
        directories_created.append(str(userdir_path))
        
        # Create subdirectories
        subdirs = [
            "strategies",
            "hyperopts", 
            "data",
            "notebooks",
            "logs",
            "backtest_results",
            "hyperopt_results",
            "plot"
        ]
        
        for subdir in subdirs:
            subdir_path = userdir_path / subdir
            subdir_path.mkdir(exist_ok=True)
            directories_created.append(str(subdir_path))
        
        # Create sample files
        sample_files = {
            "strategies/__init__.py": "",
            "strategies/sample_strategy.py": self._get_sample_strategy(),
            "hyperopts/__init__.py": "",
            "notebooks/strategy_analysis.ipynb": self._get_sample_notebook(),
            "config.json": self._get_sample_config(),
        }
        
        for file_path, content in sample_files.items():
            full_path = userdir_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            files_created.append(str(full_path))
        
        await self.mcp_log("info", f"Created {len(directories_created)} directories and {len(files_created)} files")
        
        return {
            "command": "create_userdir",
            "success": True,
            "userdir": str(userdir_path),
            "method": "package",
            "directories_created": directories_created,
            "files_created": files_created,
            "summary": {
                "total_directories": len(directories_created),
                "total_files": len(files_created),
                "reset_performed": reset and len(directories_created) > 0
            }
        }

    async def _create_userdir_using_cli(
        self, 
        userdir_path: Path, 
        reset: bool
    ) -> Dict[str, Any]:
        """Create userdir using CLI commands."""
        args = ["create-userdir", "--userdir", str(userdir_path)]
        
        if reset:
            args.append("--reset")
        
        # Execute command
        result = await self.run_freqtrade_command(args)
        
        if result["success"]:
            await self.mcp_log("info", "User directory created successfully via CLI")
            
            # Parse created structure
            directories_created = []
            files_created = []
            
            # Check what was actually created
            if userdir_path.exists():
                for item in userdir_path.rglob("*"):
                    if item.is_dir():
                        directories_created.append(str(item))
                    else:
                        files_created.append(str(item))
        else:
            await self.mcp_log("error", f"CLI userdir creation failed: {result['stderr']}")
        
        return {
            "command": "create_userdir",
            "success": result["success"],
            "userdir": str(userdir_path),
            "method": "cli",
            "directories_created": directories_created if result["success"] else [],
            "files_created": files_created if result["success"] else [],
            "output": result["stdout"],
            "error": result["stderr"] if not result["success"] else None,
            "summary": {
                "total_directories": len(directories_created) if result["success"] else 0,
                "total_files": len(files_created) if result["success"] else 0,
                "reset_performed": reset
            }
        }

    def _get_sample_strategy(self) -> str:
        """Get sample strategy code."""
        return '''"""
Sample Strategy for Freqtrade
This is a basic template strategy to get you started.
"""

from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class SampleStrategy(IStrategy):
    """
    Sample strategy implementing RSI-based trading logic.
    """
    
    # Strategy interface version
    INTERFACE_VERSION: int = 3
    
    # Optimal timeframe for the strategy
    timeframe = '5m'
    
    # Can this strategy go short?
    can_short: bool = False
    
    # Minimal ROI designed for the strategy
    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }
    
    # Optimal stoploss
    stoploss = -0.10
    
    # Trailing stoploss
    trailing_stop = False
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        """
        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &  # RSI oversold
                (dataframe['macd'] > dataframe['macdsignal']) &  # MACD above signal
                (dataframe['close'] < dataframe['bb_lowerband']) &  # Price below lower Bollinger Band
                (dataframe['volume'] > 0)  # Make sure Volume is not 0
            ),
            'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) &  # RSI overbought
                (dataframe['macd'] < dataframe['macdsignal']) &  # MACD below signal
                (dataframe['close'] > dataframe['bb_upperband']) &  # Price above upper Bollinger Band
                (dataframe['volume'] > 0)  # Make sure Volume is not 0
            ),
            'exit_long'] = 1
        
        return dataframe
'''

    def _get_sample_notebook(self) -> str:
        """Get sample Jupyter notebook content."""
        return '''{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Freqtrade Strategy Analysis\\n",
    "\\n",
    "This notebook provides tools for analyzing your trading strategies."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import pandas as pd\\n",
    "import numpy as np\\n",
    "import matplotlib.pyplot as plt\\n",
    "\\n",
    "# Freqtrade imports\\n",
    "from freqtrade.data.history import load_pair_history\\n",
    "from freqtrade.resolvers import StrategyResolver"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.8.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}'''

    def _get_sample_config(self) -> str:
        """Get sample configuration file."""
        return '''{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": 100,
    "tradable_balance_ratio": 0.99,
    "fiat_display_currency": "USD",
    "dry_run": true,
    "dry_run_wallet": 1000,
    "cancel_open_orders_on_exit": false,
    "trading_mode": "spot",
    "unfilledtimeout": {
        "entry": 10,
        "exit": 10,
        "exit_timeout_count": 0,
        "unit": "minutes"
    },
    "entry_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1,
        "price_last_balance": 0.0,
        "check_depth_of_market": {
            "enabled": false,
            "bids_to_ask_delta": 1
        }
    },
    "exit_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },
    "exchange": {
        "name": "binance",
        "key": "",
        "secret": "",
        "ccxt_config": {},
        "ccxt_async_config": {},
        "pair_whitelist": [
            "BTC/USDT",
            "ETH/USDT"
        ],
        "pair_blacklist": []
    },
    "pairlists": [
        {"method": "StaticPairList"}
    ],
    "edge": {
        "enabled": false,
        "process_throttle_secs": 3600,
        "calculate_since_number_of_days": 7,
        "allowed_risk": 0.01,
        "stoploss_range_min": -0.01,
        "stoploss_range_max": -0.1,
        "stoploss_range_step": -0.01,
        "minimum_winrate": 0.60,
        "minimum_expectancy": 0.20,
        "min_trade_number": 10,
        "max_trade_duration_minute": 1440,
        "remove_pumps": false
    },
    "telegram": {
        "enabled": false,
        "token": "",
        "chat_id": ""
    },
    "api_server": {
        "enabled": false,
        "listen_ip_address": "127.0.0.1",
        "listen_port": 8080,
        "verbosity": "error",
        "enable_openapi": false,
        "jwt_secret_key": "",
        "CORS_origins": [],
        "username": "",
        "password": ""
    },
    "bot_name": "freqtrade",
    "initial_state": "running",
    "force_entry_enable": false,
    "internals": {
        "process_throttle_secs": 5
    }
}'''