"""
Data fetching node for market data retrieval
"""
import os
import json
import pickle
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from pathlib import Path
import hashlib
import aiohttp
import asyncio

from ..state import StrategyDevelopmentState

logger = logging.getLogger(__name__)


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


async def fetch_candles_from_mcp(
    mcp_url: str,
    symbol: str,
    timeframe: str,
    days: int = 365
) -> Dict[str, Any]:
    """
    Fetch candle data from MCP server
    
    Returns:
        Dictionary with OHLCV data
    """
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Prepare MCP request
        payload = {
            "method": "download_candles",
            "params": {
                "pairs": [symbol],
                "timeframe": timeframe,
                "timerange": f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}",
                "exchange": "binance"
            }
        }
        
        # Make request to MCP server
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{mcp_url}/tools/download_candles",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Parse the candle data
                    if result.get("success"):
                        return {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "data": result.get("data", {}),
                            "candle_count": result.get("candle_count", 0),
                            "date_range": {
                                "start": start_date.isoformat(),
                                "end": end_date.isoformat()
                            }
                        }
                    else:
                        logger.error(f"MCP error: {result.get('error')}")
                        return None
                else:
                    logger.error(f"HTTP error {response.status} from MCP server")
                    return None
                    
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {symbol} {timeframe}")
        return None
    except Exception as e:
        logger.error(f"Error fetching candles: {str(e)}")
        return None


async def fetch_market_data(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Fetch market data for all symbols and timeframes
    
    This node:
    1. Checks cache for existing data
    2. Fetches missing data from MCP
    3. Updates state with candle data
    """
    logger.info("Starting market data fetch")
    state["current_step"] = "fetch_market_data"
    
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
            
            # Check cache first
            cached_data = cache.get(symbol, timeframe, days=365)
            
            if cached_data:
                logger.info(f"Using cached data for {symbol} {timeframe}")
                candle_data[symbol][timeframe] = cached_data
                cached += 1
            else:
                # Fetch from MCP
                logger.info(f"Downloading {symbol} {timeframe} from MCP")
                
                data = await fetch_candles_from_mcp(
                    state["mcp_server_url"],
                    symbol,
                    timeframe,
                    days=365
                )
                
                if data:
                    candle_data[symbol][timeframe] = data
                    cache.set(symbol, timeframe, days=365, data=data)
                    fetched += 1
                    logger.info(f"Successfully fetched {data['candle_count']} candles for {symbol} {timeframe}")
                else:
                    error_msg = f"Failed to fetch {symbol} {timeframe}"
                    fetch_errors.append(error_msg)
                    logger.error(error_msg)
                    
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
    
    # Validate we have enough data to continue
    total_candles = sum(
        data.get("candle_count", 0)
        for symbol_data in candle_data.values()
        for data in symbol_data.values()
    )
    
    if total_candles == 0:
        state["errors"].append("No candle data available for any symbol/timeframe")
        state["current_step"] = "error"
        logger.error("No candle data available, cannot continue")
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
            validation["statistics"] = {
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": sum(prices) / len(prices),
                "data_points": len(prices)
            }
    
    return validation