"""Pydantic models for MCP server responses and data structures."""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator


class MCPResponse(BaseModel):
    """Base MCP response model."""
    command: str = Field(..., description="The MCP command that was executed")
    success: bool = Field(..., description="Whether the operation succeeded")
    error: Optional[str] = Field(None, description="Error message if success is False")
    error_type: Optional[str] = Field(None, description="Type of error")
    duration_seconds: Optional[float] = Field(None, description="Execution time in seconds")
    
    class Config:
        extra = "allow"  # Allow additional fields


class CacheFileInfo(BaseModel):
    """Information about a cache file."""
    pair: str = Field(..., description="Trading pair symbol")
    filename: str = Field(..., description="Cache filename")
    full_path: str = Field(..., description="Full path to cache file")
    candle_count: int = Field(0, description="Number of candles in the file")


class DownloadResult(BaseModel):
    """Result for a single timeframe download."""
    timeframe: str = Field(..., description="Timeframe that was downloaded")
    pairs_count: int = Field(..., description="Number of pairs requested")
    pairs: List[str] = Field(..., description="List of pairs requested")
    successful_pairs: List[str] = Field(default_factory=list, description="Successfully downloaded pairs")
    failed_pairs: List[Dict[str, str]] = Field(default_factory=list, description="Failed pairs with error info")
    success: bool = Field(..., description="Whether the download succeeded")
    returncode: Optional[int] = Field(None, description="Return code from download process")
    cache_files: List[CacheFileInfo] = Field(default_factory=list, description="Cache files created")
    candle_count: int = Field(0, description="Total candles downloaded")
    output: Optional[str] = Field(None, description="Download output/logs")
    error: Optional[str] = Field(None, description="Error message if failed")


class DownloadCandlesResponse(MCPResponse):
    """Response from download_candles MCP tool."""
    exchange: str = Field(..., description="Exchange used for download")
    pairs: List[str] = Field(..., description="Trading pairs downloaded")
    timeframes: List[str] = Field(..., description="Timeframes downloaded")
    date_range: str = Field(..., description="Natural language date range")
    timerange: str = Field(..., description="Formatted timerange")
    total_downloads: int = Field(..., description="Total download operations")
    successful: int = Field(..., description="Number of successful downloads")
    failed: int = Field(..., description="Number of failed downloads")
    results: List[DownloadResult] = Field(..., description="Download results per timeframe")


class CandleData(BaseModel):
    """OHLCV candle data structure."""
    symbol: str = Field(..., description="Trading pair symbol")
    timeframe: str = Field(..., description="Timeframe")
    timerange: Optional[str] = Field(None, description="Time range of data")
    data: Dict[str, Dict[str, Union[float, int]]] = Field(..., description="OHLCV data")
    candle_count: int = Field(0, description="Number of candles")
    cache_file: Optional[str] = Field(None, description="Source cache file")
    
    class Config:
        extra = "allow"


class ReadFileInfo(BaseModel):
    """Information about a successfully read file."""
    file: str = Field(..., description="Cache filename")
    symbol: str = Field(..., description="Trading pair symbol")
    timeframe: str = Field(..., description="Timeframe")
    candle_count: int = Field(..., description="Number of candles read")


class ReadFileError(BaseModel):
    """Information about a failed file read."""
    file: str = Field(..., description="Cache filename")
    error: str = Field(..., description="Error message")


class ReadCandlesResponse(MCPResponse):
    """Response from read_candles MCP tool."""
    files_requested: int = Field(..., description="Number of files requested")
    files_read: int = Field(..., description="Number of files successfully read")
    files_failed: int = Field(..., description="Number of files that failed to read")
    total_candles: int = Field(..., description="Total candles read")
    candle_data: Dict[str, Dict[str, CandleData]] = Field(..., description="Nested candle data by symbol/timeframe")
    successful_reads: List[ReadFileInfo] = Field(default_factory=list, description="Successfully read files")
    failed_reads: List[ReadFileError] = Field(default_factory=list, description="Failed file reads")


class PerformanceMetrics(BaseModel):
    """Trading performance metrics."""
    total_profit_pct: float = Field(..., description="Total profit percentage")
    total_profit_abs: Optional[float] = Field(None, description="Total profit in absolute terms")
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: Optional[int] = Field(None, description="Number of winning trades")
    losing_trades: Optional[int] = Field(None, description="Number of losing trades")
    win_rate: float = Field(..., description="Win rate as decimal (0-1)")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    sortino_ratio: Optional[float] = Field(None, description="Sortino ratio")
    calmar_ratio: Optional[float] = Field(None, description="Calmar ratio")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown percentage")
    avg_profit_pct: Optional[float] = Field(None, description="Average profit per trade")
    avg_duration: Optional[str] = Field(None, description="Average trade duration")


class PairSummary(BaseModel):
    """Performance summary for a trading pair."""
    profit_pct: float = Field(..., description="Profit percentage for this pair")
    trades: int = Field(..., description="Number of trades for this pair")
    win_rate: float = Field(..., description="Win rate for this pair")


class BacktestResponse(MCPResponse):
    """Response from backtest_strategy MCP tool."""
    strategy: str = Field(..., description="Strategy name")
    result_id: str = Field(..., description="Unique result identifier")
    result_file: str = Field(..., description="Path to result file")
    performance: PerformanceMetrics = Field(..., description="Performance metrics")
    pairs_summary: Dict[str, PairSummary] = Field(default_factory=dict, description="Per-pair performance")
    timerange_used: str = Field(..., description="Timerange used for backtest")


class HyperoptParams(BaseModel):
    """Hyperopt parameter spaces."""
    buy: Optional[Dict[str, Any]] = Field(None, description="Buy signal parameters")
    sell: Optional[Dict[str, Any]] = Field(None, description="Sell signal parameters")  
    roi: Optional[Dict[str, float]] = Field(None, description="ROI table")
    stoploss: Optional[float] = Field(None, description="Stop loss value")
    trailing: Optional[Dict[str, Any]] = Field(None, description="Trailing stop parameters")
    
    class Config:
        extra = "allow"


class OptimizationStats(BaseModel):
    """Hyperopt optimization statistics."""
    total_epochs: int = Field(..., description="Total epochs run")
    best_epoch: int = Field(..., description="Epoch with best result")
    duration_minutes: Optional[float] = Field(None, description="Total duration in minutes")
    avg_time_per_epoch: Optional[float] = Field(None, description="Average time per epoch")


class HyperoptResponse(MCPResponse):
    """Response from hyperopt_strategy MCP tool."""
    strategy: str = Field(..., description="Strategy name")
    result_id: str = Field(..., description="Unique result identifier")
    result_file: str = Field(..., description="Path to hyperopt result file")
    best_result: PerformanceMetrics = Field(..., description="Best optimization result")
    best_params: HyperoptParams = Field(..., description="Best parameter combination")
    optimization_stats: OptimizationStats = Field(..., description="Optimization statistics")


class StrategyFeatures(BaseModel):
    """Features enabled in a strategy."""
    timeframe: Optional[str] = Field(None, description="Primary timeframe")
    indicators: Optional[List[str]] = Field(None, description="Technical indicators used")
    can_short: bool = Field(False, description="Whether strategy can short")
    trailing_stop: bool = Field(False, description="Whether trailing stop is enabled")
    
    class Config:
        extra = "allow"


class StrategyResponse(MCPResponse):
    """Response from create_strategy or create_strategy_wireframe MCP tools."""
    strategy_name: str = Field(..., description="Name of created strategy")
    file_path: str = Field(..., description="Path to strategy file")
    template_used: Optional[str] = Field(None, description="Template used for creation")
    style: Optional[str] = Field(None, description="Wireframe style used")
    features: Optional[StrategyFeatures] = Field(None, description="Strategy features")
    message: str = Field(..., description="Success message")
    code_preview: Optional[str] = Field(None, description="Preview of generated code")


class ResultInfo(BaseModel):
    """Information about a backtest or hyperopt result."""
    id: str = Field(..., description="Unique result identifier")
    type: str = Field(..., description="Result type (backtest/hyperopt)")
    strategy: str = Field(..., description="Strategy name")
    timestamp: str = Field(..., description="Result timestamp")
    file_path: str = Field(..., description="Path to result file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Performance summary")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ListResultsResponse(MCPResponse):
    """Response from list_results MCP tool."""
    results: List[ResultInfo] = Field(..., description="List of available results")
    total_results: int = Field(..., description="Total number of results")
    filtered_count: int = Field(..., description="Number of results after filtering")


class SearchMatch(BaseModel):
    """A search result match."""
    id: str = Field(..., description="Result identifier")
    type: str = Field(..., description="Result type")
    strategy: str = Field(..., description="Strategy name")
    timestamp: str = Field(..., description="Result timestamp")
    relevance_score: Optional[float] = Field(None, description="Search relevance score")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Performance summary")
    matched_criteria: List[str] = Field(default_factory=list, description="Matched search criteria")


class SearchStats(BaseModel):
    """Search execution statistics."""
    total_searched: int = Field(..., description="Total items searched")
    execution_time_ms: int = Field(..., description="Search execution time")
    index_used: bool = Field(..., description="Whether search index was used")


class SearchResultsResponse(MCPResponse):
    """Response from search_results MCP tool."""
    query: Optional[str] = Field(None, description="Search query used")
    matches: List[SearchMatch] = Field(..., description="Search matches")
    total_matches: int = Field(..., description="Total number of matches")
    search_stats: SearchStats = Field(..., description="Search execution statistics")


class ExtractedTrade(BaseModel):
    """Individual trade data."""
    pair: str = Field(..., description="Trading pair")
    profit_pct: float = Field(..., description="Trade profit percentage")
    profit_abs: float = Field(..., description="Trade profit absolute")
    open_date: str = Field(..., description="Trade open timestamp")
    close_date: str = Field(..., description="Trade close timestamp")
    duration: str = Field(..., description="Trade duration")
    entry_tag: Optional[str] = Field(None, description="Entry tag/signal")
    exit_reason: Optional[str] = Field(None, description="Exit reason")


class DailyStats(BaseModel):
    """Daily performance statistics."""
    avg_daily_profit: float = Field(..., description="Average daily profit")
    best_day: str = Field(..., description="Best performing day")
    worst_day: str = Field(..., description="Worst performing day")


class ExtractDataResponse(MCPResponse):
    """Response from extract_backtest_data or extract_hyperopt_data MCP tools."""
    file_path: str = Field(..., description="Path to analyzed file")
    data: Dict[str, Any] = Field(..., description="Extracted data")


class ConfigurationData(BaseModel):
    """Freqtrade configuration structure."""
    exchange: Optional[Dict[str, Any]] = Field(None, description="Exchange configuration")
    stake_currency: Optional[str] = Field(None, description="Stake currency")
    stake_amount: Optional[Union[float, str]] = Field(None, description="Stake amount per trade")
    max_open_trades: Optional[int] = Field(None, description="Maximum concurrent trades")
    dry_run: Optional[bool] = Field(None, description="Dry run mode enabled")
    trading_mode: Optional[str] = Field(None, description="Trading mode")
    pairs: Optional[List[str]] = Field(None, description="Trading pairs")
    timeframe: Optional[str] = Field(None, description="Primary timeframe")
    features: Optional[Dict[str, Any]] = Field(None, description="Feature flags")
    
    class Config:
        extra = "allow"


class ConfigResponse(MCPResponse):
    """Response from create_config MCP tool."""
    config_path: str = Field(..., description="Path to created config file")
    template_used: str = Field(..., description="Template used")
    configuration: ConfigurationData = Field(..., description="Configuration created")
    message: str = Field(..., description="Success message")


class UserdirResponse(MCPResponse):
    """Response from create_userdir MCP tool."""
    userdir: str = Field(..., description="Path to created user directory")
    created_directories: List[str] = Field(..., description="Directories that were created")
    created_files: List[str] = Field(..., description="Files that were created")
    message: str = Field(..., description="Success message")


# Utility functions for response creation
def create_error_response(
    command: str,
    error: str,
    error_type: str = "Error",
    duration: Optional[float] = None
) -> MCPResponse:
    """Create a standardized error response."""
    return MCPResponse(
        command=command,
        success=False,
        error=error,
        error_type=error_type,
        duration_seconds=duration
    )


def create_success_response(
    command: str,
    duration: Optional[float] = None,
    **kwargs
) -> MCPResponse:
    """Create a standardized success response."""
    return MCPResponse(
        command=command,
        success=True,
        duration_seconds=duration,
        **kwargs
    )