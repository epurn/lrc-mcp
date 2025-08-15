"""Test execution tools for the lrc-mcp server."""

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime, timedelta, timezone

import mcp.types as mcp_types

from lrc_mcp.services.lrc_bridge import get_queue, get_store


def _is_lightroom_running() -> bool:
    """Check if Lightroom is running and the plugin is connected.
    
    Returns:
        True if Lightroom is running and plugin is connected, False otherwise
    """
    store = get_store()
    heartbeat = store.get_last_heartbeat()
    
    if not heartbeat:
        return False
    
    # Check if the heartbeat is recent (within last 30 seconds)
    now = datetime.now(timezone.utc)
    if heartbeat.received_at < now - timedelta(seconds=30):
        return False
    
    return True


def _check_lightroom_dependency() -> Dict[str, Any] | None:
    """Check if Lightroom is running and return error response if not.
    
    Returns:
        None if Lightroom is running, error response dict if not
    """
    if not _is_lightroom_running():
        return {
            "status": "error",
            "error": "Lightroom Classic is not running or plugin is not connected. Please start Lightroom and ensure the lrc-mcp plugin is loaded.",
            "command_id": None,
            "message": "Lightroom Classic is not running or plugin is not connected.",
        }
    return None


def get_run_tests_tool() -> mcp_types.Tool:
    """Get the run tests tool definition."""
    return mcp_types.Tool(
        name="lrc_run_tests",
        description="Does run the in-situ test suite for the lrc-mcp Lightroom plugin. Requires Lightroom to be running with plugin connected. Tests run asynchronously and results are logged to the plugin log file.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "pending", "error"], "description": "Operation status: ok (command sent), pending (command queued), error (failed)"},
                "command_id": {"type": ["string", "null"], "description": "Command identifier for tracking the test execution"},
                "message": {"type": "string", "description": "Status message"},
                "error": {"type": ["string", "null"], "description": "Error message if operation failed, null otherwise"}
            },
            "required": ["status", "command_id", "message", "error"],
            "additionalProperties": False,
        },
    )


def handle_run_tests_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the run tests tool call."""
    # Check if Lightroom is running first
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        # Make sure we return all required fields
        return {
            "status": "error",
            "command_id": None,
            "message": "Lightroom dependency check failed",
            "error": dependency_error.get("error", "Unknown dependency error")
        }
    
    # Enqueue the test command
    queue = get_queue()
    command_id = queue.enqueue(
        type="run_tests",
        payload={}
    )
    
    return {
        "status": "ok",
        "command_id": command_id,
        "message": "Test suite started - check plugin logs for results",
        "error": None
    }
