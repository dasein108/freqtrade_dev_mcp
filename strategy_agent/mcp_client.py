"""
MCP Client wrapper for stdio communication with Freqtrade MCP Server
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List, Union

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

# Import Pydantic models for response validation
from .models import (
    DownloadCandlesResponse,
    BacktestResponse,
    HyperoptResponse,
    MCPResponse
)

logger = logging.getLogger(__name__)


class FreqtradeMCPClient:
    """
    Client for communicating with Freqtrade MCP Server via stdio
    """
    
    def __init__(self, server_path: Optional[Path] = None):
        """
        Initialize MCP client
        
        Args:
            server_path: Path to the MCP server script (run_server.py)
        """
        # Find server path
        if server_path:
            self.server_path = server_path
        else:
            # Default to run_server.py in parent directory
            self.server_path = Path(__file__).parent.parent / "run_server.py"
        
        if not self.server_path.exists():
            raise FileNotFoundError(f"MCP server not found at {self.server_path}")
        
        self.session: Optional[ClientSession] = None
        self.server_params: Optional[StdioServerParameters] = None
        self._stdio_context = None
        self._session_context = None
        self._connected = False
        
        logger.info(f"MCP client initialized with server at {self.server_path}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()
    
    async def start(self):
        """Start the MCP server subprocess and establish connection"""
        if self._connected:
            logger.warning("MCP client already connected")
            return
        
        try:
            # Prepare server parameters
            self.server_params = StdioServerParameters(
                command=sys.executable,
                args=[str(self.server_path)],
                env=None  # Will inherit current environment
            )
            
            logger.info("Starting MCP server subprocess...")
            
            # Create the stdio client context
            self._stdio_context = stdio_client(self.server_params)
            read_stream, write_stream = await self._stdio_context.__aenter__()
            
            # Create and initialize session
            self.session = ClientSession(read_stream, write_stream)
            self._session_context = self.session
            await self._session_context.__aenter__()
            
            # Initialize the connection
            await self.session.initialize()
            
            self._connected = True
            logger.info("MCP client connected successfully")
            
            # List available tools to verify connection
            tools = await self.session.list_tools()
            logger.info(f"Available tools: {[t.name for t in tools.tools]}")
                    
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            await self.stop()  # Clean up on failure
            raise
    
    async def stop(self):
        """Stop the MCP server and close connection"""
        if not self._connected:
            return
        
        logger.info("Stopping MCP client...")
        
        try:
            # Close session context
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
                self._session_context = None
            
            # Close stdio context
            if self._stdio_context:
                await self._stdio_context.__aexit__(None, None, None)
                self._stdio_context = None
                
        except Exception as e:
            logger.error(f"Error stopping MCP client: {e}")
        finally:
            self._connected = False
            self.session = None
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the MCP server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        if not self._connected or not self.session:
            raise RuntimeError("MCP client not connected. Call start() first.")
        
        try:
            logger.debug(f"Calling tool: {tool_name} with args: {arguments}")
            
            # Call the tool
            result = await self.session.call_tool(tool_name, arguments)
            
            # Parse the result
            if result and result.content:
                # Extract text content from the result
                for content in result.content:
                    if hasattr(content, 'text'):
                        # Parse JSON response if possible
                        try:
                            parsed_result = json.loads(content.text)
                            logger.debug(f"Tool {tool_name} returned: {parsed_result}")
                            
                            # Optionally validate with Pydantic models
                            validated_result = self._validate_response(tool_name, parsed_result)
                            return validated_result if validated_result else parsed_result
                            
                        except json.JSONDecodeError:
                            logger.warning(f"Tool {tool_name} returned non-JSON content: {content.text[:200]}")
                            return {"success": False, "error": f"Invalid JSON response", "raw_content": content.text}
            
            logger.warning(f"Tool {tool_name} returned no content or empty result")
            return {"success": False, "error": "No content in response", "raw_result": str(result)}
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Tool call {tool_name} failed: {e}")
            logger.debug(f"Full traceback: {error_trace}")
            return {"success": False, "error": str(e), "error_type": type(e).__name__, "traceback": error_trace}
    
    def _validate_response(self, tool_name: str, response_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate MCP response using appropriate Pydantic model.
        
        Args:
            tool_name: Name of the tool that generated the response
            response_data: Raw response data
            
        Returns:
            Validated response data or None if validation fails
        """
        try:
            # Map tool names to their response models
            model_mapping = {
                "download_candles": DownloadCandlesResponse,
                "backtest_strategy": BacktestResponse,
                "hyperopt_strategy": HyperoptResponse,
                # Add more mappings as needed
            }
            
            model_class = model_mapping.get(tool_name)
            if not model_class:
                # No specific model for this tool, use generic validation
                try:
                    MCPResponse(**response_data)
                    logger.debug(f"Generic MCP response validation passed for {tool_name}")
                except ValidationError as e:
                    logger.warning(f"Generic MCP response validation failed for {tool_name}: {e}")
                return None
            
            # Validate with specific model
            validated_response = model_class(**response_data)
            logger.debug(f"Response validation passed for {tool_name}")
            return validated_response.dict()
            
        except ValidationError as e:
            logger.warning(f"Response validation failed for {tool_name}: {e}")
            logger.debug(f"Raw response data: {response_data}")
            # Return None to use original response
            return None
        except Exception as e:
            logger.error(f"Unexpected error during response validation for {tool_name}: {e}")
            return None
    
    async def download_candles(
        self,
        pairs: List[str],
        timeframe: str,
        days: int = 365,
        exchange: str = "binance"
    ) -> Union[Dict[str, Any], DownloadCandlesResponse]:
        """
        Download candle data
        
        Args:
            pairs: List of trading pairs
            timeframe: Timeframe (1h, 4h, etc.)
            days: Number of days to download
            exchange: Exchange name
            
        Returns:
            Download result
        """
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Detect if any pairs are futures (ending with :USDT or :BUSD)
        # Futures pairs need trading_mode set to "futures"
        is_futures = any(":USDT" in pair or ":BUSD" in pair for pair in pairs)
        
        params = {
            "pairs": pairs,
            "timeframes": [timeframe],  # MCP server expects array
            "date_range": f"last {days} days",  # MCP server expects natural language
            "exchange": exchange
        }
        
        # Add trading_mode for futures pairs
        if is_futures:
            params["trading_mode"] = "futures"
            logger.info(f"Detected futures pairs, setting trading_mode=futures")
        
        return await self.call_tool("download_candles", params)
    
    async def backtest_strategy(
        self,
        strategy: str,
        timeframe: str = "1h",
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run backtest for a strategy
        
        Args:
            strategy: Strategy name
            timeframe: Timeframe
            timerange: Time range for backtest
            pairs: Optional list of pairs to detect trading mode
            **kwargs: Additional backtest parameters
            
        Returns:
            Backtest results
        """
        params = {
            "strategy_name": strategy,  # MCP expects strategy_name, not strategy
            "timeframe": timeframe
        }
        
        if timerange:
            params["timerange"] = timerange
        
        # Auto-detect futures mode from pairs
        if pairs:
            is_futures = any(":USDT" in pair or ":BUSD" in pair for pair in pairs)
            if is_futures:
                params["trading_mode"] = "futures"
                logger.info("Detected futures pairs for backtest, setting trading_mode=futures")
        
        params.update(kwargs)
        
        return await self.call_tool("backtest_strategy", params)
    
    async def hyperopt_strategy(
        self,
        strategy: str,
        epochs: int = 100,
        spaces: List[str] = None,
        loss_function: str = "SharpeHyperOptLoss",
        pairs: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run hyperopt optimization
        
        Args:
            strategy: Strategy name
            epochs: Number of epochs
            spaces: Hyperopt spaces
            loss_function: Loss function to use
            pairs: Optional list of pairs to detect trading mode
            **kwargs: Additional hyperopt parameters
            
        Returns:
            Hyperopt results
        """
        # MCP server requires these exact parameter names
        params = {
            "strategy_name": strategy,  # MCP expects strategy_name, not strategy
            "epochs": epochs,
            "loss_function": loss_function  # MCP expects loss_function, not loss
        }
        
        # Required parameters - must be provided
        if not pairs:
            raise ValueError("pairs parameter is required for hyperopt")
        params["pairs"] = pairs
        
        # Add timerange - MCP server requires this
        if "timerange" not in kwargs:
            # Default to last year if not specified
            params["timerange"] = "last year"
        
        if spaces:
            if isinstance(spaces, list):
                params["spaces"] = ",".join(spaces)  # MCP expects comma-separated string
            else:
                params["spaces"] = spaces
        
        # Auto-detect futures mode from pairs
        if pairs:
            is_futures = any(":USDT" in pair or ":BUSD" in pair for pair in pairs)
            if is_futures:
                params["trading_mode"] = "futures"
                logger.info("Detected futures pairs for hyperopt, setting trading_mode=futures")
        
        params.update(kwargs)
        
        return await self.call_tool("hyperopt_strategy", params)
    
    async def extract_backtest_data(
        self,
        result_path: str,
        output_format: str = "summary"
    ) -> Dict[str, Any]:
        """
        Extract data from backtest results
        
        Args:
            result_path: Path to backtest result file
            output_format: Output format (summary, full, trades)
            
        Returns:
            Extracted data
        """
        return await self.call_tool("extract_backtest_data", {
            "result_path": result_path,
            "output_format": output_format
        })
    
    async def extract_hyperopt_data(
        self,
        hyperopt_path: str,
        output_format: str = "summary",
        max_trials: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract data from hyperopt results
        
        Args:
            hyperopt_path: Path to hyperopt result file
            output_format: Output format
            max_trials: Maximum number of trials to extract
            
        Returns:
            Extracted data
        """
        params = {
            "hyperopt_path": hyperopt_path,
            "output_format": output_format
        }
        
        if max_trials:
            params["max_trials"] = max_trials
        
        return await self.call_tool("extract_hyperopt_data", params)
    async def list_results(
        self,
        result_type: str = "backtest",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        List available results
        
        Args:
            result_type: Type of results (backtest, hyperopt)
            limit: Maximum number of results
            
        Returns:
            List of results
        """
        return await self.call_tool("list_results", {
            "result_type": result_type,
            "limit": limit
        })
    
    async def search_results(
        self,
        query: str,
        result_type: str = "backtest",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for results
        
        Args:
            query: Search query
            result_type: Type of results
            limit: Maximum number of results
            
        Returns:
            Search results
        """
        return await self.call_tool("search_results", {
            "query": query,
            "result_type": result_type,
            "limit": limit
        })
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected


async def test_connection():
    """Test MCP client connection"""
    client = FreqtradeMCPClient()
    
    try:
        async with client:
            print("✅ Connected to MCP server")
            
            # Test tool call
            result = await client.list_results(limit=5)
            print(f"📊 Found {len(result.get('results', []))} results")
            
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test the client
    asyncio.run(test_connection())