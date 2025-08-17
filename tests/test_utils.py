#!/usr/bin/env python3
"""Test utilities functionality."""

import sys
import os
import asyncio
sys.path.insert(0, '/Users/dasein/dev/freqtrade')
sys.path.insert(0, os.path.dirname(__file__))

from src.utils.date_parser import parse_natural_date, format_timerange
from src.utils.coingecko import CoinGeckoClient

def test_date_parser():
    """Test natural language date parsing."""
    test_cases = [
        ("last month", "relative period"),
        ("september", "month name"), 
        ("Q1 2024", "quarter"),
        ("2024", "year"),
        ("march to june", "month range")
    ]
    
    print("Testing date parser...")
    for date_str, description in test_cases:
        try:
            start, end = parse_natural_date(date_str)
            timerange = format_timerange(start, end)
            print(f"✅ {description}: '{date_str}' -> {timerange}")
        except Exception as e:
            print(f"❌ {description}: '{date_str}' -> Error: {e}")

async def test_coingecko():
    """Test CoinGecko client."""
    print("\nTesting CoinGecko client...")
    client = CoinGeckoClient()
    
    try:
        # Test fetching top coins (will use fallback if API fails)
        coins = await client.get_top_coins_by_market_cap(limit=5)
        print(f"✅ Fetched {len(coins)} top coins")
        
        # Test mapping to trading pairs
        pairs = client.map_coins_to_trading_pairs(coins[:3])
        print(f"✅ Mapped to trading pairs: {pairs}")
        
    except Exception as e:
        print(f"⚠️ CoinGecko test failed (expected if no API key): {e}")

def main():
    """Run all tests."""
    test_date_parser()
    asyncio.run(test_coingecko())
    print("\n✅ All utility tests completed!")

if __name__ == "__main__":
    main()