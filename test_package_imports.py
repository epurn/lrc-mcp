#!/usr/bin/env python3
"""Test script to verify all package imports work correctly with absolute imports."""

import sys
import os

def test_imports():
    """Test that all modules can be imported correctly using package names."""
    tests = [
        # Core modules
        ("lrc_mcp", "package"),
        ("lrc_mcp.__version__", "version"),
        ("lrc_mcp.main", "main module"),
        ("lrc_mcp.server", "server module"),
        ("lrc_mcp.health", "health module"),
        ("lrc_mcp.lightroom", "lightroom module"),
        ("lrc_mcp.models", "models module"),
        ("lrc_mcp.utils", "utils module"),
        
        # Subpackages
        ("lrc_mcp.adapters", "adapters package"),
        ("lrc_mcp.adapters.lightroom", "adapters.lightroom module"),
        ("lrc_mcp.api", "api package"),
        ("lrc_mcp.api.routes", "api.routes module"),
        ("lrc_mcp.infra", "infra package"),
        ("lrc_mcp.infra.http", "infra.http module"),
        ("lrc_mcp.services", "services package"),
        ("lrc_mcp.services.lrc_bridge", "services.lrc_bridge module"),
        
        # Deployment modules
        ("lrc_mcp.uvicorn_config", "uvicorn_config module"),
        ("lrc_mcp.http_server", "http_server module"),
        ("lrc_mcp.asgi", "asgi module"),
    ]
    
    success_count = 0
    failed_imports = []
    
    for import_name, description in tests:
        try:
            __import__(import_name)
            print(f"✓ {description} ({import_name})")
            success_count += 1
        except ImportError as e:
            print(f"✗ {description} ({import_name}): {e}")
            failed_imports.append((import_name, str(e)))
    
    print(f"\nResults: {success_count}/{len(tests)} imports successful")
    
    if failed_imports:
        print("\nFailed imports:")
        for import_name, error in failed_imports:
            print(f"  - {import_name}: {error}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing package imports with absolute imports...")
    success = test_imports()
    sys.exit(0 if success else 1)
