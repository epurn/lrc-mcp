#!/usr/bin/env python3
"""
Functional test for photo metadata commands (E9-S1).

This script demonstrates how to:
1. Enqueue a photo_metadata.get command
2. Enqueue a photo_metadata.bulk_get command

Environment:
  LRC_MCP_HTTP_PORT (default 8765)
  LRC_MCP_PLUGIN_TOKEN (optional)
References:
- MCP docs: see local .resources/MCP-docs
- Lightroom SDK: see local .resources/LrC (catalog access rules, metadata)
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


def test_photo_metadata_get() -> bool:
    """Queue a photo_metadata.get command."""
    print("1) Enqueue photo_metadata.get...")
    payload = {
        "type": "photo_metadata.get",
        "payload": {
            # Provide either local_id or file_path; these are examples.
            # Adjust to your catalog as needed.
            "photo": {"local_id": "1"},
            "fields": ["title", "rating", "capture_time"]
        }
    }
    result = post("/plugin/commands/enqueue", payload)
    print(f"   Result: {json.dumps(result, indent=2)}")
    if "command_id" in result:
        print("   ✓ Command queued (plugin will claim/process asynchronously)")
        return True
    print("   ✗ Failed to enqueue get command")
    return False


def test_photo_metadata_bulk_get() -> bool:
    """Queue a photo_metadata.bulk_get command."""
    print("\n2) Enqueue photo_metadata.bulk_get...")
    payload = {
        "type": "photo_metadata.bulk_get",
        "payload": {
            "photos": [
                {"local_id": "1"},
                {"file_path": "C:/path/to/nonexistent.jpg"}  # Expect PHOTO_NOT_FOUND for demo
            ],
            "fields": ["keywords", "rating"]
        }
    }
    result = post("/plugin/commands/enqueue", payload)
    print(f"   Result: {json.dumps(result, indent=2)}")
    if "command_id" in result:
        print("   ✓ Command queued (plugin will claim/process asynchronously)")
        return True
    print("   ✗ Failed to enqueue bulk_get command")
    return False


def main() -> int:
    print("Functional test: Photo Metadata (E9-S1)")
    print("=" * 50)
    tests = [
        test_photo_metadata_get(),
        test_photo_metadata_bulk_get(),
    ]
    if all(tests):
        print("\nNext steps:")
        print("- Ensure Lightroom is running with the plugin loaded.")
        print("- Check plugin logs at plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log for claim/completion.")
        print("- Use the MCP tool 'check_command_status' with command_id to fetch results if needed.")
        return 0
    print("\n❌ One or more enqueue operations failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
