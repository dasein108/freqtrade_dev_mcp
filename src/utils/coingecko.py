"""CoinGecko API client for fetching market data."""

import asyncio
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Import Freqtrade's CoinGecko wrapper from the installed package
try:
    from freqtrade.util.coin_gecko import FtCoinGeckoApi
except ImportError:
    # Don't log during import as it interferes with MCP protocol
    from pycoingecko import CoinGeckoAPI as FtCoinGeckoApi


class CoinGeckoClient:
    """Async client for CoinGecko API using Freqtrade's wrapper."""

    def __init__(self, api_key: Optional[str] = None, is_demo: bool = True):
        """Initialize CoinGecko client."""
        self.api_key = api_key
        self.is_demo = is_demo
        
        if api_key:
            self.cg = FtCoinGeckoApi(api_key=api_key, is_demo=is_demo)
        else:
            self.cg = FtCoinGeckoApi()
            
        self._cache: Dict[str, List[Dict]] = {}
        self._cache_timestamp = 0

    async def get_top_coins_by_market_cap(
        self, 
        limit: int = 15,
        vs_currency: str = "usd"
    ) -> List[Dict]:
        """Get top coins by market cap.
        
        Args:
            limit: Number of top coins to return
            vs_currency: Base currency for market cap
            
        Returns:
            List of coin data dictionaries
        """
        cache_key = f"top_coins_{limit}_{vs_currency}"
        current_time = asyncio.get_event_loop().time()
        
        # Check cache (15 minute TTL)
        if (cache_key in self._cache and 
            current_time - self._cache_timestamp < 900):
            return self._cache[cache_key][:limit]
        
        try:
            # Fetch from API
            coins = await asyncio.to_thread(
                self.cg.get_coins_markets,
                vs_currency=vs_currency,
                order="market_cap_desc",
                per_page=limit,
                page=1,
                sparkline=False
            )
            
            # Update cache
            self._cache[cache_key] = coins
            self._cache_timestamp = current_time
            
            logger.info(f"Fetched {len(coins)} top coins from CoinGecko")
            return coins
            
        except Exception as e:
            logger.error(f"Failed to fetch top coins: {e}")
            # Return cached data if available
            if cache_key in self._cache:
                logger.warning("Using cached data due to API error")
                return self._cache[cache_key][:limit]
            raise

    def map_coins_to_trading_pairs(
        self, 
        coins: List[Dict], 
        quote_currency: str = "USDT",
        exchange: str = "binance"
    ) -> List[str]:
        """Map CoinGecko coins to trading pairs.
        
        Args:
            coins: List of coin data from CoinGecko
            quote_currency: Quote currency for pairs (USDT, BTC, etc.)
            exchange: Exchange name for pair format
            
        Returns:
            List of trading pair strings
        """
        pairs = []
        
        for coin in coins:
            symbol = coin.get("symbol", "").upper()
            if not symbol:
                continue
                
            # Skip stablecoins when quote is USDT
            if quote_currency == "USDT" and symbol in ["USDT", "USDC", "BUSD", "DAI", "TUSD"]:
                continue
                
            # Common symbol mappings for Binance
            symbol_mapping = {
                "MIOTA": "IOTA",  # IOTA has different symbol on exchanges
                "HOT": "HOLO",    # Holochain mapping
            }
            
            exchange_symbol = symbol_mapping.get(symbol, symbol)
            pair = f"{exchange_symbol}/{quote_currency}"
            pairs.append(pair)
        
        logger.info(f"Mapped {len(pairs)} trading pairs for {exchange}")
        return pairs

    async def get_top_trading_pairs(
        self,
        limit: int = 15,
        quote_currency: str = "USDT",
        exchange: str = "binance"
    ) -> List[str]:
        """Get top trading pairs by market cap.
        
        Args:
            limit: Number of pairs to return
            quote_currency: Quote currency for pairs
            exchange: Exchange name
            
        Returns:
            List of trading pair strings
        """
        coins = await self.get_top_coins_by_market_cap(limit * 2)  # Get more to account for filtering
        pairs = self.map_coins_to_trading_pairs(coins, quote_currency, exchange)
        return pairs[:limit]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example usage
    client = CoinGeckoClient()

    async def main():
        top_coins = await client.get_top_coins_by_market_cap(limit=10)
        logger.info(f"Top coins: {top_coins}")

        trading_pairs = await client.get_top_trading_pairs(limit=10)
        logger.info(f"Top trading pairs: {trading_pairs}")

    asyncio.run(main())