"""Get result command implementation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .base import BaseCommand
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand

logger = logging.getLogger(__name__)


class GetResultCommand(BaseCommand):
    """Command to retrieve a specific result by ID."""

    async def execute(
        self,
        result_id: str,
        include_metadata: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute get result command.
        
        Args:
            result_id: ID of the result to retrieve
            include_metadata: Include metadata in response
            
        Returns:
            Result data with optional metadata
        """
        try:
            # Load the main result data
            result_data = self.load_result(result_id)
            
            if not result_data:
                return {
                    "command": "get_result",
                    "success": False,
                    "error": f"Result with ID '{result_id}' not found"
                }

            response = {
                "command": "get_result",
                "success": True,
                "result_id": result_id,
                "data": result_data
            }

            # Add metadata if requested
            if include_metadata:
                metadata = self._load_metadata(result_id)
                if metadata:
                    response["metadata"] = metadata

            # Add file information if available
            file_info = self._get_file_info(result_id, result_data)
            if file_info:
                response["files"] = file_info

            return response

        except Exception as e:
            logger.error(f"Get result command failed: {e}", exc_info=True)
            return {
                "command": "get_result",
                "success": False,
                "error": str(e),
                "result_id": result_id
            }

    def _load_metadata(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Load metadata for a result."""
        # Try backtest metadata first
        meta_file = self.config.full_backtest_results_dir / f"{result_id}.meta.json"
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load backtest metadata {meta_file}: {e}")

        # Try hyperopt metadata
        meta_file = self.config.full_hyperopt_results_dir / f"{result_id}.meta.json"
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load hyperopt metadata {meta_file}: {e}")

        return None

    def _get_file_info(self, result_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get information about related files."""
        files = {}

        # Check for exported trade files
        if "trades_file" in result_data and result_data["trades_file"]:
            trades_path = Path(result_data["trades_file"])
            if trades_path.exists():
                files["trades"] = {
                    "path": str(trades_path),
                    "size": trades_path.stat().st_size,
                    "exists": True
                }
            else:
                files["trades"] = {
                    "path": str(trades_path),
                    "exists": False
                }

        # Check for exported signal files
        if "signals_file" in result_data and result_data["signals_file"]:
            signals_path = Path(result_data["signals_file"])
            if signals_path.exists():
                files["signals"] = {
                    "path": str(signals_path),
                    "size": signals_path.stat().st_size,
                    "exists": True
                }
            else:
                files["signals"] = {
                    "path": str(signals_path),
                    "exists": False
                }

        # Check for hyperopt results file
        if "results_file" in result_data and result_data["results_file"]:
            results_path = Path(result_data["results_file"])
            if results_path.exists():
                files["hyperopt_results"] = {
                    "path": str(results_path),
                    "size": results_path.stat().st_size,
                    "exists": True
                }
            else:
                files["hyperopt_results"] = {
                    "path": str(results_path),
                    "exists": False
                }

        return files