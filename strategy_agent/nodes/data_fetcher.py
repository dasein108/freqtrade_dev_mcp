"""
Data fetching node for market data retrieval
"""

import hashlib
import json
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from ..logging_config import get_logger
from ..mcp_client import FreqtradeMCPClient
from ..response_utils import (
    get_error_message,
    is_successful_response,
)
from ..state import StrategyDevelopmentState

logger = logging.getLogger(__name__)
strategy_logger = get_logger()


class DataCache:
    """Simple cache for market data"""

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, symbol: str, timeframe: str, days: int) -> str:
        """Generate cache key for data"""
        key_str = f"{symbol}_{timeframe}_{days}days"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, symbol: str, timeframe: str, days: int) -> Any:
        """Get cached data if exists and not expired"""
        cache_key = self.get_cache_key(symbol, timeframe, days)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        meta_file = self.cache_dir / f"{cache_key}.meta"

        if cache_file.exists() and meta_file.exists():
            # Check if cache is still valid (less than 24 hours old)
            with open(meta_file, "r") as f:
                meta = json.load(f)

            cached_time = datetime.fromisoformat(meta["timestamp"])
            if datetime.now() - cached_time < timedelta(hours=24):
                with open(cache_file, "rb") as f:
                    return pickle.load(f)

        return None

    def set(self, symbol: str, timeframe: str, days: int, data: Any):
        """Cache data with metadata"""
        cache_key = self.get_cache_key(symbol, timeframe, days)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        meta_file = self.cache_dir / f"{cache_key}.meta"

        # Save data
        with open(cache_file, "wb") as f:
            pickle.dump(data, f)

        # Save metadata
        meta = {
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "timestamp": datetime.now().isoformat(),
        }
        with open(meta_file, "w") as f:
            json.dump(meta, f)


OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def read_ohlcv_cache_file(cache_path: Path) -> Dict[str, Dict[str, float]]:
    """
    Read a Freqtrade JSON candle file into column-oriented OHLCV data.

    Args:
        cache_path: Path to a Freqtrade JSON data file (rows of [timestamp_ms, o, h, l, c, v])

    Returns:
        Dict mapping column name (open/high/low/close/volume) to {iso_date: value}

    Raises:
        OSError: If the file cannot be read
        ValueError: If the file content is not a list of OHLCV rows
    """
    with open(cache_path, "r") as f:
        rows = json.load(f)

    if not isinstance(rows, list) or not rows or len(rows[0]) < len(OHLCV_COLUMNS):
        raise ValueError(f"Unexpected candle data format in {cache_path}")

    ohlcv: Dict[str, Dict[str, float]] = {column: {} for column in OHLCV_COLUMNS[1:]}
    for row in rows:
        date = datetime.utcfromtimestamp(row[0] / 1000).isoformat()
        for column, value in zip(OHLCV_COLUMNS[1:], row[1:6]):
            ohlcv[column][date] = float(value)
    return ohlcv


async def download_and_read_candles_from_mcp(
    mcp_client: FreqtradeMCPClient, symbol: str, timeframe: str, days: int = 365
) -> Dict[str, Any]:
    """
    Download candle data using MCP server and then read from cache files

    Args:
        mcp_client: Connected MCP client
        symbol: Trading pair symbol
        timeframe: Timeframe
        days: Number of days to fetch

    Returns:
        Dictionary with OHLCV data
    """
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Downloading {symbol} {timeframe} data for {days} days")

        # Step 1: Download candles (this returns cache filenames now)
        download_result = await mcp_client.download_candles(
            pairs=[symbol], timeframe=timeframe, days=days
        )

        # Enhanced result validation and logging
        if download_result is None:
            error_msg = f"MCP client returned None for {symbol} {timeframe}"
            logger.error(error_msg)
            strategy_logger.log_error(
                "Data download returned None",
                details={"symbol": symbol, "timeframe": timeframe, "days": days},
            )
            return None

        # Log the full result for debugging
        logger.debug(f"MCP download_candles result for {symbol} {timeframe}: {download_result}")

        # Parse the download result using response utilities
        if not is_successful_response(download_result):
            error_msg = get_error_message(download_result) or "Unknown MCP error"
            error_type = download_result.get("error_type", "Unknown")
            raw_content = download_result.get("raw_content", "")
            raw_result = download_result.get("raw_result", "")

            logger.error(f"MCP download error for {symbol} {timeframe}: {error_msg}")

            # Log detailed error information
            error_details = {
                "symbol": symbol,
                "timeframe": timeframe,
                "days": days,
                "error": error_msg,
                "error_type": error_type,
                "success": is_successful_response(download_result),
            }

            if raw_content:
                error_details["raw_content"] = raw_content[:500]  # Limit length
            if raw_result:
                error_details["raw_result"] = str(raw_result)[:500]  # Limit length
            if download_result.get("traceback"):
                error_details["server_traceback"] = download_result["traceback"][
                    :1000
                ]  # Limit length

            strategy_logger.log_error("MCP download_candles failed", details=error_details)
            return None

        # Step 2: Find the cache file for this symbol in the download result
        if isinstance(download_result, dict):
            results = download_result.get("results", [])
        else:
            results = download_result.results

        cache_paths = []
        for result in results:
            cache_file_infos = (
                result.get("cache_files", []) if isinstance(result, dict) else result.cache_files
            )
            for cache_file_info in cache_file_infos:
                pair = (
                    cache_file_info.get("pair")
                    if isinstance(cache_file_info, dict)
                    else cache_file_info.pair
                )
                full_path = (
                    cache_file_info.get("full_path")
                    if isinstance(cache_file_info, dict)
                    else cache_file_info.full_path
                )
                if pair == symbol and full_path:
                    cache_paths.append(Path(full_path))

        if not cache_paths:
            logger.error("No cache files found for %s %s", symbol, timeframe)
            return None

        # Step 3: Read candles directly from the cache file. The MCP server runs as a local
        # stdio subprocess, so the paths it returns are readable here.
        cache_path = cache_paths[0]
        try:
            ohlcv = read_ohlcv_cache_file(cache_path)
        except (OSError, ValueError) as e:
            logger.error("Failed to read cache file %s: %s", cache_path, e)
            strategy_logger.log_error(
                "Reading candle cache file failed",
                details={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "cache_file": str(cache_path),
                    "error": str(e),
                },
            )
            return None

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": ohlcv,
            "candle_count": len(ohlcv["close"]),
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "cache_file": str(cache_path),
        }

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"Error fetching candles: {str(e)}")
        logger.debug(f"Traceback: {error_trace}")
        return None


async def fetch_market_data(
    state: StrategyDevelopmentState, mcp_client: Optional[FreqtradeMCPClient] = None
) -> StrategyDevelopmentState:
    """
    Node: Fetch market data for all symbols and timeframes

    This node:
    1. Checks cache for existing data
    2. Fetches missing data from MCP
    3. Updates state with candle data

    Args:
        state: Current workflow state
        mcp_client: Optional MCP client instance (will use from state if not provided)
    """
    logger.info("Starting market data fetch")
    strategy_logger.set_phase("DATA FETCHING")
    strategy_logger.set_step("Market Data Collection")
    state["current_step"] = "fetch_market_data"

    # Get MCP client from state if not provided
    if mcp_client is None:
        mcp_client = state.get("mcp_client")
        if mcp_client is None:
            error_msg = "No MCP client available"
            state["errors"].append(error_msg)
            strategy_logger.log_error(error_msg)
            return state

    # Initialize cache
    cache = DataCache(cache_dir="./cache")

    # Initialize candle data storage
    candle_data = {}
    fetch_errors = []

    # Track fetch progress
    total_combinations = len(state["symbols"]) * len(state["timeframes"])
    fetched = 0
    cached = 0

    # Fetch data for each symbol/timeframe combination
    for symbol in state["symbols"]:
        candle_data[symbol] = {}

        for timeframe in state["timeframes"]:
            logger.info(f"Fetching {symbol} {timeframe}")
            strategy_logger.log_progress(
                f"Fetching {symbol} {timeframe}", fetched + cached, total_combinations
            )

            # Check cache first
            cached_data = cache.get(symbol, timeframe, days=365)

            if cached_data:
                logger.info(f"Using cached data for {symbol} {timeframe}")
                logger.debug(
                    f"Cached data structure: {list(cached_data.keys()) if isinstance(cached_data, dict) else type(cached_data)}"
                )

                # Debug: Check if cached data has expected structure
                if isinstance(cached_data, dict):
                    if "data" in cached_data:
                        data_keys = (
                            list(cached_data["data"].keys())
                            if isinstance(cached_data["data"], dict)
                            else "not dict"
                        )
                        logger.debug(f"Cached data.data keys: {data_keys}")

                        # Count candles in cached data for debugging
                        if isinstance(cached_data["data"], dict) and "close" in cached_data["data"]:
                            cached_candle_count = (
                                len(cached_data["data"]["close"])
                                if isinstance(cached_data["data"]["close"], dict)
                                else 0
                            )
                            logger.info(
                                f"Cached data contains {cached_candle_count} candles for {symbol} {timeframe}"
                            )

                candle_data[symbol][timeframe] = cached_data
                cached += 1
            else:
                # Fetch from MCP
                logger.info(f"Downloading {symbol} {timeframe} from MCP")

                data = await download_and_read_candles_from_mcp(
                    mcp_client, symbol, timeframe, days=365
                )

                if data:
                    candle_data[symbol][timeframe] = data
                    cache.set(symbol, timeframe, days=365, data=data)
                    fetched += 1
                    logger.info(
                        f"Successfully fetched {data['candle_count']} candles for {symbol} {timeframe}"
                    )
                    strategy_logger.log_data(
                        logging.INFO,
                        f"Fetched {symbol} {timeframe}",
                        {"candles": data["candle_count"], "cached": False},
                    )
                else:
                    error_msg = f"Failed to fetch {symbol} {timeframe}"
                    fetch_errors.append(error_msg)
                    logger.error(error_msg)
                    strategy_logger.log_error(f"Data fetch failed: {error_msg}")

                    # Use empty data as fallback
                    candle_data[symbol][timeframe] = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "data": {},
                        "candle_count": 0,
                        "error": "Failed to fetch",
                    }

    # Update state
    state["candle_data"] = candle_data
    state["data_cached"] = cached > 0
    state["data_fetch_timestamp"] = datetime.now()

    # Add any errors to state
    if fetch_errors:
        state["errors"].extend(fetch_errors)
        state["warnings"].append(f"Failed to fetch {len(fetch_errors)} data combinations")

    # Log summary
    logger.info(
        f"Data fetch complete: {fetched} fetched, {cached} from cache, {len(fetch_errors)} errors"
    )
    strategy_logger.log_success(
        "Data fetch completed",
        {
            "fetched": fetched,
            "cached": cached,
            "errors": len(fetch_errors),
            "total_candles": sum(
                data.get("candle_count", 0)
                for symbol_data in candle_data.values()
                for data in symbol_data.values()
            ),
        },
    )

    # Validate we have enough data to continue
    total_candles = 0
    for symbol_data in candle_data.values():
        for data in symbol_data.values():
            # Handle both cached data (without candle_count) and fresh MCP data (with candle_count)
            candle_count = data.get("candle_count", 0)

            # If no candle_count field, calculate from actual data structure
            if candle_count == 0 and "data" in data and isinstance(data["data"], dict):
                # Count candles from the data structure (e.g., length of 'close' prices)
                if "close" in data["data"] and isinstance(data["data"]["close"], dict):
                    candle_count = len(data["data"]["close"])
                elif isinstance(data["data"], list):
                    candle_count = len(data["data"])

            total_candles += candle_count

    if total_candles == 0:
        error_msg = "No candle data available for any symbol/timeframe"
        state["errors"].append(error_msg)
        state["current_step"] = "error"
        logger.error("No candle data available, cannot continue")
        strategy_logger.log_error(error_msg)
    else:
        logger.info(f"Total candles available: {total_candles}")

        # Add summary to state
        state["analysis_summary"] = (
            f"Fetched data for {len(state['symbols'])} symbols across "
            f"{len(state['timeframes'])} timeframes. Total candles: {total_candles}"
        )

    return state


async def validate_data_quality(candle_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the quality of fetched candle data

    Returns:
        Dictionary with validation results
    """
    validation = {"is_valid": True, "issues": [], "statistics": {}}

    if not candle_data or candle_data.get("candle_count", 0) == 0:
        validation["is_valid"] = False
        validation["issues"].append("No candle data available")
        return validation

    # Check for data gaps
    data = candle_data.get("data", {})
    if isinstance(data, dict) and "close" in data:
        closes = data["close"]

        # Check for NaN or null values
        if any(v is None or (isinstance(v, float) and v != v) for v in closes.values()):
            validation["issues"].append("Data contains null or NaN values")

        # Calculate basic statistics
        if closes:
            prices = list(closes.values())
            # Filter out None and NaN values for statistics calculation
            valid_prices = [
                p for p in prices if p is not None and (not isinstance(p, float) or p == p)
            ]

            if valid_prices:
                validation["statistics"] = {
                    "min_price": min(valid_prices),
                    "max_price": max(valid_prices),
                    "avg_price": sum(valid_prices) / len(valid_prices),
                    "data_points": len(prices),  # Total data points including nulls
                    "valid_data_points": len(valid_prices),  # Only valid data points
                }
            else:
                validation["statistics"] = {
                    "min_price": None,
                    "max_price": None,
                    "avg_price": None,
                    "data_points": len(prices),
                    "valid_data_points": 0,
                }

    return validation
