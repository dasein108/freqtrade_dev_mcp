#!/usr/bin/env python3
"""
Example usage of Freqtrade MCP Server commands.
This demonstrates how to use the MCP server programmatically.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import FreqtradeMCPServer


async def example_download_candles():
    """Example: Download candle data."""
    server = FreqtradeMCPServer()
    
    # Initialize download command
    command = server.commands["download_candles"]
    
    # Execute download
    result = await command.execute(
        pairs=["BTC/USDT"],
        timeframes=["1h"],
        date_range="last month",
        exchange="binance"
    )
    
    print("Download Result:")
    print(json.dumps(result, indent=2))


async def example_backtest():
    """Example: Run a backtest."""
    server = FreqtradeMCPServer()
    
    # Initialize backtest command
    command = server.commands["backtest_strategy"]
    
    # Execute backtest
    result = await command.execute(
        strategy_name="SampleStrategy",
        pairs=["BTC/USDT", "ETH/USDT"],
        timerange="last 3 months",
        stake_amount=100,
        export_trades=True
    )
    
    print("Backtest Result:")
    print(json.dumps(result, indent=2))


async def example_list_results():
    """Example: List available results."""
    server = FreqtradeMCPServer()
    
    # Initialize list command
    command = server.commands["list_results"]
    
    # Execute list
    result = await command.execute(
        result_type="backtest",
        limit=10
    )
    
    print("Available Results:")
    print(json.dumps(result, indent=2))


async def main():
    """Run examples."""
    print("=== Freqtrade MCP Server Examples ===\n")
    
    try:
        print("1. Downloading candle data...")
        await example_download_candles()
        print("\n" + "="*50 + "\n")
        
        print("2. Running backtest...")
        await example_backtest()
        print("\n" + "="*50 + "\n")
        
        print("3. Listing results...")
        await example_list_results()
        
    except Exception as e:
        print(f"Example failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())