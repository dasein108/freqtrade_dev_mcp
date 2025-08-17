"""List results command implementation."""

import logging
from typing import Any, Dict, List, Optional

try:
    from .base import BaseCommand
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand

logger = logging.getLogger(__name__)


class ListResultsCommand(BaseCommand):
    """Command to list available backtest and hyperopt results."""

    async def execute(
        self,
        result_type: str = "all",
        strategy: Optional[str] = None,
        limit: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute list results command.
        
        Args:
            result_type: Type of results to list ("backtest", "hyperopt", "all")
            strategy: Filter by strategy name
            limit: Maximum number of results to return
            
        Returns:
            List of available results with metadata
        """
        try:
            # Validate result_type
            valid_types = ["backtest", "hyperopt", "all"]
            if result_type not in valid_types:
                return {
                    "command": "list_results",
                    "success": False,
                    "error": f"Invalid result_type. Must be one of: {valid_types}"
                }

            # Get results from base class
            all_results = self.list_saved_results(
                result_type if result_type != "all" else None
            )

            # Filter by strategy if specified
            if strategy:
                all_results = [
                    r for r in all_results 
                    if r.get("strategy", "").lower() == strategy.lower()
                ]

            # Apply limit
            results = all_results[:limit]

            # Add summary statistics
            summary = self._generate_summary(all_results, result_type)

            return {
                "command": "list_results",
                "success": True,
                "filter": {
                    "result_type": result_type,
                    "strategy": strategy,
                    "limit": limit
                },
                "summary": summary,
                "results": results,
                "total_found": len(all_results),
                "returned": len(results)
            }

        except Exception as e:
            logger.error(f"List results command failed: {e}", exc_info=True)
            return {
                "command": "list_results",
                "success": False,
                "error": str(e)
            }

    def _generate_summary(self, results: List[Dict[str, Any]], result_type: str) -> Dict[str, Any]:
        """Generate summary statistics for results."""
        summary = {
            "total_results": len(results),
            "by_type": {},
            "by_strategy": {},
            "date_range": {}
        }

        # Count by type
        for result in results:
            res_type = result.get("type", "unknown")
            summary["by_type"][res_type] = summary["by_type"].get(res_type, 0) + 1

        # Count by strategy
        for result in results:
            strategy = result.get("strategy", "unknown")
            summary["by_strategy"][strategy] = summary["by_strategy"].get(strategy, 0) + 1

        # Find date range
        dates = [r.get("created_at") for r in results if r.get("created_at")]
        if dates:
            dates.sort()
            summary["date_range"] = {
                "earliest": dates[0],
                "latest": dates[-1]
            }

        return summary