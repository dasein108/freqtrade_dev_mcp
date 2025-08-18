"""
Main LangGraph Agent for Strategy Development
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import (
    StrategyDevelopmentState,
    create_initial_state,
    should_continue_optimization,
    get_state_summary
)
from .mcp_client import FreqtradeMCPClient
from .nodes.data_fetcher import fetch_market_data
from .nodes.strategy_generator import generate_strategy_idea, create_strategy_code, rewrite_strategy
from .nodes.hyperopt_runner import run_hyperopt
from .nodes.result_analyzer import analyze_results, finalize_strategy, return_best_attempt
from .logging_config import get_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
strategy_logger = get_logger()


class StrategyDevelopmentAgent:
    """
    LangGraph-based agent for automated strategy development
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        timeframes: List[str] = None,
        max_iterations: int = 3,
        hyperopt_epochs: int = 100,
        min_profit_threshold: float = 5.0,
        cache_dir: str = "./cache",
        mcp_server_path: str = None
    ):
        """
        Initialize the strategy development agent
        
        Args:
            symbols: List of trading pairs
            timeframes: List of timeframes
            max_iterations: Maximum strategy rewrite attempts
            hyperopt_epochs: Number of hyperopt epochs
            min_profit_threshold: Minimum profit percentage to consider strategy profitable
            cache_dir: Directory for caching data
            mcp_server_path: Path to MCP server script (optional)
        """
        self.symbols = symbols or ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
        self.timeframes = timeframes or ["1h", "4h"]
        self.max_iterations = max_iterations
        self.hyperopt_epochs = hyperopt_epochs
        self.min_profit_threshold = min_profit_threshold
        self.cache_dir = cache_dir
        
        # Initialize MCP client
        from pathlib import Path
        if mcp_server_path:
            server_path = Path(mcp_server_path)
        else:
            server_path = None
        self.mcp_client = FreqtradeMCPClient(server_path)
        
        # Memory for checkpointing - must be initialized before building graph
        self.memory = MemorySaver()
        
        # Initialize the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create the graph
        workflow = StateGraph(StrategyDevelopmentState)
        
        # Create wrapper functions that inject MCP client
        async def fetch_market_data_wrapper(state):
            return await fetch_market_data(state, self.mcp_client)
        
        async def run_hyperopt_wrapper(state):
            return await run_hyperopt(state, self.mcp_client)
        
        # Add nodes
        workflow.add_node("fetch_market_data", fetch_market_data_wrapper)
        workflow.add_node("generate_strategy_idea", generate_strategy_idea)
        workflow.add_node("create_strategy_code", create_strategy_code)
        workflow.add_node("run_hyperopt", run_hyperopt_wrapper)
        workflow.add_node("analyze_results", analyze_results)
        workflow.add_node("rewrite_strategy", rewrite_strategy)
        workflow.add_node("finalize_strategy", finalize_strategy)
        workflow.add_node("return_best_attempt", return_best_attempt)
        
        # Define edges
        workflow.set_entry_point("fetch_market_data")
        
        # Linear flow for main path
        workflow.add_edge("fetch_market_data", "generate_strategy_idea")
        workflow.add_edge("generate_strategy_idea", "create_strategy_code")
        workflow.add_edge("create_strategy_code", "run_hyperopt")
        workflow.add_edge("run_hyperopt", "analyze_results")
        
        # Conditional routing after analysis
        workflow.add_conditional_edges(
            "analyze_results",
            should_continue_optimization,
            {
                "finalize_strategy": "finalize_strategy",
                "return_best_attempt": "return_best_attempt",
                "rewrite_strategy": "rewrite_strategy"
            }
        )
        
        # Rewrite loop
        workflow.add_edge("rewrite_strategy", "create_strategy_code")
        
        # End states
        workflow.add_edge("finalize_strategy", END)
        workflow.add_edge("return_best_attempt", END)
        
        return workflow.compile(checkpointer=self.memory)
    
    async def develop_strategy(
        self,
        resume_from: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the complete strategy development workflow
        
        Args:
            resume_from: Optional checkpoint ID to resume from
            
        Returns:
            Dictionary with results including strategy name, code, and metrics
        """
        logger.info("Starting strategy development workflow")
        strategy_logger.set_phase("WORKFLOW INITIALIZATION")
        strategy_logger.log_progress(f"Starting strategy development for {len(self.symbols)} symbols")
        
        # Create initial state
        initial_state = create_initial_state(
            symbols=self.symbols,
            timeframes=self.timeframes,
            max_iterations=self.max_iterations,
            hyperopt_epochs=self.hyperopt_epochs
        )
        
        # Don't add MCP client to state - it's not serializable
        # Nodes will get it through the wrapper functions
        
        # Configuration for the run
        config = {
            "configurable": {
                "thread_id": initial_state["session_id"],
                "checkpoint_id": resume_from
            }
        }
        
        try:
            # Start MCP client
            async with self.mcp_client:
                logger.info("MCP client connected, starting workflow")
                
                # Run the workflow
                final_state = None
                strategy_logger.set_phase("WORKFLOW EXECUTION")
                
                async for event in self.graph.astream(initial_state, config):
                    # Log progress
                    for node_name, node_state in event.items():
                        strategy_logger.set_step(node_name)
                        strategy_logger.log_progress(f"Executing node: {node_name}")
                        
                        logger.info(f"Completed node: {node_name}")
                        if isinstance(node_state, dict):
                            summary = get_state_summary(node_state)
                            logger.info(f"State summary: {summary}")
                            
                            # Log detailed progress
                            if node_state.get("errors"):
                                strategy_logger.log_data(logging.WARNING, "Errors in state", {
                                    "errors": node_state["errors"][-5:]  # Last 5 errors
                                })
                            
                            final_state = node_state
                
                # Process final results
                if final_state:
                    return self._prepare_results(final_state)
                else:
                    return {
                        "success": False,
                        "error": "Workflow completed without final state"
                    }
                
        except Exception as e:
            logger.error(f"Error in strategy development: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "session_id": initial_state["session_id"],
                "iterations": 0,
                "duration_minutes": 0
            }
    
    def _prepare_results(self, state: StrategyDevelopmentState) -> Dict[str, Any]:
        """Prepare final results from the completed workflow"""
        
        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - state["start_time"]).total_seconds() / 60
        
        results = {
            "success": state["success"],
            "session_id": state["session_id"],
            "strategy_name": state["strategy_name"],
            "iterations": state["iteration_count"],
            "duration_minutes": round(duration, 2)
        }
        
        if state["success"]:
            results.update({
                "strategy_file": state["strategy_file_path"],
                "metrics": {
                    "total_profit": state["performance_metrics"].total_profit_pct if state["performance_metrics"] else 0,
                    "sharpe_ratio": state["performance_metrics"].sharpe_ratio if state["performance_metrics"] else 0,
                    "max_drawdown": state["performance_metrics"].max_drawdown_pct if state["performance_metrics"] else 0,
                    "win_rate": state["performance_metrics"].win_rate_pct if state["performance_metrics"] else 0,
                    "total_trades": state["performance_metrics"].total_trades if state["performance_metrics"] else 0
                },
                "hyperopt_params": state["hyperopt_best_params"],
                "backtest_file": state["backtest_file_path"]
            })
        else:
            # Return best attempt if failed
            if state["best_iteration"]:
                results["best_attempt"] = state["best_iteration"]
            results["errors"] = state["errors"]
            results["warnings"] = state["warnings"]
        
        return results
    
    async def get_checkpoints(self) -> List[Dict[str, Any]]:
        """Get list of available checkpoints"""
        checkpoints = []
        async for checkpoint in self.memory.alist():
            checkpoints.append({
                "id": checkpoint.config["configurable"]["checkpoint_id"],
                "thread_id": checkpoint.config["configurable"]["thread_id"],
                "timestamp": checkpoint.metadata.get("timestamp", "")
            })
        return checkpoints
    
    async def validate_connection(self) -> bool:
        """Validate MCP server connection"""
        try:
            async with self.mcp_client:
                logger.info("MCP connection validation successful")
                return True
        except Exception as e:
            logger.error(f"MCP connection validation failed: {e}")
            return False


async def main():
    """Example usage"""
    agent = StrategyDevelopmentAgent(
        symbols=["BTC/USDT:USDT"],
        timeframes=["1h"],
        max_iterations=2,
        hyperopt_epochs=50
    )
    
    # Check connection
    if not await agent.validate_connection():
        logger.error("Failed to connect to MCP server")
        return
    
    # Run strategy development
    result = await agent.develop_strategy()
    
    if result["success"]:
        print(f"✅ Successfully created strategy: {result['strategy_name']}")
        print(f"📊 Profit: {result['metrics']['total_profit']}%")
        print(f"📈 Sharpe Ratio: {result['metrics']['sharpe_ratio']}")
        print(f"📉 Max Drawdown: {result['metrics']['max_drawdown']}%")
        print(f"🎯 Win Rate: {result['metrics']['win_rate']}%")
        print(f"📁 Strategy saved to: {result['strategy_file']}")
    else:
        print(f"❌ Strategy development failed after {result['iterations']} iterations")
        if "best_attempt" in result:
            print(f"Best attempt metrics: {result['best_attempt']}")
        print(f"Errors: {result.get('errors', [])}")


if __name__ == "__main__":
    asyncio.run(main())