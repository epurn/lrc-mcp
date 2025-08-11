"""Collection management tools for the lrc-mcp server."""

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
            "created": None,
            "removed": None,
            "updated": None,
            "collection": None
        }
    return None


def get_add_collection_tool() -> mcp_types.Tool:
    """Get the add collection tool definition."""
    return mcp_types.Tool(
        name="lrc_add_collection",
        description="Create a new collection in Lightroom Classic.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the collection to create"},
                "parent_path": {
                    "type": ["string", "null"], 
                    "description": "Parent collection path (e.g., 'Sets/Nature'; null or '' means root)"
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "description": "Wait timeout in seconds (default 5; 0 to return immediately)"
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "pending", "error"]},
                "created": {"type": ["boolean", "null"]},
                "collection": {
                    "type": ["object", "null"],
                    "properties": {
                        "id": {"type": ["string", "null"]},
                        "name": {"type": "string"},
                        "path": {"type": "string"}
                    },
                    "required": ["id", "name", "path"],
                    "additionalProperties": False
                },
                "command_id": {"type": ["string", "null"]},
                "error": {"type": ["string", "null"]}
            },
            "required": ["status", "created", "collection", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def get_remove_collection_tool() -> mcp_types.Tool:
    """Get the remove collection tool definition."""
    return mcp_types.Tool(
        name="lrc_remove_collection",
        description="Remove a collection from Lightroom Classic.",
        inputSchema={
            "type": "object",
            "properties": {
                "collection_path": {
                    "type": "string",
                    "description": "Collection path (e.g., 'Sets/Nature/Birds' or just 'Birds' at root)"
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "description": "Wait timeout in seconds (default 5; 0 to return immediately)"
                }
            },
            "required": ["collection_path"],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "pending", "error"]},
                "removed": {"type": ["boolean", "null"]},
                "command_id": {"type": ["string", "null"]},
                "error": {"type": ["string", "null"]}
            },
            "required": ["status", "removed", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def get_edit_collection_tool() -> mcp_types.Tool:
    """Get the edit collection tool definition."""
    return mcp_types.Tool(
        name="lrc_edit_collection",
        description="Edit (rename/move) a collection in Lightroom Classic.",
        inputSchema={
            "type": "object",
            "properties": {
                "collection_path": {
                    "type": "string",
                    "description": "Current collection path"
                },
                "new_name": {
                    "type": ["string", "null"],
                    "description": "New name for the collection (optional)"
                },
                "new_parent_path": {
                    "type": ["string", "null"],
                    "description": "New parent path (move to another collection set or root if null/'') (optional)"
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "description": "Wait timeout in seconds (default 5; 0 to return immediately)"
                }
            },
            "required": ["collection_path"],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "pending", "error"]},
                "updated": {"type": ["boolean", "null"]},
                "collection": {
                    "type": ["object", "null"],
                    "properties": {
                        "id": {"type": ["string", "null"]},
                        "name": {"type": "string"},
                        "path": {"type": "string"}
                    },
                    "required": ["id", "name", "path"],
                    "additionalProperties": False
                },
                "command_id": {"type": ["string", "null"]},
                "error": {"type": ["string", "null"]}
            },
            "required": ["status", "updated", "collection", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def handle_add_collection_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the add collection tool call."""
    # Check if Lightroom is running first
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return dependency_error
    
    if not arguments:
        return {"status": "error", "created": None, "collection": None, "command_id": None, "error": "No arguments provided"}
    
    name = arguments.get("name")
    if not name or not isinstance(name, str):
        return {"status": "error", "created": None, "collection": None, "command_id": None, "error": "Collection name is required"}
    
    parent_path = arguments.get("parent_path")
    if parent_path is not None and not isinstance(parent_path, str):
        parent_path = None
    
    wait_timeout_sec = arguments.get("wait_timeout_sec")
    if wait_timeout_sec is not None:
        if not isinstance(wait_timeout_sec, (int, float)) or wait_timeout_sec < 0:
            wait_timeout_sec = 5  # reduced default timeout
    else:
        wait_timeout_sec = 5  # reduced default timeout
    
    # Enqueue the command
    queue = get_queue()
    payload = {
        "name": name,
        "parent_path": parent_path
    }
    command_id = queue.enqueue(
        type="collection.create",
        payload=payload
    )
    
    # Wait for result if timeout > 0
    if wait_timeout_sec > 0:
        result = queue.wait_for_result(command_id, wait_timeout_sec)
        if result is None:
            # Timeout - return pending
            return {
                "status": "pending",
                "created": None,
                "collection": None,
                "command_id": command_id,
                "error": None
            }
        elif result.ok and result.result:
            return {
                "status": "ok",
                "created": result.result.get("created"),
                "collection": result.result.get("collection"),
                "command_id": command_id,
                "error": None
            }
        else:
            return {
                "status": "error",
                "created": None,
                "collection": None,
                "command_id": command_id,
                "error": result.error or "Unknown error"
            }
    else:
        # Return immediately
        return {
            "status": "pending",
            "created": None,
            "collection": None,
            "command_id": command_id,
            "error": None
        }


def handle_remove_collection_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the remove collection tool call."""
    # Check if Lightroom is running first
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return dependency_error
    
    if not arguments:
        return {"status": "error", "removed": None, "command_id": None, "error": "No arguments provided"}
    
    collection_path = arguments.get("collection_path")
    if not collection_path or not isinstance(collection_path, str):
        return {"status": "error", "removed": None, "command_id": None, "error": "Collection path is required"}
    
    wait_timeout_sec = arguments.get("wait_timeout_sec")
    if wait_timeout_sec is not None:
        if not isinstance(wait_timeout_sec, (int, float)) or wait_timeout_sec < 0:
            wait_timeout_sec = 5  # reduced default timeout
    else:
        wait_timeout_sec = 5  # reduced default timeout
    
    # Enqueue the command
    queue = get_queue()
    payload = {
        "collection_path": collection_path
    }
    command_id = queue.enqueue(
        type="collection.remove",
        payload=payload
    )
    
    # Wait for result if timeout > 0
    if wait_timeout_sec > 0:
        result = queue.wait_for_result(command_id, wait_timeout_sec)
        if result is None:
            # Timeout - return pending
            return {
                "status": "pending",
                "removed": None,
                "command_id": command_id,
                "error": None
            }
        elif result.ok and result.result:
            return {
                "status": "ok",
                "removed": result.result.get("removed"),
                "command_id": command_id,
                "error": None
            }
        else:
            return {
                "status": "error",
                "removed": None,
                "command_id": command_id,
                "error": result.error or "Unknown error"
            }
    else:
        # Return immediately
        return {
            "status": "pending",
            "removed": None,
            "command_id": command_id,
            "error": None
        }


def handle_edit_collection_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the edit collection tool call."""
    # Check if Lightroom is running first
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return dependency_error
    
    if not arguments:
        return {"status": "error", "updated": None, "collection": None, "command_id": None, "error": "No arguments provided"}
    
    collection_path = arguments.get("collection_path")
    if not collection_path or not isinstance(collection_path, str):
        return {"status": "error", "updated": None, "collection": None, "command_id": None, "error": "Collection path is required"}
    
    new_name = arguments.get("new_name")
    if new_name is not None and not isinstance(new_name, str):
        new_name = None
    
    new_parent_path = arguments.get("new_parent_path")
    if new_parent_path is not None and not isinstance(new_parent_path, str):
        new_parent_path = None
    
    wait_timeout_sec = arguments.get("wait_timeout_sec")
    if wait_timeout_sec is not None:
        if not isinstance(wait_timeout_sec, (int, float)) or wait_timeout_sec < 0:
            wait_timeout_sec = 5  # reduced default timeout
    else:
        wait_timeout_sec = 5  # reduced default timeout
    
    # Enqueue the command
    queue = get_queue()
    payload = {
        "collection_path": collection_path,
        "new_name": new_name,
        "new_parent_path": new_parent_path
    }
    command_id = queue.enqueue(
        type="collection.edit",
        payload=payload
    )
    
    # Wait for result if timeout > 0
    if wait_timeout_sec > 0:
        result = queue.wait_for_result(command_id, wait_timeout_sec)
        if result is None:
            # Timeout - return pending
            return {
                "status": "pending",
                "updated": None,
                "collection": None,
                "command_id": command_id,
                "error": None
            }
        elif result.ok and result.result:
            return {
                "status": "ok",
                "updated": result.result.get("updated"),
                "collection": result.result.get("collection"),
                "command_id": command_id,
                "error": None
            }
        else:
            return {
                "status": "error",
                "updated": None,
                "collection": None,
                "command_id": command_id,
                "error": result.error or "Unknown error"
            }
    else:
        # Return immediately
        return {
            "status": "pending",
            "updated": None,
            "collection": None,
            "command_id": command_id,
            "error": None
        }
