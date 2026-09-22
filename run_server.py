#!/usr/bin/env python3
"""
Freqtrade MCP Server launcher.
Handles import paths and provides a clean entry point for the MCP server.
"""

import sys
from pathlib import Path


def main():
    """Launch the Freqtrade MCP server."""
    # Import `src` as a package so relative imports inside it resolve
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))

    try:
        from src.server import main as server_main

        server_main()
    except ImportError as e:
        print(f"Failed to import server: {e}", file=sys.stderr)
        print(
            f"Check that dependencies are installed and {project_root / 'src'} exists.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
