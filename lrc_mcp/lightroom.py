"""Lightroom Classic tools for the lrc-mcp server."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

import mcp.types as mcp_types

from lrc_mcp.adapters.lightroom import launch_lightroom
from lrc_mcp.services.lrc_bridge import get_store


def get_launch_lightroom_tool() -> mcp_types.Tool:
    """Get the Lightroom launch tool definition."""
    return mcp_types.Tool(
        name="lrc_launch_lightroom",
        description="Launch Lightroom Classic (Windows). Optional path override via LRCLASSIC_PATH or argument.",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "launched": {"type": "boolean"},
                "pid": {"type": ["integer", "null"]},
                "path": {"type": "string"},
            },
            "required": ["launched", "pid", "path"],
            "additionalProperties": False,
        },
    )


def get_lightroom_version_tool() -> mcp_types.Tool:
    """Get the Lightroom version tool definition."""
    return mcp_types.Tool(
        name="lrc_lightroom_version",
        description="Return the last known Lightroom Classic version as reported by the plugin.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "waiting"]},
                "lr_version": {"type": ["string", "null"]},
                "last_seen": {"type": ["string", "null"], "format": "date-time"},
            },
            "required": ["status", "lr_version", "last_seen"],
            "additionalProperties": False,
        },
    )


def handle_launch_lightroom_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the Lightroom launch tool call."""
    explicit_path: Optional[str] = None
    if arguments and isinstance(arguments.get("path"), str):
        explicit_path = arguments.get("path")
    result = launch_lightroom(explicit_path)
    return {"launched": result.launched, "pid": result.pid, "path": result.path}


def handle_lightroom_version_tool() -> Dict[str, Any]:
    """Handle the Lightroom version tool call."""
    store = get_store()
    hb = store.get_last_heartbeat()
    if not hb:
        return {"status": "waiting", "lr_version": None, "last_seen": None}
    return {
        "status": "ok",
        "lr_version": hb.lr_version,
        "last_seen": hb.received_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
