"""Download candles command implementation."""

import logging
from typing import Any, Dict, List, Union

try:
    from .base import BaseCommand, FREQTRADE_AVAILABLE
    from ..utils.date_parser import parse_and_format_date
    from ..utils.coingecko import CoinGeckoClient
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand, FREQTRADE_AVAILABLE
    from utils.date_parser import parse_and_format_date
    from utils.coingecko import CoinGeckoClient

# Import freqtrade modules for package-based functionality
if FREQTRADE_AVAILABLE:
    try:
        from freqtrade.data.history import download_pair_history
        from freqtrade.exchange import get_exchange_class
        from freqtrade.constants import AVAILABLE_DATAHANDLERS
    except ImportError:
        FREQTRADE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DownloadCandlesCommand(BaseCommand):
    """Command to download historical candle data."""

    def __init__(self, config, server=None):
        """Initialize download candles command."""
        super().__init__(config, server)
        self.coingecko_client = CoinGeckoClient(
            api_key=config.coingecko_api_key,
            is_demo=True
        )

    async def execute(
        self,
        pairs: Union[List[str], str],
        timeframes: Union[List[str], str],
        date_range: str,
        exchange: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute download candles command.
        
        Args:
            pairs: List of trading pairs or "top15" for market cap selection
            timeframes: List of timeframes or "all" for standard timeframes
            date_range: Natural language date range
            exchange: Exchange name (defaults to config default)
            
        Returns:
            Command execution result
        """
        try:
            # Set default exchange
            if exchange is None:
                exchange = self.config.default_exchange

            # Parse date range
            timerange = parse_and_format_date(date_range)
            logger.info(f"Parsed date range '{date_range}' to timerange: {timerange}")

            # Process pairs
            pairs_list = await self._process_pairs(pairs, exchange)
            
            # Process timeframes
            timeframes_list = self._process_timeframes(timeframes)
            
            # Validate that we have data directory
            self.config.full_data_dir.mkdir(parents=True, exist_ok=True)

            # Build and execute freqtrade download command
            results = []
            for timeframe in timeframes_list:
                result = await self._download_for_timeframe(
                    pairs_list, timeframe, timerange, exchange
                )
                results.append(result)

            # Compile final result
            successful_downloads = [r for r in results if r["success"]]
            failed_downloads = [r for r in results if not r["success"]]

            return {
                "command": "download_candles",
                "exchange": exchange,
                "pairs": pairs_list,
                "timeframes": timeframes_list,
                "date_range": date_range,
                "timerange": timerange,
                "total_downloads": len(results),
                "successful": len(successful_downloads),
                "failed": len(failed_downloads),
                "results": results,
                "success": len(failed_downloads) == 0
            }

        except Exception as e:
            logger.error(f"Download candles command failed: {e}", exc_info=True)
            return {
                "command": "download_candles",
                "success": False,
                "error": str(e),
                "details": {
                    "pairs": pairs,
                    "timeframes": timeframes,
                    "date_range": date_range,
                    "exchange": exchange
                }
            }

    async def _process_pairs(self, pairs: Union[List[str], str], exchange: str) -> List[str]:
        """Process pairs parameter into list of trading pairs."""
        if isinstance(pairs, str):
            if pairs.lower() == "top15":
                logger.info("Fetching top 15 coins by market cap")
                try:
                    pairs_list = await self.coingecko_client.get_top_trading_pairs(
                        limit=15, exchange=exchange
                    )
                    logger.info(f"Got {len(pairs_list)} top trading pairs")
                    return pairs_list
                except Exception as e:
                    logger.error(f"Failed to fetch top pairs: {e}")
                    # Fallback to common pairs
                    return [
                        "BTC/USDT", "ETH/USDT", "BNB/USDT", "ADA/USDT", "SOL/USDT",
                        "XRP/USDT", "DOT/USDT", "DOGE/USDT", "AVAX/USDT", "SHIB/USDT",
                        "LUNA/USDT", "LTC/USDT", "LINK/USDT", "UNI/USDT", "ALGO/USDT"
                    ]
            else:
                # Single pair as string
                return [pairs]
        else:
            # List of pairs
            return pairs

    def _process_timeframes(self, timeframes: Union[List[str], str]) -> List[str]:
        """Process timeframes parameter into list of timeframes."""
        if isinstance(timeframes, str):
            if timeframes.lower() == "all":
                return ["5m", "15m", "30m", "1h", "4h", "1d"]
            else:
                return [timeframes]
        else:
            return timeframes

    async def _download_for_timeframe(
        self, 
        pairs: List[str], 
        timeframe: str, 
        timerange: str, 
        exchange: str
    ) -> Dict[str, Any]:
        """Download data for specific timeframe."""
        await self.mcp_log("info", f"Downloading {timeframe} data for {len(pairs)} pairs on {exchange}")
        
        if FREQTRADE_AVAILABLE:
            # Use freqtrade package functions for better performance
            try:
                await self.mcp_log("info", "Using freqtrade package for download")
                return await self._download_using_package(pairs, timeframe, timerange, exchange)
            except Exception as e:
                await self.mcp_log("warning", f"Package-based download failed, falling back to CLI: {e}")
        else:
            await self.mcp_log("warning", "Freqtrade package not available, using CLI mode")
        
        # Fallback to CLI mode
        return await self._download_using_cli(pairs, timeframe, timerange, exchange)

    async def _download_using_package(
        self, 
        pairs: List[str], 
        timeframe: str, 
        timerange: str, 
        exchange: str
    ) -> Dict[str, Any]:
        """Download using freqtrade package functions."""
        import asyncio
        from freqtrade.data.history import get_timerange
        
        await self.mcp_log("info", f"Setting up freqtrade config for {exchange}")
        
        try:
            config = self.get_freqtrade_config()
            config.update({
                'exchange': {
                    'name': exchange,
                    'ccxt_config': {},
                    'ccxt_async_config': {},
                },
                'datadir': str(self.config.full_data_dir),
            })
            
            await self.mcp_log("info", f"Data directory: {self.config.full_data_dir}")
            
            # Get exchange instance
            exchange_class = get_exchange_class(exchange)
            exchange_instance = exchange_class(config)
            
            await self.mcp_log("info", f"Created {exchange} exchange instance")
            
            # Parse timerange
            timerange_obj = get_timerange(timerange)
            await self.mcp_log("info", f"Parsed timerange: {timerange} -> {timerange_obj}")
            
            # Ensure data directory exists
            self.config.full_data_dir.mkdir(parents=True, exist_ok=True)
            
            successful_pairs = []
            failed_pairs = []
            
            for pair in pairs:
                try:
                    await self.mcp_log("info", f"Starting download for {pair}")
                    # Download pair history using freqtrade package
                    await asyncio.to_thread(
                        download_pair_history,
                        datadir=self.config.full_data_dir,
                        exchange=exchange_instance,
                        pair=pair,
                        timeframe=timeframe,
                        timerange=timerange_obj,
                        candle_type='spot'
                    )
                    successful_pairs.append(pair)
                    await self.mcp_log("info", f"Successfully downloaded {pair} {timeframe} data")
                except Exception as e:
                    failed_pairs.append((pair, str(e)))
                    await self.mcp_log("error", f"Failed to download {pair}: {e}")
                    
        except Exception as e:
            await self.mcp_log("error", f"Package setup failed: {e}")
            raise
        
        success = len(failed_pairs) == 0
        output_lines = [f"Downloaded {len(successful_pairs)} pairs successfully"]
        if failed_pairs:
            output_lines.append(f"Failed to download {len(failed_pairs)} pairs")
            
        return {
            "timeframe": timeframe,
            "pairs_count": len(pairs),
            "pairs": pairs,
            "successful_pairs": successful_pairs,
            "failed_pairs": failed_pairs,
            "success": success,
            "returncode": 0 if success else 1,
            "output": "\n".join(output_lines),
            "error": None if success else f"Failed pairs: {[p[0] for p in failed_pairs]}"
        }

    async def _download_using_cli(
        self, 
        pairs: List[str], 
        timeframe: str, 
        timerange: str, 
        exchange: str
    ) -> Dict[str, Any]:
        """Download using CLI commands (fallback)."""
        await self.mcp_log("info", "Attempting CLI download with freqtrade command")
        
        # First check if freqtrade command is available
        try:
            import shutil
            freqtrade_path = shutil.which("freqtrade")
            if not freqtrade_path:
                await self.mcp_log("error", "freqtrade command not found in PATH. Please install freqtrade or ensure it's in your PATH")
                return {
                    "timeframe": timeframe,
                    "pairs_count": len(pairs),
                    "pairs": pairs,
                    "success": False,
                    "returncode": -1,
                    "output": "",
                    "error": "freqtrade command not found in PATH. Please install freqtrade CLI or ensure it's accessible."
                }
            else:
                await self.mcp_log("info", f"Found freqtrade command at: {freqtrade_path}")
        except Exception as e:
            await self.mcp_log("error", f"Error checking freqtrade command: {e}")
        
        # Build freqtrade download-data command
        args = [
            "download-data",
            "--exchange", exchange,
            "--timeframes", timeframe,
            "--timerange", timerange,
        ]
        
        # Add pairs
        for pair in pairs:
            args.extend(["--pairs", pair])

        # Execute command
        result = await self.run_freqtrade_command(args, timeout=600)  # 10 minute timeout
        
        if not result["success"]:
            await self.mcp_log("error", f"CLI download failed: {result['stderr']}")
        else:
            await self.mcp_log("info", "CLI download completed successfully")
        
        return {
            "timeframe": timeframe,
            "pairs_count": len(pairs),
            "pairs": pairs,
            "success": result["success"],
            "returncode": result["returncode"],
            "output": result["stdout"],
            "error": result["stderr"] if not result["success"] else None
        }