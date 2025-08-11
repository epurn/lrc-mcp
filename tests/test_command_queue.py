#!/usr/bin/env python3
"""
Test script to demonstrate the full command queue functionality.

This script shows how to:
1. Enqueue different types of commands
2. Monitor the command processing
3. Verify the command queue is working properly
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any, Dict, Optional

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


def test_noop_command() -> bool:
    """Test enqueuing a noop command.
    
    Returns:
        True if test passes, False otherwise
    """
    print("1. Testing noop command...")
    noop_payload = {"type": "noop", "payload": {}}
    result = post("/plugin/commands/enqueue", noop_payload)
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    if "command_id" in result:
        print(f"   ✓ Noop command queued successfully: {result['command_id']}")
        return True
    else:
        print(f"   ✗ Failed to queue noop command: {result}")
        return False


def test_echo_command() -> bool:
    """Test enqueuing an echo command.
    
    Returns:
        True if test passes, False otherwise
    """
    print("\n2. Testing echo command...")
    echo_payload = {"type": "echo", "payload": {"message": "Hello from command queue test!"}}
    result = post("/plugin/commands/enqueue", echo_payload)
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    if "command_id" in result:
        print(f"   ✓ Echo command queued successfully: {result['command_id']}")
        return True
    else:
        print(f"   ✗ Failed to queue echo command: {result}")
        return False


def test_idempotency() -> bool:
    """Test command idempotency feature.
    
    Returns:
        True if test passes, False otherwise
    """
    print("\n3. Testing idempotency...")
    idempotent_payload = {
        "type": "echo", 
        "payload": {"message": "Idempotent command"},
        "idempotency_key": "test-key-123"
    }
    result1 = post("/plugin/commands/enqueue", idempotent_payload)
    result2 = post("/plugin/commands/enqueue", idempotent_payload)  # Same key
    
    print(f"   First enqueue: {json.dumps(result1, indent=2)}")
    print(f"   Second enqueue: {json.dumps(result2, indent=2)}")
    
    if result1.get("command_id") == result2.get("command_id"):
        print("   ✓ Idempotency working correctly - same command ID returned")
        return True
    else:
        print("   ⚠ Idempotency may not be working as expected")
        return False


def test_command_queue() -> bool:
    """Test the full command queue functionality.
    
    Returns:
        True if all tests pass, False otherwise
    """
    print("Testing MCP Command Queue Functionality")
    print("=" * 40)
    
    # Run all tests
    tests = [
        test_noop_command(),
        test_echo_command(),
        test_idempotency()
    ]
    
    success = all(tests)
    
    if success:
        print("\n4. Commands are now queued and will be processed by the Lightroom plugin.")
        print("   Check the plugin logs at plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log")
        print("   to see the commands being claimed and completed.")
    
    return success


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        success = test_command_queue()
        if success:
            print("\n🎉 All tests completed successfully!")
            print("\nTo verify command processing:")
            print("1. Check the plugin logs: plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log")
            print("2. Look for 'Command [id] completed ok=true' messages")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
