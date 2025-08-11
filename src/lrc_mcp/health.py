"""Health check tool for the lrc-mcp server."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

import mcp.types as mcp_types


def get_health_tool() -> mcp_types.Tool:
    """Get the health check tool definition."""
    return mcp_types.Tool(
        name="lrc_mcp_health",
        description="Check the health status of the MCP server.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok"]},
                "serverTime": {"type": "string", "format": "date-time"},
                "version": {"type": "string"},
            },
            "required": ["status", "serverTime", "version"],
            "additionalProperties": False,
        },
    )


def handle_health_tool(version: str) -> Dict[str, Any]:
    """Handle the health check tool call."""
    return {
        "status": "ok",
        "serverTime": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "version": version,
    }
