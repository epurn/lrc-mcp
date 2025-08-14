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
        description="Does create a new collection in Lightroom Classic. Requires Lightroom to be running with plugin connected. Parent collection sets must already exist. Returns collection information and creation status.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the collection to create"},
                "parent_path": {
                    "type": ["string", "null"], 
                    "description": "Parent collection set path (e.g., 'Sets/Nature'; null or '' means root). Parent sets must already exist."
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
                "status": {"type": "string", "enum": ["ok", "pending", "error"], "description": "Operation status: ok (completed), pending (in progress), error (failed)"},
                "created": {"type": ["boolean", "null"], "description": "True if collection was created, False if not, null if pending"},
                "collection": {
                    "type": ["object", "null"],
                    "properties": {
                        "id": {"type": ["string", "null"], "description": "Collection identifier"},
                        "name": {"type": "string", "description": "Collection name"},
                        "path": {"type": "string", "description": "Full collection path"}
                    },
                    "required": ["id", "name", "path"],
                    "additionalProperties": False
                },
                "command_id": {"type": ["string", "null"], "description": "Command identifier for tracking asynchronous operations"},
                "error": {"type": ["string", "null"], "description": "Error message if operation failed, null otherwise"}
            },
            "required": ["status", "created", "collection", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def get_add_collection_set_tool() -> mcp_types.Tool:
    """Get the add collection set tool definition."""
    return mcp_types.Tool(
        name="lrc_add_collection_set",
        description="Does create a new collection set in Lightroom Classic. Requires Lightroom to be running with plugin connected. Parent collection sets must already exist. Returns collection set information and creation status.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the collection set to create"},
                "parent_path": {
                    "type": ["string", "null"], 
                    "description": "Parent collection set path (e.g., 'Sets/Nature'; null or '' means root). Parent sets must already exist."
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
                "status": {"type": "string", "enum": ["ok", "pending", "error"], "description": "Operation status: ok (completed), pending (in progress), error (failed)"},
                "created": {"type": ["boolean", "null"], "description": "True if collection set was created, False if not, null if pending"},
                "collection_set": {
                    "type": ["object", "null"],
                    "properties": {
                        "id": {"type": ["string", "null"], "description": "Collection set identifier"},
                        "name": {"type": "string", "description": "Collection set name"},
                        "path": {"type": "string", "description": "Full collection set path"}
                    },
                    "required": ["id", "name", "path"],
                    "additionalProperties": False
                },
                "command_id": {"type": ["string", "null"], "description": "Command identifier for tracking asynchronous operations"},
                "error": {"type": ["string", "null"], "description": "Error message if operation failed, null otherwise"}
            },
            "required": ["status", "created", "collection_set", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def get_remove_collection_tool() -> mcp_types.Tool:
    """Get the remove collection tool definition."""
    return mcp_types.Tool(
        name="lrc_remove_collection",
        description="Does remove a collection from Lightroom Classic. Requires Lightroom to be running with plugin connected. Returns removal status and operation information.",
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
                "status": {"type": "string", "enum": ["ok", "pending", "error"], "description": "Operation status: ok (completed), pending (in progress), error (failed)"},
                "removed": {"type": ["boolean", "null"], "description": "True if collection was removed, False if not, null if pending"},
                "command_id": {"type": ["string", "null"], "description": "Command identifier for tracking asynchronous operations"},
                "error": {"type": ["string", "null"], "description": "Error message if operation failed, null otherwise"}
            },
            "required": ["status", "removed", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def get_edit_collection_tool() -> mcp_types.Tool:
    """Get the edit collection tool definition."""
    return mcp_types.Tool(
        name="lrc_edit_collection",
        description="Does edit (rename/move) a collection in Lightroom Classic. Requires Lightroom to be running with plugin connected. Can change collection name and/or move to different parent. Returns updated collection information and operation status.",
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
                "status": {"type": "string", "enum": ["ok", "pending", "error"], "description": "Operation status: ok (completed), pending (in progress), error (failed)"},
                "updated": {"type": ["boolean", "null"], "description": "True if collection was updated, False if not, null if pending"},
                "collection": {
                    "type": ["object", "null"],
                    "properties": {
                        "id": {"type": ["string", "null"], "description": "Collection identifier"},
                        "name": {"type": "string", "description": "Collection name"},
                        "path": {"type": "string", "description": "Full collection path"}
                    },
                    "required": ["id", "name", "path"],
                    "additionalProperties": False
                },
                "command_id": {"type": ["string", "null"], "description": "Command identifier for tracking asynchronous operations"},
                "error": {"type": ["string", "null"], "description": "Error message if operation failed, null otherwise"}
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


def handle_add_collection_set_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the add collection set tool call."""
    # Check if Lightroom is running first
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return dependency_error
    
    if not arguments:
        return {"status": "error", "created": None, "collection_set": None, "command_id": None, "error": "No arguments provided"}
    
    name = arguments.get("name")
    if not name or not isinstance(name, str):
        return {"status": "error", "created": None, "collection_set": None, "command_id": None, "error": "Collection set name is required"}
    
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
        type="collection_set.create",
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
                "collection_set": None,
                "command_id": command_id,
                "error": None
            }
        elif result.ok and result.result:
            return {
                "status": "ok",
                "created": result.result.get("created"),
                "collection_set": result.result.get("collection_set"),
                "command_id": command_id,
                "error": None
            }
        else:
            return {
                "status": "error",
                "created": None,
                "collection_set": None,
                "command_id": command_id,
                "error": result.error or "Unknown error"
            }
    else:
        # Return immediately
        return {
            "status": "pending",
            "created": None,
            "collection_set": None,
            "command_id": command_id,
            "error": None
        }
