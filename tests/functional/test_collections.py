#!/usr/bin/env python3
"""
Test script for collection management commands.

This script demonstrates how to:
1. Create collections and collection sets
2. Remove collections and collection sets
3. Edit collections (rename/move)

Environment:
  LRC_MCP_HTTP_PORT (default 8765)
  LRC_MCP_PLUGIN_TOKEN (optional)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import time
from typing import Any, Dict

# Configuration
PORT = int(os.getenv("LRC_MCP_HTTP_PORT", "8765"))
TOKEN = os.getenv("LRC_MCP_PLUGIN_TOKEN")
BASE = f"http://127.0.0.1:{PORT}"


def post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send a POST request to the MCP server.
    
    Args:
        path: API endpoint path
        payload: JSON payload to send
        
    Returns:
        Response dictionary with status and data
    """
    url = f"{BASE}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    if TOKEN:
        req.add_header("X-Plugin-Token", TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return {"status": resp.status}
            try:
                return json.loads(body)
            except Exception:
                return {"status": resp.status, "raw": body}
    except Exception as e:
        return {"error": str(e)}


def test_create_collection() -> bool:
    """Test creating a collection.
    
    Returns:
        True if test passes, False otherwise
    """
    print("1. Testing create collection...")
    
    # Test creating a collection in root
    payload = {
        "type": "collection.create",
        "payload": {
            "name": "Test Collection",
            "parent_path": None
        }
    }
    result = post("/plugin/commands/enqueue", payload)
    print(f"   Create root collection result: {json.dumps(result, indent=2)}")
    
    if "command_id" not in result:
        print("   ✗ Failed to create collection")
        return False
    
    # Test creating a collection in a nested path
    payload2 = {
        "type": "collection.create",
        "payload": {
            "name": "Nested Collection",
            "parent_path": "Test Sets/Nature"
        }
    }
    result2 = post("/plugin/commands/enqueue", payload2)
    print(f"   Create nested collection result: {json.dumps(result2, indent=2)}")
    
    if "command_id" not in result2:
        print("   ⚠ Warning: Failed to create nested collection")
    
    print("   ✓ Collection creation commands queued")
    return True


def test_create_collection_set() -> bool:
    """Test creating a collection set.
    
    Returns:
        True if test passes, False otherwise
    """
    print("\n2. Testing create collection set...")
    
    # Test creating a collection set in root
    payload = {
        "type": "collection_set.create",
        "payload": {
            "name": "Test Sets",
            "parent_path": None
        }
    }
    result = post("/plugin/commands/enqueue", payload)
    print(f"   Create root collection set result: {json.dumps(result, indent=2)}")
    
    if "command_id" not in result:
        print("   ✗ Failed to create collection set")
        return False
    
    # Test creating a nested collection set
    payload2 = {
        "type": "collection_set.create",
        "payload": {
            "name": "Nature",
            "parent_path": "Test Sets"
        }
    }
    result2 = post("/plugin/commands/enqueue", payload2)
    print(f"   Create nested collection set result: {json.dumps(result2, indent=2)}")
    
    if "command_id" not in result2:
        print("   ⚠ Warning: Failed to create nested collection set")
    
    print("   ✓ Collection set creation commands queued")
    return True


def test_remove_collection() -> bool:
    """Test removing a collection.
    
    Returns:
        True if test passes, False otherwise
    """
    print("\n3. Testing remove collection...")
    
    payload = {
        "type": "collection.remove",
        "payload": {
            "collection_path": "Test Collection"
        }
    }
    result = post("/plugin/commands/enqueue", payload)
    print(f"   Remove collection result: {json.dumps(result, indent=2)}")
    
    if "command_id" in result:
        print("   ✓ Collection removal command queued")
        return True
    else:
        print("   ✗ Failed to queue collection removal command")
        return False


def test_remove_collection_set() -> bool:
    """Test removing a collection set.
    
    Returns:
        True if test passes, False otherwise
    """
    print("\n4. Testing remove collection set...")
    
    payload = {
        "type": "collection_set.remove",
        "payload": {
            "collection_set_path": "Test Sets"
        }
    }
    result = post("/plugin/commands/enqueue", payload)
    print(f"   Remove collection set result: {json.dumps(result, indent=2)}")
    
    if "command_id" in result:
        print("   ✓ Collection set removal command queued")
        return True
    else:
        print("   ✗ Failed to queue collection set removal command")
        return False


def test_edit_collection() -> bool:
    """Test editing a collection.
    
    Returns:
        True if test passes, False otherwise
    """
    print("\n5. Testing edit collection...")
    
    # First create a collection to edit
    create_payload = {
        "type": "collection.create",
        "payload": {
            "name": "Collection To Edit"
        }
    }
    create_result = post("/plugin/commands/enqueue", create_payload)
    if "command_id" not in create_result:
        print("   ✗ Failed to create collection for editing")
        return False
    
    # Wait a moment for the create command to process
    time.sleep(1)
    
    # Test renaming the collection
    edit_payload = {
        "type": "collection.edit",
        "payload": {
            "collection_path": "Collection To Edit",
            "new_name": "Edited Collection"
        }
    }
    edit_result = post("/plugin/commands/enqueue", edit_payload)
    print(f"   Edit collection result: {json.dumps(edit_result, indent=2)}")
    
    if "command_id" in edit_result:
        print("   ✓ Collection edit command queued")
        return True
    else:
        print("   ✗ Failed to queue collection edit command")
        return False


def test_collection_commands() -> bool:
    """Test all collection management commands.
    
    Returns:
        True if all tests pass, False otherwise
    """
    print("Testing Collection Management Commands")
    print("=" * 40)
    
    # Run all tests
    tests = [
        test_create_collection_set(),
        test_create_collection(),
        test_edit_collection(),
        test_remove_collection(),
        test_remove_collection_set()
    ]
    
    success = all(tests)
    
    if success:
        print("\n6. Collection commands are now queued and will be processed by the Lightroom plugin.")
        print("   Check the plugin logs at plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log")
        print("   to see the commands being claimed and completed.")
    
    return success


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        success = test_collection_commands()
        if success:
            print("\n🎉 All collection tests completed successfully!")
            print("\nTo verify command processing:")
            print("1. Check the plugin logs: plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log")
            print("2. Look for 'Command [id] completed ok=true' messages")
            return 0
        else:
            print("\n❌ Some collection tests failed!")
            return 1
    except Exception as e:
        print(f"\n💥 Collection test failed with exception: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
