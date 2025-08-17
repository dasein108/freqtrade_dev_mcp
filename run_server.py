#!/usr/bin/env python3
"""
Freqtrade MCP Server launcher.
Handles import paths and provides a clean entry point for the MCP server.
"""

import sys
from pathlib import Path


def main():
    """Launch the Freqtrade MCP server."""
    # Add src directory to Python path
    src_dir = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_dir))
    
    try:
        # Import and run the server
        from server import main as server_main
        server_main()
    except ImportError as e:
        print(f"Failed to import server: {e}", file=sys.stderr)
        print("Make sure the src directory contains the server module.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()