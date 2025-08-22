"""Health check tool for the lrc-mcp server."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

import mcp.types as mcp_types


def get_health_tool() -> mcp_types.Tool:
    """Get the health check tool definition."""
    return mcp_types.Tool(
        name="lrc_mcp_health",
        title="Lightroom MCP Health",
        description="Does check the health status of the lrc-mcp server. Returns server status, current time, and version information. Use this to verify the server is running properly.",
        annotations=mcp_types.ToolAnnotations(
            title="Health",
            readOnlyHint=True,
            idempotentHint=True,
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok"], "description": "Server health status - always 'ok' when server is running"},
                "serverTime": {"type": "string", "format": "date-time", "description": "Current server time in ISO-8601 format"},
                "version": {"type": "string", "description": "Server version number"},
                "errorCode": {
                    "type": ["string", "null"],
                    "enum": ["NOT_FOUND", "VALIDATION", "DEPENDENCY_NOT_RUNNING", "TIMEOUT", "UNKNOWN"],
                    "description": "Structured error code for non-transport errors (optional)"
                },
            },
            "required": ["status", "serverTime", "version"],
            "additionalProperties": False,
        },
    )


def handle_health_tool(version: str) -> Dict[str, Any]:
    """Handle the health check tool call."""
    # Use timezone-aware datetime but format without timezone suffix to match expected "Z" format
    dt = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    # Remove the timezone suffix and add "Z" to indicate UTC
    server_time = dt.isoformat().replace('+00:00', '') + "Z"
    return {
        "status": "ok",
        "serverTime": server_time,
        "version": version,
    }
