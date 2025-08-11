#!/usr/bin/env python3
"""Test script to verify uvicorn deployment configuration."""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported correctly."""
    try:
        from lrc_mcp.http_server import app
        print("✓ http_server import successful")
        
        from lrc_mcp.uvicorn_config import UVICORN_CONFIG, DEV_CONFIG
        print("✓ uvicorn_config import successful")
        
        from lrc_mcp.infra.http import create_app
        print("✓ infra.http import successful")
        
        print("\nAll imports successful! Uvicorn deployment is ready.")
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing uvicorn deployment configuration...")
    success = test_imports()
    sys.exit(0 if success else 1)
