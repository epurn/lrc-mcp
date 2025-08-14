"""Lightroom Classic tools for the lrc-mcp server."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Dict, List, Optional

import mcp.types as mcp_types

from lrc_mcp.adapters.lightroom import launch_lightroom, kill_lightroom, is_lightroom_process_running
from lrc_mcp.services.lrc_bridge import get_store

logger = logging.getLogger(__name__)


def get_launch_lightroom_tool() -> mcp_types.Tool:
    """Get the Lightroom launch tool definition."""
    return mcp_types.Tool(
        name="lrc_launch_lightroom",
        description="Does launch Lightroom Classic on Windows. Detects and gracefully terminates existing instances before launching. Uses external launcher for job object isolation. Returns process information and launch status.",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Optional explicit path to Lightroom.exe. If not provided, uses LRCLASSIC_PATH environment variable or default Windows installation path."}},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "launched": {"type": "boolean", "description": "True if a new process was spawned, False if existing instance was reused"},
                "pid": {"type": ["integer", "null"], "description": "Process ID of the running Lightroom instance, or null if not available"},
                "path": {"type": "string", "description": "Resolved path to the Lightroom executable that was launched"},
            },
            "required": ["launched", "pid", "path"],
            "additionalProperties": False,
        },
    )


def get_lightroom_version_tool() -> mcp_types.Tool:
    """Get the Lightroom version tool definition."""
    return mcp_types.Tool(
        name="lrc_lightroom_version",
        description="Does return Lightroom Classic version and enhanced process status information. Checks both plugin heartbeat and actual process presence to determine Lightroom status. Essential for verifying Lightroom connectivity before using other tools.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "waiting", "not_running"], "description": "ok if Lightroom is running and plugin is connected, waiting if no recent heartbeat but process may be starting, not_running if no process detected"},
                "running": {"type": "boolean", "description": "True if Lightroom process is currently running, False otherwise"},
                "lr_version": {"type": ["string", "null"], "description": "Detected Lightroom Classic version, or null if not available"},
                "last_seen": {"type": ["string", "null"], "format": "date-time", "description": "ISO-8601 timestamp of last plugin heartbeat, or null if never seen"},
            },
            "required": ["status", "running", "lr_version", "last_seen"],
            "additionalProperties": False,
        },
    )


def get_kill_lightroom_tool() -> mcp_types.Tool:
    """Get the Lightroom kill tool definition."""
    return mcp_types.Tool(
        name="lrc_kill_lightroom",
        description="Does gracefully terminate any running Lightroom Classic process. Sends WM_CLOSE message to Lightroom windows, waits up to 15 seconds for graceful shutdown, then force terminates if needed. Returns termination status and process information.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "killed": {"type": "boolean", "description": "True if a Lightroom process was running and successfully terminated, False if no process was running"},
                "previous_pid": {"type": ["integer", "null"], "description": "Process ID of the terminated Lightroom process, or null if no process was running"},
                "duration_ms": {"type": "integer", "description": "Time taken for the termination process in milliseconds"},
            },
            "required": ["killed", "previous_pid", "duration_ms"],
            "additionalProperties": False,
        },
    )


def handle_launch_lightroom_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the Lightroom launch tool call."""
    logger.info(f"handle_launch_lightroom_tool called with arguments: {arguments}")
    try:
        explicit_path: Optional[str] = None
        if arguments and isinstance(arguments.get("path"), str):
            explicit_path = arguments.get("path")
            logger.info(f"Using explicit path: {explicit_path}")
        
        logger.info("Calling launch_lightroom...")
        result = launch_lightroom(explicit_path)
        logger.info(f"launch_lightroom returned: {result}")
        response = {"launched": result.launched, "pid": result.pid, "path": result.path}
        logger.info(f"Returning response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in handle_launch_lightroom_tool: {e}", exc_info=True)
        raise


def handle_lightroom_version_tool() -> Dict[str, Any]:
    """Handle the Lightroom version tool call with enhanced health check."""
    # Check if Lightroom process is running
    process_running = is_lightroom_process_running()
    
    store = get_store()
    hb = store.get_last_heartbeat()
    
    if not hb:
        # No heartbeat ever received
        if process_running:
            # Process running but no heartbeat - likely starting up
            return {
                "status": "waiting",
                "running": True,
                "lr_version": None,
                "last_seen": None
            }
        else:
            # No process and no heartbeat
            return {
                "status": "not_running",
                "running": False,
                "lr_version": None,
                "last_seen": None
            }
    
    # Heartbeat exists, check if it's recent (within last 60 seconds)
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    if hb.received_at < now - timedelta(seconds=60):
        # Heartbeat is old
        if process_running:
            # Process running but old heartbeat - likely issue with plugin
            return {
                "status": "waiting",
                "running": True,
                "lr_version": hb.lr_version,
                "last_seen": hb.received_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            }
        else:
            # No process and old heartbeat
            return {
                "status": "not_running",
                "running": False,
                "lr_version": hb.lr_version,
                "last_seen": hb.received_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            }
    else:
        # Recent heartbeat
        if process_running:
            # All good - process running with recent heartbeat
            return {
                "status": "ok",
                "running": True,
                "lr_version": hb.lr_version,
                "last_seen": hb.received_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            }
        else:
            # Recent heartbeat but no process - unusual state
            return {
                "status": "waiting",
                "running": False,
                "lr_version": hb.lr_version,
                "last_seen": hb.received_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            }


def handle_kill_lightroom_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the Lightroom kill tool call."""
    logger.info(f"handle_kill_lightroom_tool called with arguments: {arguments}")
    try:
        result = kill_lightroom()
        logger.info(f"kill_lightroom returned: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in handle_kill_lightroom_tool: {e}", exc_info=True)
        raise
