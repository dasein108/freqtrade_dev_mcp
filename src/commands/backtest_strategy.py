"""Backtest strategy command implementation."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .base import BaseCommand, FREQTRADE_AVAILABLE
    from ..utils.date_parser import parse_and_format_date
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand, FREQTRADE_AVAILABLE
    from utils.date_parser import parse_and_format_date

# Import freqtrade modules for package-based functionality
if FREQTRADE_AVAILABLE:
    try:
        from freqtrade.optimize.backtesting import Backtesting
        from freqtrade.data.history import get_timerange
        from freqtrade.configuration import Configuration
    except ImportError:
        FREQTRADE_AVAILABLE = False

logger = logging.getLogger(__name__)


class BacktestStrategyCommand(BaseCommand):
    """Command to run strategy backtesting."""

    async def execute(
        self,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        stake_amount: float = None,
        enable_protections: bool = False,
        export_trades: bool = True,
        export_signals: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute backtest strategy command.
        
        Args:
            strategy_name: Name of the strategy to backtest
            pairs: List of trading pairs to test
            timerange: Natural language date range
            stake_amount: Amount to stake per trade
            enable_protections: Enable trading protections
            export_trades: Export detailed trade data
            export_signals: Export entry/exit signals
            
        Returns:
            Command execution result with backtest metrics and file paths
        """
        try:
            # Validate strategy exists
            if not self.validate_strategy(strategy_name):
                return {
                    "command": "backtest_strategy",
                    "success": False,
                    "error": f"Strategy '{strategy_name}' not found",
                    "strategy_path": str(self.config.full_strategy_dir / f"{strategy_name}.py")
                }

            # Parse date range
            parsed_timerange = parse_and_format_date(timerange)
            logger.info(f"Parsed timerange '{timerange}' to: {parsed_timerange}")

            # Set default stake amount
            if stake_amount is None:
                stake_amount = self.config.default_stake_amount

            # Ensure results directory exists
            self.config.full_backtest_results_dir.mkdir(parents=True, exist_ok=True)

            # Generate result ID
            result_id = self.generate_result_id("backtest", strategy_name)

            # Build freqtrade backtest command
            args = self._build_backtest_args(
                strategy_name=strategy_name,
                pairs=pairs,
                timerange=parsed_timerange,
                stake_amount=stake_amount,
                enable_protections=enable_protections,
                export_trades=export_trades,
                export_signals=export_signals,
                result_id=result_id
            )

            # Execute backtest
            logger.info(f"Running backtest for strategy '{strategy_name}'")
            
            if FREQTRADE_AVAILABLE:
                # Try package-based backtest first
                try:
                    backtest_data = await self._run_backtest_using_package(
                        strategy_name, pairs, parsed_timerange, stake_amount,
                        enable_protections, export_trades, export_signals, result_id
                    )
                except Exception as e:
                    logger.warning(f"Package-based backtest failed, falling back to CLI: {e}")
                    # Fall back to CLI
                    result = await self.run_freqtrade_command(args, timeout=1800)
                    if not result["success"]:
                        return {
                            "command": "backtest_strategy",
                            "strategy": strategy_name,
                            "success": False,
                            "error": "Backtest execution failed",
                            "details": {
                                "returncode": result["returncode"],
                                "stderr": result["stderr"],
                                "stdout": result["stdout"]
                            }
                        }
                    backtest_data = self._parse_backtest_output(
                        result["stdout"], strategy_name, pairs, timerange, result_id
                    )
            else:
                # CLI mode only
                result = await self.run_freqtrade_command(args, timeout=1800)
                if not result["success"]:
                    return {
                        "command": "backtest_strategy",
                        "strategy": strategy_name,
                        "success": False,
                        "error": "Backtest execution failed",
                        "details": {
                            "returncode": result["returncode"],
                            "stderr": result["stderr"],
                            "stdout": result["stdout"]
                        }
                    }
                backtest_data = self._parse_backtest_output(
                    result["stdout"], strategy_name, pairs, timerange, result_id
                )

            # Add export file paths if they exist
            export_files = self._find_export_files(result_id)
            backtest_data.update(export_files)

            # Save result
            self.save_result(backtest_data, result_id, "backtest")

            return backtest_data

        except Exception as e:
            logger.error(f"Backtest command failed: {e}", exc_info=True)
            return {
                "command": "backtest_strategy",
                "strategy": strategy_name,
                "success": False,
                "error": str(e)
            }

    def _build_backtest_args(
        self,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        stake_amount: float,
        enable_protections: bool,
        export_trades: bool,
        export_signals: bool,
        result_id: str
    ) -> List[str]:
        """Build freqtrade backtest command arguments."""
        args = [
            "backtesting",
            "--strategy", strategy_name,
            "--timerange", timerange,
            "--stake-amount", str(stake_amount),
        ]

        # Add pairs
        if pairs:
            pairs_str = " ".join(pairs)
            args.extend(["--pairs", pairs_str])

        # Add protections
        if enable_protections:
            args.append("--enable-protections")

        # Add export options
        if export_trades:
            args.extend(["--export", "trades"])
            args.extend(["--export-filename", f"backtest_trades_{result_id}"])

        if export_signals:
            args.extend(["--export", "signals"])
            args.extend(["--export-filename", f"backtest_signals_{result_id}"])

        return args

    async def _run_backtest_using_package(
        self,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        stake_amount: float,
        enable_protections: bool,
        export_trades: bool,
        export_signals: bool,
        result_id: str
    ) -> Dict[str, Any]:
        """Run backtest using freqtrade package functions."""
        import asyncio
        
        # Build configuration for freqtrade
        config = self.get_freqtrade_config()
        config.update({
            'strategy': strategy_name,
            'timerange': timerange,
            'stake_amount': stake_amount,
            'enable_protections': enable_protections,
            'exportfilename': f"backtest_{result_id}",
            'export': [],
            'backtest_show_pair_list': True,
            'datadir': str(self.config.full_data_dir),
            'user_data_dir': str(self.config.freqtrade_path / "user_data"),
        })
        
        if pairs:
            config['pairs'] = pairs
            
        if export_trades:
            config['export'].append('trades')
        if export_signals:
            config['export'].append('signals')
            
        # Initialize backtesting engine
        def run_backtest():
            backtesting = Backtesting(config)
            return backtesting.start()
            
        # Run backtest in thread to avoid blocking
        try:
            backtest_stats = await asyncio.to_thread(run_backtest)
            
            # Extract key metrics from backtest stats
            if backtest_stats and 'strategy' in backtest_stats:
                strategy_stats = backtest_stats['strategy'][strategy_name]
                
                return {
                    "command": "backtest_strategy",
                    "result_id": result_id,
                    "strategy": strategy_name,
                    "pairs": pairs,
                    "timerange": timerange,
                    "success": True,
                    "summary": {
                        "total_profit": strategy_stats.get('profit_total', 0.0),
                        "win_rate": strategy_stats.get('wins', 0) / max(strategy_stats.get('total_trades', 1), 1),
                        "max_drawdown": strategy_stats.get('max_drawdown', 0.0),
                        "total_trades": strategy_stats.get('total_trades', 0),
                        "profit_factor": strategy_stats.get('profit_factor', 0.0),
                        "calmar_ratio": strategy_stats.get('calmar', 0.0),
                        "sharpe_ratio": strategy_stats.get('sharpe', 0.0),
                    },
                    "detailed_stats": strategy_stats,
                    "method": "package"
                }
            else:
                raise ValueError("No backtest results returned")
                
        except Exception as e:
            logger.error(f"Package-based backtest failed: {e}")
            raise

    def _parse_backtest_output(
        self,
        output: str,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        result_id: str
    ) -> Dict[str, Any]:
        """Parse freqtrade backtest output into structured data."""
        lines = output.split('\n')
        
        # Initialize result structure
        result = {
            "command": "backtest_strategy",
            "result_id": result_id,
            "strategy": strategy_name,
            "pairs": pairs,
            "timerange": timerange,
            "success": True,
            "summary": {},
            "raw_output": output
        }

        # Parse key metrics
        for line in lines:
            line = line.strip()
            
            # Total profit
            if "Total profit" in line:
                match = re.search(r"Total profit\s*[:\|]\s*([-+]?\d*\.?\d+)", line)
                if match:
                    result["summary"]["total_profit"] = float(match.group(1))
            
            # Win rate
            if "Win  %" in line or "Win rate" in line:
                match = re.search(r"Win\s*%?\s*[:\|]\s*(\d*\.?\d+)", line)
                if match:
                    result["summary"]["win_rate"] = float(match.group(1)) / 100.0
            
            # Max drawdown
            if "Max Drawdown" in line:
                match = re.search(r"Max Drawdown\s*[:\|]\s*([-+]?\d*\.?\d+)", line)
                if match:
                    result["summary"]["max_drawdown"] = float(match.group(1))
            
            # Total trades
            if "Total trades" in line:
                match = re.search(r"Total trades\s*[:\|]\s*(\d+)", line)
                if match:
                    result["summary"]["total_trades"] = int(match.group(1))
            
            # Profit factor
            if "Profit factor" in line:
                match = re.search(r"Profit factor\s*[:\|]\s*(\d*\.?\d+)", line)
                if match:
                    result["summary"]["profit_factor"] = float(match.group(1))

        return result

    def _find_export_files(self, result_id: str) -> Dict[str, Optional[str]]:
        """Find exported trade and signal files."""
        export_files = {
            "trades_file": None,
            "signals_file": None
        }

        # Look for exported files in backtest results directory
        results_dir = self.config.full_backtest_results_dir
        
        # Find trades file
        trades_pattern = f"backtest_trades_{result_id}*"
        for trades_file in results_dir.glob(trades_pattern):
            export_files["trades_file"] = str(trades_file)
            break

        # Find signals file  
        signals_pattern = f"backtest_signals_{result_id}*"
        for signals_file in results_dir.glob(signals_pattern):
            export_files["signals_file"] = str(signals_file)
            break

        # Also check user_data/backtest_results for default freqtrade location
        default_backtest_dir = self.config.freqtrade_path / "user_data" / "backtest_results"
        if default_backtest_dir.exists():
            for trades_file in default_backtest_dir.glob(f"*trades*{result_id}*"):
                export_files["trades_file"] = str(trades_file)
                break
            for signals_file in default_backtest_dir.glob(f"*signals*{result_id}*"):
                export_files["signals_file"] = str(signals_file)
                break

        return export_files