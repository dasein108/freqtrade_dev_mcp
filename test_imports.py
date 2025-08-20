#!/usr/bin/env python3
"""Test script to verify all imports and models are working correctly."""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all critical imports."""
    print("Testing imports...")
    
    # Test base model imports
    try:
        from src.models.base_models import (
            MCPBaseResponse,
            CacheFileInfo,
            CandleData,
            DownloadCandlesResponse,
            ReadCandlesResponse,
            PerformanceMetrics,
            BacktestResponse,
            HyperoptResponse,
            create_error_response,
            create_success_response
        )
        print("✅ Base models imported successfully")
    except Exception as e:
        print(f"❌ Base models import failed: {e}")
        return False
    
    # Test MCP response import
    try:
        from src.models.mcp_responses import MCPResponse
        print("✅ MCP response imported successfully")
    except Exception as e:
        print(f"❌ MCP response import failed: {e}")
        return False
    
    # Test strategy agent models import
    try:
        from strategy_agent.models import (
            MCPResponse,
            DownloadCandlesResponse,
            ReadCandlesResponse,
            BacktestResponse,
            HyperoptResponse
        )
        print("✅ Strategy agent models imported successfully")
    except Exception as e:
        print(f"❌ Strategy agent models import failed: {e}")
        return False
    
    # Test MCP client import
    try:
        from strategy_agent.mcp_client import FreqtradeMCPClient
        print("✅ MCP client imported successfully")
    except Exception as e:
        print(f"❌ MCP client import failed: {e}")
        return False
    
    # Test command imports
    try:
        from src.commands.download_candles import DownloadCandlesCommand
        from src.commands.read_candles import ReadCandlesCommand
        print("✅ Commands imported successfully")
    except Exception as e:
        print(f"❌ Commands import failed: {e}")
        return False
    
    # Test server import
    try:
        from src.server import FreqtradeMCPServer
        print("✅ MCP server imported successfully")
    except Exception as e:
        print(f"❌ MCP server import failed: {e}")
        return False
    
    # Test model validation
    try:
        # Create a sample response
        response = DownloadCandlesResponse(
            command="download_candles",
            success=True,
            pairs=["BTC/USDT"],
            timeframes=["1h"],
            cache_files=[],
            total_candles=0
        )
        print(f"✅ Model validation working: {response.command}")
    except Exception as e:
        print(f"❌ Model validation failed: {e}")
        return False
    
    return True

def test_model_consistency():
    """Test that models are consistent between server and client."""
    print("\nTesting model consistency...")
    
    try:
        from src.models.base_models import DownloadCandlesResponse as ServerModel
        from strategy_agent.models import DownloadCandlesResponse as ClientModel
        
        # Both should be the same class
        if ServerModel is ClientModel:
            print("✅ Server and client models are the same (good!)")
        else:
            print("⚠️  Server and client models are different instances")
        
        # Test creating instances
        server_response = ServerModel(
            command="test",
            success=True,
            pairs=["BTC/USDT"],
            timeframes=["1h"],
            cache_files=[],
            total_candles=100
        )
        
        # Should be able to use client model to validate server response
        client_response = ClientModel(**server_response.model_dump())
        
        if client_response.total_candles == server_response.total_candles:
            print("✅ Model data consistency verified")
        else:
            print("❌ Model data inconsistency detected")
            return False
            
    except Exception as e:
        print(f"❌ Model consistency test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("MCP System Import and Model Validation Test")
    print("=" * 60)
    
    success = True
    
    # Run import tests
    if not test_imports():
        success = False
    
    # Run model consistency tests
    if not test_model_consistency():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed! The MCP system is ready.")
    else:
        print("❌ Some tests failed. Please review the errors above.")
    print("=" * 60)
    
    sys.exit(0 if success else 1)