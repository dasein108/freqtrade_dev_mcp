#!/usr/bin/env python3
"""Test the enhanced command success analysis."""

import sys
import os
from pathlib import Path

# Add paths for import
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from src.commands.base import BaseCommand
from src.config import Config


class TestCommand(BaseCommand):
    """Test command for testing the base functionality."""
    
    async def execute(self, **kwargs):
        """Dummy execute method."""
        return {"test": "result"}


def test_success_analysis():
    """Test the _analyze_command_success method."""
    print("Testing command success analysis...")
    
    # Create a test command instance
    config = Config()
    cmd = TestCommand(config)
    
    # Test cases: (returncode, stdout, stderr, expected_success)
    test_cases = [
        # Basic success cases - stdout with no stderr
        (0, "Backtesting finished successfully", "", True),
        (0, "Download complete: 100 candles saved", "", True),
        (0, "Some output", "", True),
        
        # Basic failure cases - non-zero exit code
        (1, "", "", False),
        (1, "Some output", "", False),
        (2, "Some output", "ERROR: Critical failure", False),
        
        # Success with both stdout and stderr (warnings are OK)
        (0, "Operation completed", "WARNING: Deprecated feature used", True),
        (0, "Data downloaded", "UserWarning: Some warning", True),
        (0, "Some output", "Some stderr", True),
        
        # Failure: stderr with content but no stdout
        (0, "", "CRITICAL: Database connection failed", False),
        (0, "", "Exception: Strategy not found", False),
        (0, "", "Any error message", False),
        (0, "", "Failed to authenticate", False),
        
        # Edge cases
        (0, "", "", True),  # No output but return code 0
        (0, "   ", "   ", True),  # Whitespace only
    ]
    
    for i, (returncode, stdout, stderr, expected) in enumerate(test_cases):
        result = cmd._analyze_command_success(returncode, stdout, stderr)
        status = "✅" if result == expected else "❌"
        print(f"  {status} Test {i+1}: returncode={returncode}, expected={expected}, got={result}")
        if result != expected:
            print(f"     stdout: '{stdout[:50]}...'")
            print(f"     stderr: '{stderr[:50]}...'")
            
        assert result == expected, f"Test {i+1} failed: expected {expected}, got {result}"
    
    print("✅ All command analysis tests passed!")


def test_real_world_scenarios():
    """Test with real-world Freqtrade output patterns."""
    print("\nTesting real-world scenarios...")
    
    config = Config()
    cmd = TestCommand(config)
    
    # Simulate real freqtrade outputs
    scenarios = [
        # Successful command - has stdout, no stderr
        {
            "returncode": 0,
            "stdout": "Download complete: 1000 candles saved.",
            "stderr": "",
            "expected": True
        },
        
        # Failed command - no stdout, has stderr  
        {
            "returncode": 0,
            "stdout": "",
            "stderr": "ERROR: No data found for the specified timerange",
            "expected": False
        },
        
        # Successful with warnings - has both stdout and stderr
        {
            "returncode": 0,
            "stdout": "Backtesting finished: 15.5% profit",
            "stderr": "WARNING: Deprecated parameter used",
            "expected": True
        },
        
        # Failed command - exit code failure
        {
            "returncode": 1,
            "stdout": "Starting backtesting...",
            "stderr": "Strategy import failed",
            "expected": False
        }
    ]
    
    for i, scenario in enumerate(scenarios):
        result = cmd._analyze_command_success(
            scenario["returncode"],
            scenario["stdout"], 
            scenario["stderr"]
        )
        expected = scenario["expected"]
        status = "✅" if result == expected else "❌"
        print(f"  {status} Scenario {i+1}: expected={expected}, got={result}")
        
        assert result == expected, f"Scenario {i+1} failed"
    
    print("✅ All real-world scenario tests passed!")


if __name__ == "__main__":
    test_success_analysis()
    test_real_world_scenarios()
    print("\n🎉 All command analysis tests completed successfully!")
    print("💡 Enhanced error detection is working correctly!")