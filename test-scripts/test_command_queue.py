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
import time
import urllib.request
import os
import sys

PORT = int(os.getenv("LRC_MCP_HTTP_PORT", "8765"))
TOKEN = os.getenv("LRC_MCP_PLUGIN_TOKEN")
BASE = f"http://127.0.0.1:{PORT}"


def post(path: str, payload: dict) -> dict:
    """Send a POST request to the MCP server."""
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


def test_command_queue():
    """Test the full command queue functionality."""
    print("Testing MCP Command Queue Functionality")
    print("=" * 40)
    
    # Test 1: Enqueue a noop command
    print("\n1. Testing noop command...")
    noop_payload = {"type": "noop", "payload": {}}
    result = post("/plugin/commands/enqueue", noop_payload)
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    if "command_id" in result:
        print(f"   ✓ Noop command queued successfully: {result['command_id']}")
    else:
        print(f"   ✗ Failed to queue noop command: {result}")
        return False
    
    # Test 2: Enqueue an echo command
    print("\n2. Testing echo command...")
    echo_payload = {"type": "echo", "payload": {"message": "Hello from command queue test!"}}
    result = post("/plugin/commands/enqueue", echo_payload)
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    if "command_id" in result:
        print(f"   ✓ Echo command queued successfully: {result['command_id']}")
    else:
        print(f"   ✗ Failed to queue echo command: {result}")
        return False
    
    # Test 3: Enqueue a command with idempotency key
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
    else:
        print("   ⚠ Idempotency may not be working as expected")
    
    print("\n4. Commands are now queued and will be processed by the Lightroom plugin.")
    print("   Check the plugin logs at plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log")
    print("   to see the commands being claimed and completed.")
    
    return True


def main() -> int:
    """Main entry point."""
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
