#!/usr/bin/env python3
"""
Clean Strategy Development Agent runner
"""
import asyncio
import sys
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path
import dotenv
# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from strategy_agent import StrategyDevelopmentAgent
from strategy_agent.logging_config import setup_logging

dotenv.load_dotenv()

async def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Run the Strategy Development Agent")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/USDT:USDT", "ETH/USDT:USDT"],
        help="Trading pairs to develop strategy for"
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["1h"],
        help="Timeframes to use"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum strategy rewrite iterations"
    )
    parser.add_argument(
        "--hyperopt-epochs",
        type=int,
        default=100,
        help="Number of hyperopt epochs"
    )
    parser.add_argument(
        "--min-profit",
        type=float,
        default=5.0,
        help="Minimum profit threshold (%)"
    )
    parser.add_argument(
        "--mcp-server-path",
        help="Path to MCP server script (optional)"
    )
    parser.add_argument(
        "--resume",
        help="Resume from checkpoint ID"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure enhanced logging
    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    strategy_logger = setup_logging(session_id=session_id, verbose=args.verbose)
    
    # Also configure basic logging for other modules
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(f"📝 Logs will be saved to:")
    print(f"   • logs/strategy_{session_id}.log (human-readable)")
    print(f"   • logs/strategy_{session_id}.json (structured)")
    print("-" * 50)
    
    # Check for LLM configuration
    if not os.getenv("LLM_API_KEY"):
        print("❌ Error: LLM_API_KEY environment variable is required")
        print("Please set it with: export LLM_API_KEY='your-api-key'")
        print("Also set: export LLM_MODEL='provider/model'")
        print("Example: export LLM_MODEL='openai/gpt-4o-mini' LLM_API_KEY='sk-...'")
        return 1
    
    if not os.getenv("LLM_MODEL"):
        print("❌ Error: LLM_MODEL environment variable is required")
        print("Please set it with: export LLM_MODEL='provider/model'")
        print("Example: export LLM_MODEL='openai/gpt-4o-mini'")
        return 1
    
    print("🚀 Starting Strategy Development Agent")
    print(f"📊 Symbols: {', '.join(args.symbols)}")
    print(f"⏰ Timeframes: {', '.join(args.timeframes)}")
    print(f"🔄 Max iterations: {args.max_iterations}")
    print(f"🎯 Min profit target: {args.min_profit}%")
    print(f"🤖 LLM Model: {os.getenv('LLM_MODEL')}")
    if args.mcp_server_path:
        print(f"🔧 MCP server: {args.mcp_server_path}")
    print("-" * 50)
    
    # Initialize agent
    agent = StrategyDevelopmentAgent(
        symbols=args.symbols,
        timeframes=args.timeframes,
        max_iterations=args.max_iterations,
        hyperopt_epochs=args.hyperopt_epochs,
        min_profit_threshold=args.min_profit,
        mcp_server_path=args.mcp_server_path
    )
    
    # Check MCP connection
    print("🔗 Testing MCP server connection...")
    if not await agent.validate_connection():
        print("❌ Failed to connect to MCP server")
        print("Please ensure the MCP server is available:")
        print("  cd src && python -m server")
        return 1
    
    print("✅ MCP server connection successful")
    print("-" * 50)
    
    try:
        # Run strategy development
        if args.resume:
            print(f"📥 Resuming from checkpoint: {args.resume}")
            result = await agent.develop_strategy(resume_from=args.resume)
        else:
            result = await agent.develop_strategy()
        
        print("-" * 50)
        
        # Display results
        if result["success"]:
            print("🎉 Strategy Development Successful!")
            print(f"📝 Strategy Name: {result['strategy_name']}")
            print(f"📁 Strategy File: {result['strategy_file']}")
            print("\n📊 Performance Metrics:")
            print(f"  💰 Total Profit: {result['metrics']['total_profit']:.2f}%")
            print(f"  📈 Sharpe Ratio: {result['metrics']['sharpe_ratio']:.2f}")
            print(f"  📉 Max Drawdown: {result['metrics']['max_drawdown']:.2f}%")
            print(f"  🎯 Win Rate: {result['metrics']['win_rate']:.1f}%")
            print(f"  🔢 Total Trades: {result['metrics']['total_trades']}")
            
            if result.get("hyperopt_params"):
                print("\n🔧 Optimized Parameters:")
                for space, params in result["hyperopt_params"].items():
                    if params:
                        print(f"  {space}: {params}")
            
            print(f"\n⏱️ Total Duration: {result['duration_minutes']:.1f} minutes")
            print(f"🔄 Iterations Used: {result['iterations']}")
            
            print("\n✅ Strategy is ready for use!")
            print(f"To backtest: freqtrade backtesting --strategy {result['strategy_name']}")
            
        else:
            print("❌ Strategy Development Failed")
            print(f"🔄 Iterations attempted: {result['iterations']}")
            
            if "best_attempt" in result and result["best_attempt"]:
                print("\n📊 Best Attempt:")
                best = result["best_attempt"]
                if "metrics" in best:
                    print(f"  Strategy: {best.get('strategy_name', 'N/A')}")
                    print(f"  Profit: {best['metrics'].get('profit', 0):.2f}%")
                    print(f"  Sharpe: {best['metrics'].get('sharpe', 0):.2f}")
                    print(f"  Trades: {best['metrics'].get('trades', 0)}")
            
            if result.get("errors"):
                print("\n❌ Errors encountered:")
                for error in result["errors"][:5]:  # Show first 5 errors
                    print(f"  - {error}")
            
            print(f"\n⏱️ Duration: {result.get('duration_minutes', 0):.1f} minutes")
            
        print("\n📄 Session ID:", result["session_id"])
        return 0 if result["success"] else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)