#!/usr/bin/env python3
"""
Test script to send an echo command and see the payload format.
"""

import json
import os
import urllib.request
from typing import Any, Dict

# Configuration
PORT = int(os.getenv("LRC_MCP_HTTP_PORT", "8765"))
TOKEN = os.getenv("LRC_MCP_PLUGIN_TOKEN")
BASE = f"http://127.0.0.1:{PORT}"


def post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
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


def test_echo():
    """Test echo command to see payload format."""
    print("Testing echo command...")
    
    payload = {
        "type": "echo",
        "payload": {
            "message": "Hello, World!",
            "test_value": "test123"
        }
    }
    result = post("/plugin/commands/enqueue", payload)
    print(f"Echo command result: {json.dumps(result, indent=2)}")
    
    if "command_id" in result:
        print(f"✓ Echo command queued with ID: {result['command_id']}")
        return result['command_id']
    else:
        print("✗ Failed to queue echo command")
        return None


if __name__ == "__main__":
    test_echo()
