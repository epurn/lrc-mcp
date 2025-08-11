#!/usr/bin/env python3
"""
Enqueue a test command (noop or echo) into the local lrc-mcp command queue.

Usage:
  python tests/enqueue_echo.py            # enqueue a noop
  python tests/enqueue_echo.py hello      # enqueue an echo with message "hello"

Environment:
  LRC_MCP_HTTP_PORT (default 8765)
  LRC_MCP_PLUGIN_TOKEN (optional)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
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


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if len(sys.argv) > 1:
        # echo command
        payload = {"type": "echo", "payload": {"message": " ".join(sys.argv[1:])}}
    else:
        payload = {"type": "noop", "payload": {}}
    res = post("/plugin/commands/enqueue", payload)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
