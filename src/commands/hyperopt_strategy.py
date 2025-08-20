"""Hyperopt strategy command implementation."""

import json
import logging
import re
from typing import Any, Dict, List

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
        from freqtrade.optimize.hyperopt import Hyperopt
        from freqtrade.data.history import get_timerange
        from freqtrade.configuration import Configuration
    except ImportError:
        FREQTRADE_AVAILABLE = False

logger = logging.getLogger(__name__)


class HyperoptStrategyCommand(BaseCommand):
    """Command to run strategy hyperparameter optimization."""

    async def execute(
        self,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        epochs: int = None,
        spaces: str = "all",
        loss_function: str = "ShortTradeDurHyperOptLoss",
        **kwargs
    ) -> Dict[str, Any]:
        """Execute hyperopt strategy command.
        
        Args:
            strategy_name: Name of the strategy to optimize
            pairs: List of trading pairs for optimization
            timerange: Natural language date range
            epochs: Number of optimization epochs
            spaces: Spaces to optimize (all, buy, sell, roi, stoploss)
            loss_function: Loss function to use
            
        Returns:
            Command execution result with optimization results
        """
        try:
            # Validate strategy exists
            if not self.validate_strategy(strategy_name):
                return {
                    "command": "hyperopt_strategy",
                    "success": False,
                    "error": f"Strategy '{strategy_name}' not found",
                    "strategy_path": str(self.config.full_strategy_dir / f"{strategy_name}.py")
                }

            # Parse date range
            parsed_timerange = parse_and_format_date(timerange)
            logger.info(f"Parsed timerange '{timerange}' to: {parsed_timerange}")

            # Set default epochs
            if epochs is None:
                epochs = self.config.default_epochs

            # Ensure results directory exists
            self.config.full_hyperopt_results_dir.mkdir(parents=True, exist_ok=True)

            # Generate result ID
            result_id = self.generate_result_id("hyperopt", strategy_name)

            # Build freqtrade hyperopt command
            args = self._build_hyperopt_args(
                strategy_name=strategy_name,
                pairs=pairs,
                timerange=parsed_timerange,
                epochs=epochs,
                spaces=spaces,
                loss_function=loss_function,
                result_id=result_id
            )

            # Execute hyperopt
            logger.info(f"Running hyperopt for strategy '{strategy_name}' with {epochs} epochs")
            
            if FREQTRADE_AVAILABLE:
                # Try package-based hyperopt first
                try:
                    hyperopt_data = await self._run_hyperopt_using_package(
                        strategy_name, pairs, parsed_timerange, epochs,
                        spaces, loss_function, result_id
                    )
                except Exception as e:
                    logger.warning(f"Package-based hyperopt failed, falling back to CLI: {e}")
                    # Fall back to CLI
                    result = await self.run_freqtrade_command(args, timeout=3600)
                    if not result["success"]:
                        return {
                            "command": "hyperopt_strategy",
                            "strategy": strategy_name,
                            "success": False,
                            "error": "Hyperopt execution failed",
                            "details": {
                                "returncode": result["returncode"],
                                "stderr": result["stderr"],
                                "stdout": result["stdout"]
                            }
                        }
                    hyperopt_data = self._parse_hyperopt_output(
                        result["stdout"], strategy_name, pairs, timerange, epochs, result_id
                    )
            else:
                # CLI mode only
                result = await self.run_freqtrade_command(args, timeout=3600)
                if not result["success"]:
                    return {
                        "command": "hyperopt_strategy",
                        "strategy": strategy_name,
                        "success": False,
                        "error": "Hyperopt execution failed",
                        "details": {
                            "returncode": result["returncode"],
                            "stderr": result["stderr"],
                            "stdout": result["stdout"]
                        }
                    }
                hyperopt_data = self._parse_hyperopt_output(
                    result["stdout"], strategy_name, pairs, timerange, epochs, result_id
                )

            # Find and include hyperopt results file
            results_file = self._find_hyperopt_results_file(result_id)
            if results_file:
                hyperopt_data["results_file"] = str(results_file)

            # Save result
            self.save_result(hyperopt_data, result_id, "hyperopt")

            return hyperopt_data

        except Exception as e:
            logger.error(f"Hyperopt command failed: {e}", exc_info=True)
            return {
                "command": "hyperopt_strategy",
                "strategy": strategy_name,
                "success": False,
                "error": str(e)
            }

    def _build_hyperopt_args(
        self,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        epochs: int,
        spaces: str,
        loss_function: str,
        result_id: str
    ) -> List[str]:
        """Build freqtrade hyperopt command arguments."""
        args = [
            "hyperopt",
            "--strategy", strategy_name,
            "--timerange", timerange,
            "--epochs", str(epochs),
            "--hyperopt-loss", loss_function,
        ]
        
        # Handle spaces parameter - split comma-separated values
        if spaces:
            if ',' in spaces:
                # Split comma-separated spaces and add as separate arguments
                space_list = [s.strip() for s in spaces.split(',')]
                args.extend(["--spaces"] + space_list)
            else:
                args.extend(["--spaces", spaces])

        # Add pairs
        if pairs:
            pairs_str = " ".join(pairs)
            args.extend(["--pairs", pairs_str])

        # Add job workers for parallel execution
        args.extend(["-j", "1"])  # Single job for now, can be configurable

        return args

    async def _run_hyperopt_using_package(
        self,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        epochs: int,
        spaces: str,
        loss_function: str,
        result_id: str
    ) -> Dict[str, Any]:
        """Run hyperopt using freqtrade package functions."""
        import asyncio
        
        # Build configuration for freqtrade
        config = self.get_freqtrade_config()
        
        # Handle spaces parameter - convert comma-separated string to list
        if spaces:
            if ',' in spaces:
                space_list = [s.strip() for s in spaces.split(',')]
            else:
                space_list = [spaces]
        else:
            space_list = ["all"]
        
        config.update({
            'strategy': strategy_name,
            'timerange': timerange,
            'epochs': epochs,
            'spaces': space_list,
            'hyperopt_loss': loss_function,
            'hyperopt_jobs': 1,
            'datadir': str(self.config.full_data_dir),
            'user_data_dir': str(self.config.freqtrade_path / "user_data"),
        })
        
        if pairs:
            config['pairs'] = pairs
            
        # Initialize hyperopt engine
        def run_hyperopt():
            hyperopt = Hyperopt(config)
            return hyperopt.start()
            
        # Run hyperopt in thread to avoid blocking
        try:
            hyperopt_results = await asyncio.to_thread(run_hyperopt)
            
            # Extract best results from hyperopt
            if hyperopt_results:
                best_result = hyperopt_results.get('best', {})
                
                return {
                    "command": "hyperopt_strategy",
                    "result_id": result_id,
                    "strategy": strategy_name,
                    "pairs": pairs,
                    "timerange": timerange,
                    "epochs": epochs,
                    "success": True,
                    "best_params": best_result.get('params', {}),
                    "best_metrics": {
                        "total_profit": best_result.get('results_metrics', {}).get('profit_total', 0.0),
                        "win_rate": best_result.get('results_metrics', {}).get('wins', 0) / max(best_result.get('results_metrics', {}).get('total_trades', 1), 1),
                        "total_trades": best_result.get('results_metrics', {}).get('total_trades', 0),
                        "avg_profit": best_result.get('results_metrics', {}).get('profit_mean', 0.0),
                    },
                    "trials_summary": {
                        "completed_trials": epochs,
                        "best_epoch": best_result.get('current_epoch', 0),
                    },
                    "detailed_results": hyperopt_results,
                    "method": "package"
                }
            else:
                raise ValueError("No hyperopt results returned")
                
        except Exception as e:
            logger.error(f"Package-based hyperopt failed: {e}")
            raise

    def _parse_hyperopt_output(
        self,
        output: str,
        strategy_name: str,
        pairs: List[str],
        timerange: str,
        epochs: int,
        result_id: str
    ) -> Dict[str, Any]:
        """Parse freqtrade hyperopt output into structured data."""
        lines = output.split('\n')
        
        # Initialize result structure
        result = {
            "command": "hyperopt_strategy",
            "result_id": result_id,
            "strategy": strategy_name,
            "pairs": pairs,
            "timerange": timerange,
            "epochs": epochs,
            "success": True,
            "best_params": {},
            "best_metrics": {},
            "trials_summary": {},
            "raw_output": output
        }

        # Parse best parameters and metrics
        in_best_params = False
        in_best_result = False
        current_section = None

        for line in lines:
            line_stripped = line.strip()
            
            # Look for best parameters section
            if "Best parameters:" in line or "Best result:" in line:
                if "Best parameters:" in line:
                    in_best_params = True
                    in_best_result = False
                    current_section = "params"
                elif "Best result:" in line:
                    in_best_params = False
                    in_best_result = True
                    current_section = "result"
                continue
            
            # Parse parameter lines
            if in_best_params and line_stripped and not line_stripped.startswith('-'):
                if ':' in line_stripped:
                    key, value = line_stripped.split(':', 1)
                    key = key.strip().replace('"', '').replace("'", "")
                    value = value.strip().replace(',', '')
                    
                    # Try to parse as number
                    try:
                        if '.' in value:
                            result["best_params"][key] = float(value)
                        else:
                            result["best_params"][key] = int(value)
                    except ValueError:
                        result["best_params"][key] = value.replace('"', '').replace("'", "")
            
            # Parse result metrics
            if in_best_result and line_stripped:
                # Look for key metrics
                if "Total profit" in line:
                    match = re.search(r"Total profit\s*[:\|]\s*([-+]?\d*\.?\d+)", line)
                    if match:
                        result["best_metrics"]["total_profit"] = float(match.group(1))
                
                if "Win  %" in line or "Win rate" in line:
                    match = re.search(r"Win\s*%?\s*[:\|]\s*(\d*\.?\d+)", line)
                    if match:
                        result["best_metrics"]["win_rate"] = float(match.group(1)) / 100.0
                
                if "Avg profit" in line:
                    match = re.search(r"Avg profit\s*[:\|]\s*([-+]?\d*\.?\d+)", line)
                    if match:
                        result["best_metrics"]["avg_profit"] = float(match.group(1))
                
                if "Total trades" in line:
                    match = re.search(r"Total trades\s*[:\|]\s*(\d+)", line)
                    if match:
                        result["best_metrics"]["total_trades"] = int(match.group(1))
            
            # Parse trials summary
            if "trials" in line.lower() and "completed" in line.lower():
                match = re.search(r"(\d+)\s+trials?\s+completed", line)
                if match:
                    result["trials_summary"]["completed_trials"] = int(match.group(1))

        return result

    def _find_hyperopt_results_file(self, result_id: str) -> str:
        """Find hyperopt results file."""
        # Check hyperopt results directory
        results_dir = self.config.full_hyperopt_results_dir
        
        # Look for hyperopt results files
        for results_file in results_dir.glob("*.json"):
            if result_id in results_file.name:
                return str(results_file)
        
        # Also check default freqtrade hyperopt location
        default_hyperopt_dir = self.config.freqtrade_path / "user_data" / "hyperopt_results"
        if default_hyperopt_dir.exists():
            for results_file in default_hyperopt_dir.glob(f"*{result_id}*.json"):
                return str(results_file)
        
        return None