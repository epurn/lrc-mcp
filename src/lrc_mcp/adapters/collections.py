"""Collection management tools for the lrc-mcp server."""

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime, timedelta, timezone

import logging
import mcp.types as mcp_types

from lrc_mcp.services.lrc_bridge import get_queue, get_store

logger = logging.getLogger(__name__)


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


def get_remove_collection_set_tool() -> mcp_types.Tool:
    """Get the remove collection set tool definition."""
    return mcp_types.Tool(
        name="lrc_remove_collection_set",
        description="Does remove a collection set from Lightroom Classic. Requires Lightroom to be running with plugin connected. Returns removal status and operation information.",
        inputSchema={
            "type": "object",
            "properties": {
                "collection_set_path": {
                    "type": "string",
                    "description": "Collection set path (e.g., 'Sets/Nature' or just 'Nature' at root)"
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "description": "Wait timeout in seconds (default 5; 0 to return immediately)"
                }
            },
            "required": ["collection_set_path"],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "pending", "error"], "description": "Operation status: ok (completed), pending (in progress), error (failed)"},
                "removed": {"type": ["boolean", "null"], "description": "True if collection set was removed, False if not, null if pending"},
                "command_id": {"type": ["string", "null"], "description": "Command identifier for tracking asynchronous operations"},
                "error": {"type": ["string", "null"], "description": "Error message if operation failed, null otherwise"}
            },
            "required": ["status", "removed", "command_id", "error"],
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


def handle_remove_collection_set_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the remove collection set tool call."""
    # Check if Lightroom is running first
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return dependency_error
    
    if not arguments:
        return {"status": "error", "removed": None, "command_id": None, "error": "No arguments provided"}
    
    collection_set_path = arguments.get("collection_set_path")
    if not collection_set_path or not isinstance(collection_set_path, str):
        return {"status": "error", "removed": None, "command_id": None, "error": "Collection set path is required"}
    
    wait_timeout_sec = arguments.get("wait_timeout_sec")
    if wait_timeout_sec is not None:
        if not isinstance(wait_timeout_sec, (int, float)) or wait_timeout_sec < 0:
            wait_timeout_sec = 5  # reduced default timeout
    else:
        wait_timeout_sec = 5  # reduced default timeout
    
    # Enqueue the command
    queue = get_queue()
    payload = {
        "collection_set_path": collection_set_path
    }
    command_id = queue.enqueue(
        type="collection_set.remove",
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


# -------------------------------
# Unified Collection Set Tool API
# -------------------------------

def get_collection_set_tool() -> mcp_types.Tool:
    """Get the unified collection set tool definition.

    Provides a single entry point for listing, creating, editing, and deleting collection sets.
    """
    return mcp_types.Tool(
        name="lrc_collection_set",
        description="Does execute collection set actions in Lightroom Classic via a unified dispatcher. Requires Lightroom to be running with plugin connected. Static functions: list, create, edit, delete.",
        inputSchema={
            "type": "object",
            "properties": {
                "function": {
                    "type": "string",
                    "enum": ["list", "create", "edit", "delete"],
                    "description": "Collection set action to perform"
                },
                "args": {
                    "type": "object",
                    "description": "Arguments for the selected function",
                    "additionalProperties": True
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "default": 5,
                    "description": "Wait for plugin result; 0 to return immediately"
                }
            },
            "required": ["function"],
            "additionalProperties": False
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "pending", "error"],
                    "description": "Operation status"
                },
                "result": {
                    "type": ["object", "null"],
                    "description": "Function-specific result payload. list: { collection_sets: [...] }. create: { created, collection_set }. edit: { updated, collection_set }. delete: { removed }."
                },
                "command_id": {
                    "type": ["string", "null"],
                    "description": "Command identifier for async tracking"
                },
                "error": {
                    "type": ["string", "null"],
                    "description": "Error message if any"
                }
            },
            "required": ["status", "result", "command_id", "error"],
            "additionalProperties": False
        }
    )


def handle_collection_set_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the unified collection set tool call.

    Supports function=list|create|edit|delete with corresponding args.
    """
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        # Normalize to this tool's output schema
        return {
            "status": "error",
            "result": None,
            "command_id": None,
            "error": dependency_error.get("error") if isinstance(dependency_error, dict) else "Lightroom dependency check failed"
        }

    if not arguments or not isinstance(arguments, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "No arguments provided"}

    func = arguments.get("function")
    if func not in {"list", "create", "edit", "delete"}:
        return {"status": "error", "result": None, "command_id": None, "error": "Invalid function. Expected one of: list, create, edit, delete"}

    args = arguments.get("args") or {}
    if not isinstance(args, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "args must be an object"}

    wait_timeout_sec = arguments.get("wait_timeout_sec")
    if wait_timeout_sec is not None:
        if not isinstance(wait_timeout_sec, (int, float)) or wait_timeout_sec < 0:
            wait_timeout_sec = 5
    else:
        wait_timeout_sec = 5

    queue = get_queue()

    if func == "list":
        parent_path = args.get("parent_path")
        if parent_path is not None and not isinstance(parent_path, str):
            parent_path = None

        # Optional recursive flag: default to True to include all nested sets
        include_nested = args.get("include_nested")
        if include_nested is None:
            include_nested = True
        elif not isinstance(include_nested, bool):
            include_nested = True

        command_id = queue.enqueue(
            type="collection_set.list",
            payload={"parent_path": parent_path, "include_nested": include_nested},
        )
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error"}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None}

    if func == "create":
        name = args.get("name")
        if not name or not isinstance(name, str):
            return {"status": "error", "result": None, "command_id": None, "error": "name is required for create"}
        parent_path = args.get("parent_path")
        if parent_path is not None and not isinstance(parent_path, str):
            parent_path = None
        command_id = queue.enqueue(type="collection_set.create", payload={"name": name, "parent_path": parent_path})
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error"}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None}

    if func == "edit":
        collection_set_path = args.get("collection_set_path")
        if not collection_set_path or not isinstance(collection_set_path, str):
            return {"status": "error", "result": None, "command_id": None, "error": "collection_set_path is required for edit"}
        new_name = args.get("new_name")
        if new_name is not None and not isinstance(new_name, str):
            new_name = None
        new_parent_path = args.get("new_parent_path")
        if new_parent_path is not None and not isinstance(new_parent_path, str):
            new_parent_path = None
        command_id = queue.enqueue(
            type="collection_set.edit",
            payload={
                "collection_set_path": collection_set_path,
                "new_name": new_name,
                "new_parent_path": new_parent_path,
            },
        )
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error"}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None}

    if func == "delete":
        collection_set_path = args.get("collection_set_path")
        if not collection_set_path or not isinstance(collection_set_path, str):
            return {"status": "error", "result": None, "command_id": None, "error": "collection_set_path is required for delete"}
        command_id = queue.enqueue(type="collection_set.remove", payload={"collection_set_path": collection_set_path})
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error"}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None}

    # Should not reach here
    return {"status": "error", "result": None, "command_id": None, "error": "Unhandled function"}


# ---------------------------
# Unified Collection Tool API
# ---------------------------

def get_collection_tool() -> mcp_types.Tool:
    """Get the unified collection tool definition.

    Provides a single entry point for listing, creating, editing, and deleting collections.
    Also supports 'remove' as a backward-compatible alias for 'delete' (deprecated).
    """
    return mcp_types.Tool(
        name="lrc_collection",
        description=(
            "Does execute collection actions in Lightroom Classic via a unified dispatcher. "
            "Requires Lightroom to be running with plugin connected. Functions: list, create, edit, delete. "
            "Accepts 'remove' as a deprecated alias for 'delete'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "function": {
                    "type": "string",
                    "enum": ["list", "create", "edit", "delete"],  # 'remove' accepted at runtime as alias
                    "description": "Collection action to perform"
                },
                "args": {
                    "type": "object",
                    "description": "Arguments for the selected function",
                    "additionalProperties": True
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "default": 5,
                    "description": "Wait for plugin result; 0 to return immediately"
                }
            },
            "required": ["function"],
            "additionalProperties": False
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "pending", "error"],
                    "description": "Operation status"
                },
                "result": {
                    "type": ["object", "null"],
                    "description": (
                        "Function-specific result payload. "
                        "list: { collections: [{ id, name, set_id, smart, photo_count, path }] }. "
                        "create: { created, collection }. "
                        "edit: { updated, collection }. "
                        "delete: { removed }."
                    ),
                    "additionalProperties": True
                },
                "command_id": {
                    "type": ["string", "null"],
                    "description": "Command identifier for async tracking"
                },
                "error": {
                    "type": ["string", "null"],
                    "description": "Error message if any"
                },
                "deprecation": {
                    "type": ["string", "null"],
                    "description": "Deprecation note when using deprecated alias (e.g., 'remove' -> 'delete')"
                }
            },
            "required": ["status", "result", "command_id", "error"],
            "additionalProperties": False
        }
    )


def handle_collection_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the unified collection tool call.

    Supports function=list|create|edit|delete with corresponding args.
    Back-compat alias: function='remove' is treated as 'delete' with a deprecation note.
    """
    # Dependency check is deferred until after argument validation to surface schema errors first.

    if not arguments or not isinstance(arguments, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "No arguments provided", "deprecation": None}

    func = arguments.get("function")
    deprecation: Optional[str] = None
    if func == "remove":
        # Backward compatibility: map remove -> delete
        logger.warning("lrc_collection: 'remove' is deprecated; use 'delete' instead.")
        func = "delete"
        deprecation = "Function 'remove' is deprecated; use 'delete' instead."
    if func not in {"list", "create", "edit", "delete"}:
        return {"status": "error", "result": None, "command_id": None, "error": "Invalid function. Expected one of: list, create, edit, delete", "deprecation": None}

    args = arguments.get("args") or {}
    if not isinstance(args, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "args must be an object", "deprecation": None}

    # Early validation for required parameters to surface schema errors before dependency checks
    if func == "delete":
        coll_id = args.get("id")
        if not coll_id or not isinstance(coll_id, (str, int)):
            return {"status": "error", "result": None, "command_id": None, "error": "id is required for delete", "deprecation": deprecation}

    wait_timeout_sec = arguments.get("wait_timeout_sec")
    if wait_timeout_sec is not None:
        if not isinstance(wait_timeout_sec, (int, float)) or wait_timeout_sec < 0:
            wait_timeout_sec = 5
    else:
        wait_timeout_sec = 5

    # Perform dependency check after basic validation
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return {
            "status": "error",
            "result": None,
            "command_id": None,
            "error": dependency_error.get("error") if isinstance(dependency_error, dict) else "Lightroom dependency check failed",
            "deprecation": deprecation
        }

    queue = get_queue()

    # list
    if func == "list":
        # Optional filters
        set_id = args.get("set_id")
        if set_id is not None and not isinstance(set_id, str):
            set_id = None
        name_contains = args.get("name_contains")
        if name_contains is not None and not isinstance(name_contains, str):
            name_contains = None

        command_id = queue.enqueue(
            type="collection.list",
            payload={"set_id": set_id, "name_contains": name_contains},
        )
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None, "deprecation": deprecation}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error", "deprecation": deprecation}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}

    # create
    if func == "create":
        name = args.get("name")
        if not name or not isinstance(name, str):
            return {"status": "error", "result": None, "command_id": None, "error": "name is required for create", "deprecation": deprecation}
        parent_path = args.get("parent_path")
        if parent_path is not None and not isinstance(parent_path, str):
            parent_path = None
        smart = args.get("smart")
        if smart is not None and not isinstance(smart, bool):
            smart = None

        command_id = queue.enqueue(
            type="collection.create",
            payload={"name": name, "parent_path": parent_path, "smart": smart},
        )
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None, "deprecation": deprecation}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error", "deprecation": deprecation}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}

    # edit
    if func == "edit":
        collection_path = args.get("collection_path")
        if not collection_path or not isinstance(collection_path, str):
            return {"status": "error", "result": None, "command_id": None, "error": "collection_path is required for edit", "deprecation": deprecation}
        new_name = args.get("new_name")
        if new_name is not None and not isinstance(new_name, str):
            new_name = None
        new_parent_path = args.get("new_parent_path")
        if new_parent_path is not None and not isinstance(new_parent_path, str):
            new_parent_path = None

        command_id = queue.enqueue(
            type="collection.edit",
            payload={
                "collection_path": collection_path,
                "new_name": new_name,
                "new_parent_path": new_parent_path,
            },
        )
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None, "deprecation": deprecation}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error", "deprecation": deprecation}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}

    # delete (by id)
    if func == "delete":
        coll_id = args.get("id")
        if not coll_id or not isinstance(coll_id, (str, int)):
            return {"status": "error", "result": None, "command_id": None, "error": "id is required for delete", "deprecation": deprecation}

        command_id = queue.enqueue(
            type="collection.remove",
            payload={"id": str(coll_id)},
        )
        if wait_timeout_sec > 0:
            result = queue.wait_for_result(command_id, wait_timeout_sec)
            if result is None:
                return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}
            if result.ok and result.result is not None:
                return {"status": "ok", "result": result.result, "command_id": command_id, "error": None, "deprecation": deprecation}
            return {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error", "deprecation": deprecation}
        return {"status": "pending", "result": None, "command_id": command_id, "error": None, "deprecation": deprecation}

    # Should not reach here
    return {"status": "error", "result": None, "command_id": None, "error": "Unhandled function", "deprecation": deprecation}
