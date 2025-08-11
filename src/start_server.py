#!/usr/bin/env python3
"""Convenience script to start the lrc-mcp server."""

import sys
import os

def main():
    """Start the lrc-mcp server."""
    try:
        # Import and run the main server
        from lrc_mcp.main import main as server_main
        print("Starting lrc-mcp server...")
        server_main()
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
