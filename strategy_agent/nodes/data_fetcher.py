"""
Data fetching node for market data retrieval
"""
import os
import json
import pickle
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import hashlib

from ..state import StrategyDevelopmentState
from ..mcp_client import FreqtradeMCPClient
from ..logging_config import get_logger
from ..response_utils import (
    is_successful_response,
    get_error_message,
    extract_cache_files
)

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
            with open(meta_file, 'r') as f:
                meta = json.load(f)
            
            cached_time = datetime.fromisoformat(meta['timestamp'])
            if datetime.now() - cached_time < timedelta(hours=24):
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
        
        return None
    
    def set(self, symbol: str, timeframe: str, days: int, data: Any):
        """Cache data with metadata"""
        cache_key = self.get_cache_key(symbol, timeframe, days)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        meta_file = self.cache_dir / f"{cache_key}.meta"
        
        # Save data
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
        
        # Save metadata
        meta = {
            'symbol': symbol,
            'timeframe': timeframe,
            'days': days,
            'timestamp': datetime.now().isoformat()
        }
        with open(meta_file, 'w') as f:
            json.dump(meta, f)


async def download_and_read_candles_from_mcp(
    mcp_client: FreqtradeMCPClient,
    symbol: str,
    timeframe: str,
    days: int = 365
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
            pairs=[symbol],
            timeframe=timeframe,
            days=days
        )
        
        # Enhanced result validation and logging
        if download_result is None:
            error_msg = f"MCP client returned None for {symbol} {timeframe}"
            logger.error(error_msg)
            strategy_logger.log_error(f"Data download returned None", details={
                "symbol": symbol,
                "timeframe": timeframe,
                "days": days
            })
            return None
        
        # Log the full result for debugging
        logger.debug(f"MCP download_candles result for {symbol} {timeframe}: {download_result}")
        
        # Parse the download result using response utilities
        if not is_successful_response(download_result):
            error_msg = get_error_message(download_result) or 'Unknown MCP error'
            error_type = download_result.get('error_type', 'Unknown')
            raw_content = download_result.get('raw_content', '')
            raw_result = download_result.get('raw_result', '')
            
            logger.error(f"MCP download error for {symbol} {timeframe}: {error_msg}")
            
            # Log detailed error information
            error_details = {
                "symbol": symbol,
                "timeframe": timeframe,
                "days": days,
                "error": error_msg,
                "error_type": error_type,
                "success": is_successful_response(download_result)
            }
            
            if raw_content:
                error_details["raw_content"] = raw_content[:500]  # Limit length
            if raw_result:
                error_details["raw_result"] = str(raw_result)[:500]  # Limit length
            if download_result.get("traceback"):
                error_details["server_traceback"] = download_result["traceback"][:1000]  # Limit length
                
            strategy_logger.log_error(f"MCP download_candles failed", details=error_details)
            return None
        
        # Step 2: Extract cache filenames from download result using utility
        all_cache_files = extract_cache_files(download_result)
        
        # Filter for the specific symbol we're looking for
        cache_files = []
        if isinstance(download_result, dict):
            results = download_result.get("results", [])
        else:
            results = download_result.results
            
        for result in results:
            cache_file_infos = result.get("cache_files", []) if isinstance(result, dict) else result.cache_files
            for cache_file_info in cache_file_infos:
                pair = cache_file_info.get("pair") if isinstance(cache_file_info, dict) else cache_file_info.pair
                filename = cache_file_info.get("filename") if isinstance(cache_file_info, dict) else cache_file_info.filename
                if pair == symbol and filename:
                    cache_files.append(filename)
        
        if not cache_files:
            logger.error(f"No cache files found for {symbol} {timeframe}")
            return None
        
        logger.info(f"Found {len(cache_files)} cache files for {symbol} {timeframe}: {cache_files}")
        
        # Step 3: Read candles from cache files
        read_result = await mcp_client.read_candles(cache_files)
        
        if not read_result or not is_successful_response(read_result):
            error_msg = get_error_message(read_result) or 'Failed to read cache files'
            logger.error(f"Failed to read cache files for {symbol} {timeframe}: {error_msg}")
            strategy_logger.log_error(f"MCP read_candles failed", details={
                "symbol": symbol,
                "timeframe": timeframe,
                "cache_files": cache_files,
                "error": error_msg
            })
            return None
        
        # Step 4: Extract data for the specific symbol/timeframe using utility
        candle_data = extract_candle_data(read_result)
        symbol_data = candle_data.get(symbol, {})
        timeframe_data = symbol_data.get(timeframe, {})
        
        if not timeframe_data:
            logger.error(f"No data found for {symbol} {timeframe} in read result")
            return None
        
        # Return in expected format
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": timeframe_data.get("data", {}),
            "candle_count": timeframe_data.get("candle_count", 0),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "cache_file": timeframe_data.get("cache_file", "")
        }
                    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error fetching candles: {str(e)}")
        logger.debug(f"Traceback: {error_trace}")
        return None


async def fetch_market_data(
    state: StrategyDevelopmentState,
    mcp_client: Optional[FreqtradeMCPClient] = None
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
            strategy_logger.log_progress(f"Fetching {symbol} {timeframe}", fetched + cached, total_combinations)
            
            # Check cache first
            cached_data = cache.get(symbol, timeframe, days=365)
            
            if cached_data:
                logger.info(f"Using cached data for {symbol} {timeframe}")
                logger.debug(f"Cached data structure: {list(cached_data.keys()) if isinstance(cached_data, dict) else type(cached_data)}")
                
                # Debug: Check if cached data has expected structure
                if isinstance(cached_data, dict):
                    if "data" in cached_data:
                        data_keys = list(cached_data["data"].keys()) if isinstance(cached_data["data"], dict) else "not dict"
                        logger.debug(f"Cached data.data keys: {data_keys}")
                        
                        # Count candles in cached data for debugging
                        if isinstance(cached_data["data"], dict) and "close" in cached_data["data"]:
                            cached_candle_count = len(cached_data["data"]["close"]) if isinstance(cached_data["data"]["close"], dict) else 0
                            logger.info(f"Cached data contains {cached_candle_count} candles for {symbol} {timeframe}")
                
                candle_data[symbol][timeframe] = cached_data
                cached += 1
            else:
                # Fetch from MCP
                logger.info(f"Downloading {symbol} {timeframe} from MCP")
                
                data = await download_and_read_candles_from_mcp(
                    mcp_client,
                    symbol,
                    timeframe,
                    days=365
                )
                
                if data:
                    candle_data[symbol][timeframe] = data
                    cache.set(symbol, timeframe, days=365, data=data)
                    fetched += 1
                    logger.info(f"Successfully fetched {data['candle_count']} candles for {symbol} {timeframe}")
                    strategy_logger.log_data(logging.INFO, f"Fetched {symbol} {timeframe}", {
                        "candles": data['candle_count'],
                        "cached": False
                    })
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
                        "error": "Failed to fetch"
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
    logger.info(f"Data fetch complete: {fetched} fetched, {cached} from cache, {len(fetch_errors)} errors")
    strategy_logger.log_success(f"Data fetch completed", {
        "fetched": fetched,
        "cached": cached,
        "errors": len(fetch_errors),
        "total_candles": sum(
            data.get("candle_count", 0)
            for symbol_data in candle_data.values()
            for data in symbol_data.values()
        )
    })
    
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
    validation = {
        "is_valid": True,
        "issues": [],
        "statistics": {}
    }
    
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
            valid_prices = [p for p in prices if p is not None and (not isinstance(p, float) or p == p)]
            
            if valid_prices:
                validation["statistics"] = {
                    "min_price": min(valid_prices),
                    "max_price": max(valid_prices),
                    "avg_price": sum(valid_prices) / len(valid_prices),
                    "data_points": len(prices),  # Total data points including nulls
                    "valid_data_points": len(valid_prices)  # Only valid data points
                }
            else:
                validation["statistics"] = {
                    "min_price": None,
                    "max_price": None,
                    "avg_price": None,
                    "data_points": len(prices),
                    "valid_data_points": 0
                }
    
    return validation