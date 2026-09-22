"""Base command class for MCP server commands."""

import asyncio
import json
import logging
import os
import re
import shutil
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
    from freqtrade.configuration import Configuration  # noqa: F401
    from freqtrade.data.history import get_timerange, load_pair_history  # noqa: F401
    from freqtrade.resolvers import StrategyResolver

    FREQTRADE_AVAILABLE = True
except ImportError:
    # Don't log during import as it interferes with MCP protocol
    # The warning will be logged later when commands are actually used
    FREQTRADE_AVAILABLE = False

STRATEGY_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
RESULT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")

# Fallback locations searched when `freqtrade` is not on PATH
FREQTRADE_FALLBACK_DIRS = [
    "~/miniconda3/bin",
    "~/anaconda3/bin",
    "~/.local/bin",
    "/usr/local/bin",
    "/opt/homebrew/bin",
]


def validate_strategy_name(strategy_name: str) -> str:
    """Validate a strategy name so it is a safe Python identifier and file name.

    Raises:
        ValueError: If the name is not a valid identifier.
    """
    if not isinstance(strategy_name, str) or not STRATEGY_NAME_PATTERN.match(strategy_name):
        raise ValueError(
            f"Invalid strategy name {strategy_name!r}: use letters, digits and underscores, "
            "starting with a letter or underscore"
        )
    return strategy_name


def validate_result_id(result_id: str) -> str:
    """Validate a result ID so it cannot escape the results directories.

    Raises:
        ValueError: If the ID contains path separators or other unsafe characters.
    """
    if (
        not isinstance(result_id, str)
        or not RESULT_ID_PATTERN.match(result_id)
        or ".." in result_id
    ):
        raise ValueError(f"Invalid result ID {result_id!r}")
    return result_id


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

    def resolve_workspace_path(self, path: str) -> Path:
        """Resolve a user-supplied path and ensure it stays inside the Freqtrade root.

        Relative paths are resolved against `config.freqtrade_path`.

        Raises:
            ValueError: If the resolved path is outside the Freqtrade root.
        """
        root = self.config.freqtrade_path.expanduser().resolve()
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"Path {resolved} is outside the Freqtrade root {root}")
        return resolved

    def get_freqtrade_config(self) -> Dict[str, Any]:
        """Get basic freqtrade configuration."""
        config = {
            "user_data_dir": self.config.freqtrade_path / "user_data",
            "strategy_path": str(self.config.full_strategy_dir),
            "datadir": self.config.full_data_dir,
        }
        return config

    def validate_strategy(self, strategy_name: str) -> bool:
        """Validate that a strategy exists."""
        if FREQTRADE_AVAILABLE:
            try:
                # Use freqtrade's strategy resolver
                config = self.get_freqtrade_config()
                config["strategy"] = strategy_name  # Set strategy name in config
                StrategyResolver.load_strategy(config)  # Load with just config
                return True
            except Exception as e:
                logger.debug(f"Strategy validation failed for '{strategy_name}': {e}")
                return False
        else:
            # Fallback to file check
            strategy_file = self.config.full_strategy_dir / f"{strategy_name}.py"
            return strategy_file.exists()

    async def run_freqtrade_command(
        self, args: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run a freqtrade command and return structured output."""
        if cwd is None:
            cwd = self.config.freqtrade_path

        # Look up freqtrade on PATH first, then in common install locations
        env = os.environ.copy()
        fallback_dirs = [os.path.expanduser(d) for d in FREQTRADE_FALLBACK_DIRS]
        search_path = os.pathsep.join([env.get("PATH", "")] + fallback_dirs)
        freqtrade_cmd = shutil.which("freqtrade", path=search_path) or "freqtrade"
        env["PATH"] = search_path

        cmd = [freqtrade_cmd] + args

        try:
            await self.mcp_log("info", f"Running command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            if timeout:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
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
                "success": success,
            }

        except asyncio.TimeoutError:
            logger.error(f"Command timeout: {' '.join(cmd)}")
            process.kill()
            return {"returncode": -1, "stdout": "", "stderr": "timeout", "success": False}
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {"returncode": -1, "stdout": "", "stderr": str(e), "success": False}

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
        validate_result_id(result_id)
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

        For CLI tools, returncode 0 means success regardless of stderr content,
        as many tools output logging/progress info to stderr during normal operation.
        """
        # Trust the exit code - returncode 0 means success
        # Many CLI tools output progress/logging to stderr even when successful
        return returncode == 0
