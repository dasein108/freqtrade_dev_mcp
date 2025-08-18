"""
Strategy generation nodes using Instructor and LLMs
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path
from pydantic import BaseModel

from ..state import StrategyDevelopmentState, StrategyIdea
from ..prompts.strategy_prompts import (
    IDEA_GENERATION_PROMPT,
    STRATEGY_CODE_PROMPT,
    STRATEGY_REWRITE_PROMPT
)
from ..llm_client import create_llm_client, LLMConfig
from ..config import config
from ..logging_config import get_logger

logger = logging.getLogger(__name__)
strategy_logger = get_logger()


class StrategyCodeResponse(BaseModel):
    """Response model for strategy code generation (DRY principle)"""
    strategy_code: str
    explanation: str


def _get_idea_generation_client():
    """Get LLM client for idea generation (uses regular model)"""
    try:
        llm_config_dict = config.get_llm_config()
        llm_config = LLMConfig(**llm_config_dict)
        return create_llm_client(llm_config)
    except Exception as e:
        logger.error(f"Failed to create LLM client for idea generation: {e}")
        raise


def _get_code_generation_client():
    """Get LLM client for code generation (uses code model with lower temperature)"""
    try:
        llm_config_dict = config.get_llm_code_config()
        llm_config = LLMConfig(**llm_config_dict)
        return create_llm_client(llm_config)
    except Exception as e:
        logger.error(f"Failed to create LLM client for code generation: {e}")
        raise


async def generate_strategy_idea(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Generate a trading strategy idea based on market data analysis
    """
    logger.info("Generating strategy idea")
    strategy_logger.set_phase("STRATEGY GENERATION")
    strategy_logger.set_step("Idea Generation")
    state["current_step"] = "generate_strategy_idea"
    
    try:
        # Prepare market context
        strategy_logger.log_progress("Analyzing market data for strategy ideas")
        market_context = prepare_market_context(state["candle_data"])
        
        # Generate idea using configured LLM client
        strategy_logger.log_progress("Calling LLM for strategy idea generation")
        llm_client = _get_idea_generation_client()
        idea = await llm_client.create_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert quantitative trader and strategy developer."
                },
                {
                    "role": "user",
                    "content": IDEA_GENERATION_PROMPT.format(
                        symbols=", ".join(state["symbols"]),
                        timeframes=", ".join(state["timeframes"]),
                        market_context=market_context
                    )
                }
            ],
            response_model=StrategyIdea,
            temperature=0.7,
            max_retries=2
        )
        
        # Store idea in state
        state["strategy_idea"] = idea
        state["strategy_name"] = f"AI_{idea.name}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        strategy_logger.log_success("Strategy idea generated", {
            "name": idea.name,
            "description": idea.description,
            "indicators": idea.indicators,
            "timeframe": idea.timeframe_preference
        })
        
        logger.info(f"Generated strategy idea: {idea.name}")
        logger.info(f"Indicators: {', '.join(idea.indicators)}")
        logger.info(f"Timeframe preference: {idea.timeframe_preference}")
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error generating strategy idea: {str(e)}")
        logger.debug(f"Traceback: {error_trace}")
        
        strategy_logger.log_error(f"Failed to generate strategy idea", e, error_trace)
        state["errors"].append(f"Failed to generate strategy idea: {str(e)}")
        state["retry_count"] += 1
    
    return state


async def create_strategy_code(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Create complete strategy code from the idea
    """
    logger.info("Creating strategy code")
    state["current_step"] = "create_strategy_code"
    
    if not state["strategy_idea"]:
        state["errors"].append("No strategy idea available")
        return state
    
    try:
        idea = state["strategy_idea"]
        
        # Generate strategy code using code generation client
        llm_client = _get_code_generation_client()
        
        code_response = await llm_client.create_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Freqtrade strategy developer. Generate complete, working strategy code."
                },
                {
                    "role": "user",
                    "content": STRATEGY_CODE_PROMPT.format(
                        strategy_name=state["strategy_name"],
                        idea_description=idea.description,
                        indicators=", ".join(idea.indicators),
                        entry_logic=idea.entry_logic,
                        exit_logic=idea.exit_logic,
                        risk_management=idea.risk_management,
                        timeframe=idea.timeframe_preference
                    )
                }
            ],
            response_model=StrategyCodeResponse,
            max_tokens=4000
        )
        
        strategy_code = code_response.strategy_code
        
        # Clean and validate code
        strategy_code = clean_strategy_code(strategy_code)
        
        # Save strategy file
        strategy_path = save_strategy_file(state["strategy_name"], strategy_code)
        
        # Update state
        state["strategy_code"] = strategy_code
        state["strategy_file_path"] = str(strategy_path)
        
        # Create strategy config
        state["strategy_config"] = {
            "strategy": state["strategy_name"],
            "timeframe": idea.timeframe_preference,
            "stake_currency": "USDT",
            "stake_amount": 100,
            "max_open_trades": 3,
            "dry_run": True
        }
        
        logger.info(f"Strategy code created and saved to {strategy_path}")
        
    except Exception as e:
        logger.error(f"Error creating strategy code: {str(e)}")
        state["errors"].append(f"Failed to create strategy code: {str(e)}")
        state["retry_count"] += 1
    
    return state


async def rewrite_strategy(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Rewrite strategy based on analysis feedback
    """
    logger.info("Rewriting strategy based on analysis")
    state["current_step"] = "rewrite_strategy"
    state["iteration_count"] += 1
    
    if not state["strategy_analysis"]:
        state["errors"].append("No analysis available for rewrite")
        return state
    
    try:
        analysis = state["strategy_analysis"]
        
        # Generate improved strategy using code generation client
        llm_client = _get_code_generation_client()
        
        improved_response = await llm_client.create_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at improving trading strategies based on performance analysis."
                },
                {
                    "role": "user",
                    "content": STRATEGY_REWRITE_PROMPT.format(
                        original_code=state["strategy_code"],
                        performance_rating=analysis.performance_rating,
                        weaknesses=", ".join(analysis.weaknesses),
                        suggestions=", ".join(analysis.improvement_suggestions),
                        metrics=json.dumps({
                            "profit": state["performance_metrics"].total_profit_pct if state["performance_metrics"] else 0,
                            "sharpe": state["performance_metrics"].sharpe_ratio if state["performance_metrics"] else 0,
                            "drawdown": state["performance_metrics"].max_drawdown_pct if state["performance_metrics"] else 0,
                            "trades": state["performance_metrics"].total_trades if state["performance_metrics"] else 0
                        }, indent=2)
                    )
                }
            ],
            response_model=StrategyCodeResponse,
            temperature=0.5,
            max_tokens=4000
        )
        
        improved_code = improved_response.strategy_code
        improved_code = clean_strategy_code(improved_code)
        
        # Update strategy name for new version
        version = state["iteration_count"] + 1
        state["strategy_name"] = f"{state['strategy_name'].rsplit('_v', 1)[0]}_v{version}"
        
        # Save new version
        strategy_path = save_strategy_file(state["strategy_name"], improved_code)
        
        # Update state
        state["strategy_code"] = improved_code
        state["strategy_file_path"] = str(strategy_path)
        
        # Add to iteration history
        state["iteration_history"].append({
            "iteration": state["iteration_count"],
            "strategy_name": state["strategy_name"],
            "improvements_attempted": analysis.improvement_suggestions
        })
        
        logger.info(f"Strategy rewritten: {state['strategy_name']}")
        
    except Exception as e:
        logger.error(f"Error rewriting strategy: {str(e)}")
        state["errors"].append(f"Failed to rewrite strategy: {str(e)}")
        state["retry_count"] += 1
    
    return state


def prepare_market_context(candle_data: Dict[str, Any]) -> str:
    """Prepare market context summary for LLM"""
    context_parts = []
    
    for symbol, timeframes in candle_data.items():
        for tf, data in timeframes.items():
            if data and data.get("candle_count", 0) > 0:
                context_parts.append(
                    f"- {symbol} ({tf}): {data['candle_count']} candles available"
                )
                
                # Add price statistics if available
                if "statistics" in data:
                    stats = data["statistics"]
                    context_parts.append(
                        f"  Price range: ${stats.get('min_price', 0):.2f} - ${stats.get('max_price', 0):.2f}"
                    )
    
    return "\n".join(context_parts) if context_parts else "Market data available for analysis"


def clean_strategy_code(code: str) -> str:
    """Clean and format strategy code"""
    # Remove markdown code blocks if present
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]
    
    # Ensure proper imports
    required_imports = [
        "from freqtrade.strategy import IStrategy",
        "import talib.abstract as ta",
        "import pandas as pd",
        "from pandas import DataFrame",
        "from datetime import datetime",
        "from freqtrade.strategy import DecimalParameter, IntParameter"
    ]
    
    for imp in required_imports:
        if imp not in code:
            code = imp + "\n" + code
    
    return code.strip()


def save_strategy_file(strategy_name: str, code: str) -> Path:
    """Save strategy code to file"""
    # Strategy files go in the freqtrade user_data/strategies directory
    # Navigate from freqtrade_mcp/strategy_agent/nodes/ to freqtrade/user_data/strategies/
    current_dir = Path(__file__).parent  # .../freqtrade_mcp/strategy_agent/nodes/
    freqtrade_dir = current_dir.parent.parent.parent  # .../freqtrade/
    strategies_dir = freqtrade_dir / "user_data" / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    
    strategy_file = strategies_dir / f"{strategy_name}.py"
    
    with open(strategy_file, 'w') as f:
        f.write(code)
    
    logger.info(f"Strategy saved to {strategy_file}")
    return strategy_file