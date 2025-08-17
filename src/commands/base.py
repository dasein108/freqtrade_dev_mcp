"""Base command class for MCP server commands."""

import asyncio
import json
import logging
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ..config import Config
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import Config

logger = logging.getLogger(__name__)

try:
    # Import freqtrade modules
    from freqtrade.configuration import Configuration
    from freqtrade.data.history import get_timerange, load_pair_history
    from freqtrade.resolvers import StrategyResolver
    FREQTRADE_AVAILABLE = True
except ImportError:
    # Don't log during import as it interferes with MCP protocol
    # The warning will be logged later when commands are actually used
    FREQTRADE_AVAILABLE = False


class BaseCommand(ABC):
    """Base class for all MCP commands."""

    def __init__(self, config: Config, server=None):
        """Initialize command with configuration."""
        self.config = config
        self.server = server

    async def mcp_log(self, level: str, message: str):
        """Log message via MCP if available, otherwise use standard logging."""
        if self.server:
            try:
                if level == "info":
                    await self.server.log_info(message)
                elif level == "warning":
                    await self.server.log_warning(message)
                elif level == "error":
                    await self.server.log_error(message)
            except Exception:
                # Fallback to standard logging
                getattr(logger, level, logger.info)(message)
        else:
            getattr(logger, level, logger.info)(message)

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the command with given parameters."""
        pass

    def get_freqtrade_config(self) -> Dict[str, Any]:
        """Get basic freqtrade configuration."""
        config = {
            "user_data_dir": str(self.config.freqtrade_path / "user_data"),
            "strategy_path": [str(self.config.full_strategy_dir)],
            "datadir": str(self.config.full_data_dir),
        }
        return config

    def validate_strategy(self, strategy_name: str) -> bool:
        """Validate that a strategy exists."""
        if FREQTRADE_AVAILABLE:
            try:
                # Use freqtrade's strategy resolver
                config = self.get_freqtrade_config()
                StrategyResolver.load_strategy(config, strategy_name)
                return True
            except Exception:
                return False
        else:
            # Fallback to file check
            strategy_file = self.config.full_strategy_dir / f"{strategy_name}.py"
            return strategy_file.exists()

    async def run_freqtrade_command(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run a freqtrade command and return structured output."""
        if cwd is None:
            cwd = self.config.freqtrade_path

        # Try multiple ways to find freqtrade
        freqtrade_cmd = "freqtrade"
        
        # First, check if freqtrade is available in PATH
        import shutil
        import os
        
        freqtrade_path = shutil.which("freqtrade")
        if not freqtrade_path:
            # Try common conda/pip installation paths
            possible_paths = [
                "/Users/dasein/miniconda3/bin/freqtrade",
                "~/.local/bin/freqtrade",
                "/usr/local/bin/freqtrade",
            ]
            
            for path in possible_paths:
                expanded_path = os.path.expanduser(path)
                if os.path.isfile(expanded_path) and os.access(expanded_path, os.X_OK):
                    freqtrade_cmd = expanded_path
                    break
            else:
                # Still not found, will try with just "freqtrade" and let it fail
                pass

        cmd = [freqtrade_cmd] + args
        
        # Set up environment with extended PATH
        env = os.environ.copy()
        # Add common binary paths to PATH
        additional_paths = [
            "/Users/dasein/miniconda3/bin",
            "~/.local/bin",
            "/usr/local/bin",
        ]
        
        current_path = env.get("PATH", "")
        for path in additional_paths:
            expanded_path = os.path.expanduser(path)
            if expanded_path not in current_path:
                current_path = f"{expanded_path}:{current_path}"
        env["PATH"] = current_path
        
        try:
            await self.mcp_log("info", f"Running command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            if timeout:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            else:
                stdout, stderr = await process.communicate()
            
            stdout_str = stdout.decode("utf-8")
            stderr_str = stderr.decode("utf-8")
            
            # Determine success based on returncode and stderr analysis
            success = self._analyze_command_success(process.returncode, stdout_str, stderr_str)
            
            return {
                "returncode": process.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "success": success
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Command timeout: {' '.join(cmd)}")
            process.kill()
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out",
                "success": False
            }
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }

    def generate_result_id(self, command_type: str, strategy: str = "") -> str:
        """Generate a unique result ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if strategy:
            return f"{command_type}_{strategy}_{timestamp}"
        return f"{command_type}_{timestamp}"

    def save_result(self, result_data: Dict[str, Any], result_id: str, result_type: str):
        """Save result to file with metadata."""
        if result_type == "backtest":
            results_dir = self.config.full_backtest_results_dir
        elif result_type == "hyperopt":
            results_dir = self.config.full_hyperopt_results_dir
        else:
            raise ValueError(f"Unknown result type: {result_type}")

        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Save main result
        result_file = results_dir / f"{result_id}.json"
        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2, default=str)
        
        # Save metadata
        metadata = {
            "id": result_id,
            "type": result_type,
            "created_at": datetime.now().isoformat(),
            "file_path": str(result_file),
            "size": result_file.stat().st_size,
        }
        
        if "strategy" in result_data:
            metadata["strategy"] = result_data["strategy"]
        if "pairs" in result_data:
            metadata["pairs"] = result_data["pairs"]
        if "timerange" in result_data:
            metadata["timerange"] = result_data["timerange"]
            
        meta_file = results_dir / f"{result_id}.meta.json"
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved {result_type} result: {result_id}")

    def list_saved_results(self, result_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all saved results."""
        results = []
        
        dirs_to_check = []
        if result_type == "backtest" or result_type is None:
            dirs_to_check.append(("backtest", self.config.full_backtest_results_dir))
        if result_type == "hyperopt" or result_type is None:
            dirs_to_check.append(("hyperopt", self.config.full_hyperopt_results_dir))
        
        for dir_type, results_dir in dirs_to_check:
            if not results_dir.exists():
                continue
                
            for meta_file in results_dir.glob("*.meta.json"):
                try:
                    with open(meta_file) as f:
                        metadata = json.load(f)
                    results.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to read metadata {meta_file}: {e}")
        
        # Sort by creation time, newest first
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def load_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Load a specific result by ID."""
        # Try backtest results first
        result_file = self.config.full_backtest_results_dir / f"{result_id}.json"
        if result_file.exists():
            with open(result_file) as f:
                return json.load(f)
        
        # Try hyperopt results
        result_file = self.config.full_hyperopt_results_dir / f"{result_id}.json"
        if result_file.exists():
            with open(result_file) as f:
                return json.load(f)
        
        return None

    def _analyze_command_success(self, returncode: int, stdout: str, stderr: str) -> bool:
        """Analyze command output to determine actual success state.
        
        Simple rule: if stderr has content but stdout is empty, command failed.
        """
        # Exit code failure is definitive
        if returncode != 0:
            return False
        
        # Simple rule: stderr with content but no stdout = failure
        if stderr.strip() and not stdout.strip():
            return False
        
        # Otherwise, trust the exit code
        return True