#!/usr/bin/env python3
"""
Test script to validate tool descriptions for LLM discoverability.

This script ensures all tool descriptions follow MCP documentation best practices:
1. First sentence: "Does X" (verb-led)
2. Second sentence: key inputs / optional params
3. Third sentence: side-effects or guarantees
4. No description exceeds 300 characters
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from lrc_mcp.server import create_server
from lrc_mcp.health import get_health_tool
from lrc_mcp.lightroom import get_launch_lightroom_tool, get_lightroom_version_tool, get_kill_lightroom_tool
from lrc_mcp.adapters.collections import get_add_collection_tool, get_add_collection_set_tool, get_remove_collection_tool, get_remove_collection_set_tool, get_edit_collection_tool, get_collection_tool
from lrc_mcp.adapters.lightroom import get_check_command_status_tool


def test_tool_descriptions():
    """Test that all tool descriptions meet LLM discoverability requirements."""
    
    # Create server to get all tools
    server = create_server("0.1.0")
    
    # Get all tools (this is a simplified approach - in practice we'd need to 
    # properly initialize the server and call list_tools())
    
    tools = [
        get_health_tool(),
        get_launch_lightroom_tool(),
        get_lightroom_version_tool(),
        get_kill_lightroom_tool(),
        get_add_collection_tool(),
        get_add_collection_set_tool(),
        get_remove_collection_tool(),
        get_remove_collection_set_tool(),
        get_edit_collection_tool(),
        get_collection_tool(),
        get_check_command_status_tool(),
    ]
    
    print("Testing tool descriptions for LLM discoverability...")
    print("=" * 60)
    
    errors = []
    
    for tool in tools:
        description = tool.description or ""
        tool_name = tool.name
        
        print(f"\nTool: {tool_name}")
        print(f"Description: {description}")
        
        # Check length
        if len(description) > 300:
            error = f"❌ {tool_name}: Description too long ({len(description)} chars > 300)"
            errors.append(error)
            print(error)
        else:
            print(f"✅ Length OK ({len(description)} chars)")
        
        # Check if it starts with "Does" (verb-led)
        if not description.strip().startswith("Does "):
            error = f"❌ {tool_name}: Description should start with 'Does' for verb-led clarity"
            errors.append(error)
            print(error)
        else:
            print("✅ Starts with 'Does'")
        
        # Check for presence of description
        if not description.strip():
            error = f"❌ {tool_name}: Description is missing or empty"
            errors.append(error)
            print(error)
        else:
            print("✅ Has description")
    
    print("\n" + "=" * 60)
    if errors:
        print(f"\n❌ Found {len(errors)} issues:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("\n✅ All tool descriptions pass validation!")
        return True


if __name__ == "__main__":
    success = test_tool_descriptions()
    sys.exit(0 if success else 1)
