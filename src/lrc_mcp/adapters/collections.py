"""Collection management tools for the lrc-mcp server."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
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
            "collection": None,
        }
    return None


# -------------------------
# Internal helper functions
# -------------------------

def _normalize_wait_timeout(value: Any, default: float = 5) -> float:
    """Normalize wait timeout to a non-negative float, fallback to default."""
    if value is None:
        return default
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return default


def _with_optional_deprecation(
    payload: Dict[str, Any],
    deprecation: Optional[str],
) -> Dict[str, Any]:
    """Attach a deprecation field to payload if provided, else return as-is."""
    if deprecation is not None:
        payload = {**payload, "deprecation": deprecation}
    return payload


def _enqueue_and_maybe_wait(
    queue: Any,
    type_name: str,
    payload: Dict[str, Any],
    wait_timeout_sec: float,
    deprecation: Optional[str] = None,
) -> Dict[str, Any]:
    """Enqueue a command and optionally wait for a result, returning a normalized response.

    Args:
        queue: Command queue instance.
        type_name: Command type (e.g., "collection", "collection_set").
        payload: Payload to enqueue.
        wait_timeout_sec: Seconds to wait for result; 0 returns immediately.
        deprecation: Optional deprecation note to include (collection tool only).

    Returns:
        Normalized tool response dict.
    """
    command_id = queue.enqueue(type=type_name, payload=payload)

    if wait_timeout_sec > 0:
        result = queue.wait_for_result(command_id, wait_timeout_sec)
        if result is None:
            return _with_optional_deprecation(
                {"status": "pending", "result": None, "command_id": command_id, "error": None},
                deprecation,
            )
        if result.ok and result.result is not None:
            return _with_optional_deprecation(
                {"status": "ok", "result": result.result, "command_id": command_id, "error": None},
                deprecation,
            )
        return _with_optional_deprecation(
            {"status": "error", "result": None, "command_id": command_id, "error": result.error or "Unknown error"},
            deprecation,
        )

    return _with_optional_deprecation(
        {"status": "pending", "result": None, "command_id": command_id, "error": None},
        deprecation,
    )


def _extract_target_identifier(args: Dict[str, Any], path_alias_key: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract target identifier for edit/delete operations.

    Gives precedence to 'id' over 'path'. Accepts a legacy alias for path.

    Args:
        args: Arguments dict.
        path_alias_key: Legacy alias key name for 'path' (e.g., 'collection_path', 'collection_set_path').

    Returns:
        (identifier_key, identifier_value, error_message)
        If error_message is not None, identifier_key/value will be None.
    """
    target_id = args.get("id")
    target_path = args.get("path") or args.get(path_alias_key)

    if not target_id and not target_path:
        return None, None, "Either 'id' or 'path' is required"

    if target_id:
        return "id", target_id, None
    return "path", target_path, None


def _build_collection_set_list_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build payload for collection_set list operation with unified shape."""
    parent_id = args.get("parent_id")
    parent_path = args.get("parent_path")
    name_contains = args.get("name_contains")

    if parent_id is not None and not isinstance(parent_id, str):
        parent_id = None
    if parent_path is not None and not isinstance(parent_path, str):
        parent_path = None
    if name_contains is not None and not isinstance(name_contains, str):
        name_contains = None

    payload: Dict[str, Any] = {}
    if parent_id:
        payload["parent_id"] = parent_id
    elif parent_path is not None:
        payload["parent_path"] = parent_path
    if name_contains:
        payload["name_contains"] = name_contains

    return payload


def _build_collection_list_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build payload for collection list operation."""
    parent_id = args.get("parent_id") or args.get("set_id")  # Accept legacy name
    parent_path = args.get("parent_path")
    name_contains = args.get("name_contains")

    if parent_id is not None and not isinstance(parent_id, str):
        parent_id = None
    if parent_path is not None and not isinstance(parent_path, str):
        parent_path = None
    if name_contains is not None and not isinstance(name_contains, str):
        name_contains = None

    payload: Dict[str, Any] = {}
    if parent_id:
        payload["set_id"] = parent_id  # Map to legacy key for compatibility
    elif parent_path is not None:
        payload["parent_path"] = parent_path
    if name_contains:
        payload["name_contains"] = name_contains

    return payload


def _normalize_new_parent_args(args: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Normalize new_parent_id/new_parent_path edit arguments."""
    new_parent_id = args.get("new_parent_id")
    new_parent_path = args.get("new_parent_path")

    if new_parent_id is not None and not isinstance(new_parent_id, str):
        new_parent_id = None
    if new_parent_path is not None and not isinstance(new_parent_path, str):
        new_parent_path = None

    return new_parent_id, new_parent_path


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
                    "description": "Collection set action to perform",
                },
                "args": {
                    "type": "object",
                    "description": "Arguments for the selected function",
                    "additionalProperties": True,
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "default": 5,
                    "description": "Wait for plugin result; 0 to return immediately",
                },
            },
            "required": ["function"],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "pending", "error"],
                    "description": "Operation status",
                },
                "result": {
                    "type": ["object", "null"],
                    "description": "Function-specific result payload. list: { collection_sets: [...] }. create: { created, collection_set }. edit: { updated, collection_set }. delete: { removed }.",
                },
                "command_id": {
                    "type": ["string", "null"],
                    "description": "Command identifier for async tracking",
                },
                "error": {
                    "type": ["string", "null"],
                    "description": "Error message if any",
                },
                "deprecation": {
                    "type": ["string", "null"],
                    "description": "Deprecation note when using deprecated alias (e.g., 'remove' -> 'delete')",
                },
            },
            "required": ["status", "result", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def handle_collection_set_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the unified collection set tool call.

    Supports function=list|create|edit|delete with corresponding args using unified argument contract.
    """
    deprecation: Optional[str] = None

    if not arguments or not isinstance(arguments, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "No arguments provided", "deprecation": deprecation}

    func = arguments.get("function")
    if func == "remove":
        # Backward compatibility: map remove -> delete
        logger.warning("lrc_collection_set: 'remove' is deprecated; use 'delete' instead.")
        func = "delete"
        deprecation = "Function 'remove' is deprecated; use 'delete' instead."
    if func not in {"list", "create", "edit", "delete"}:
        return {"status": "error", "result": None, "command_id": None, "error": "Invalid function. Expected one of: list, create, edit, delete", "deprecation": deprecation}

    args = arguments.get("args") or {}
    if not isinstance(args, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "args must be an object", "deprecation": deprecation}

    # For edit/delete, validate identifier presence before dependency check
    identifier_key: Optional[str] = None
    identifier_value: Optional[str] = None
    if func in {"edit", "delete"}:
        identifier_key, identifier_value, id_err = _extract_target_identifier(args, "collection_set_path")
        if id_err:
            return {"status": "error", "result": None, "command_id": None, "error": f"{id_err} for {func}", "deprecation": deprecation}

    # Perform dependency check after argument validation to surface schema errors first
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return {
            "status": "error",
            "result": None,
            "command_id": None,
            "error": dependency_error.get("error") if isinstance(dependency_error, dict) else "Lightroom dependency check failed",
            "deprecation": deprecation,
        }

    wait_timeout_sec = _normalize_wait_timeout(arguments.get("wait_timeout_sec"))

    queue = get_queue()

    if func == "list":
        payload = _build_collection_set_list_payload(args)
        return _enqueue_and_maybe_wait(queue, "collection_set.list", payload, wait_timeout_sec, deprecation)

    if func == "create":
        name = args.get("name")
        if not name or not isinstance(name, str):
            return {"status": "error", "result": None, "command_id": None, "error": "name is required for create", "deprecation": deprecation}

        parent_id = args.get("parent_id")
        parent_path = args.get("parent_path")

        if parent_id is not None and not isinstance(parent_id, str):
            parent_id = None
        if parent_path is not None and not isinstance(parent_path, str):
            parent_path = None

        payload: Dict[str, Any] = {"name": name}
        if parent_id:
            payload["parent_id"] = parent_id
        elif parent_path is not None:
            payload["parent_path"] = parent_path

        return _enqueue_and_maybe_wait(queue, "collection_set.create", payload, wait_timeout_sec, deprecation)

    if func == "edit":
        new_name = args.get("new_name")
        if new_name is not None and not isinstance(new_name, str):
            new_name = None
        new_parent_id, new_parent_path = _normalize_new_parent_args(args)

        payload: Dict[str, Any] = {}
        payload[str(identifier_key)] = identifier_value  # type: ignore[index]
        if new_name:
            payload["new_name"] = new_name
        if new_parent_id:
            payload["new_parent_id"] = new_parent_id
        elif new_parent_path is not None:
            payload["new_parent_path"] = new_parent_path

        return _enqueue_and_maybe_wait(queue, "collection_set.edit", payload, wait_timeout_sec, deprecation)

    if func == "delete":
        payload = {str(identifier_key): identifier_value}  # type: ignore[index]
        return _enqueue_and_maybe_wait(queue, "collection_set.remove", payload, wait_timeout_sec, deprecation)

    # Should not reach here
    return {"status": "error", "result": None, "command_id": None, "error": "Unhandled function", "deprecation": deprecation}


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
                    "description": "Collection action to perform",
                },
                "args": {
                    "type": "object",
                    "description": "Arguments for the selected function",
                    "additionalProperties": True,
                },
                "wait_timeout_sec": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "default": 5,
                    "description": "Wait for plugin result; 0 to return immediately",
                },
            },
            "required": ["function"],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "pending", "error"],
                    "description": "Operation status",
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
                    "additionalProperties": True,
                },
                "command_id": {
                    "type": ["string", "null"],
                    "description": "Command identifier for async tracking",
                },
                "error": {
                    "type": ["string", "null"],
                    "description": "Error message if any",
                },
                "deprecation": {
                    "type": ["string", "null"],
                    "description": "Deprecation note when using deprecated alias (e.g., 'remove' -> 'delete')",
                },
            },
            "required": ["status", "result", "command_id", "error"],
            "additionalProperties": False,
        },
    )


def handle_collection_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the unified collection tool call.

    Supports function=list|create|edit|delete with corresponding args using unified argument contract.
    Back-compat alias: function='remove' is treated as 'delete' with a deprecation note.
    """
    # Dependency check is deferred until after argument validation to surface schema errors first.

    deprecation: Optional[str] = None

    if not arguments or not isinstance(arguments, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "No arguments provided", "deprecation": deprecation}

    func = arguments.get("function")
    if func == "remove":
        # Backward compatibility: map remove -> delete
        logger.warning("lrc_collection: 'remove' is deprecated; use 'delete' instead.")
        func = "delete"
        deprecation = "Function 'remove' is deprecated; use 'delete' instead."
    if func not in {"list", "create", "edit", "delete"}:
        return {"status": "error", "result": None, "command_id": None, "error": "Invalid function. Expected one of: list, create, edit, delete", "deprecation": deprecation}

    args = arguments.get("args") or {}
    if not isinstance(args, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "args must be an object", "deprecation": deprecation}

    wait_timeout_sec = _normalize_wait_timeout(arguments.get("wait_timeout_sec"))

    # Normalize arguments for unified contract (edit/delete id/path)
    identifier_key: Optional[str] = None
    identifier_value: Optional[str] = None
    if func in {"edit", "delete"}:
        identifier_key, identifier_value, id_err = _extract_target_identifier(args, "collection_path")
        if id_err:
            return {"status": "error", "result": None, "command_id": None, "error": f"{id_err} for {func}", "deprecation": deprecation}

    # Perform dependency check after basic validation
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return {
            "status": "error",
            "result": None,
            "command_id": None,
            "error": dependency_error.get("error") if isinstance(dependency_error, dict) else "Lightroom dependency check failed",
            "deprecation": deprecation,
        }

    queue = get_queue()

    # list
    if func == "list":
        payload = _build_collection_list_payload(args)
        return _enqueue_and_maybe_wait(queue, "collection.list", payload, wait_timeout_sec, deprecation)

    # create
    if func == "create":
        name = args.get("name")
        if not name or not isinstance(name, str):
            return {"status": "error", "result": None, "command_id": None, "error": "name is required for create", "deprecation": deprecation}

        parent_id = args.get("parent_id")
        parent_path = args.get("parent_path") or args.get("parent_path")  # Accept legacy name
        smart = args.get("smart")

        # Precedence: parent_id > parent_path
        if parent_id is not None and not isinstance(parent_id, str):
            parent_id = None
        if parent_path is not None and not isinstance(parent_path, str):
            parent_path = None
        if smart is not None and not isinstance(smart, bool):
            smart = None

        payload: Dict[str, Any] = {"name": name}
        if parent_id:
            payload["parent_id"] = parent_id
        elif parent_path is not None:
            payload["parent_path"] = parent_path
        if smart is not None:
            payload["smart"] = smart

        return _enqueue_and_maybe_wait(queue, "collection.create", payload, wait_timeout_sec, deprecation)

    # edit
    if func == "edit":
        new_name = args.get("new_name")
        if new_name is not None and not isinstance(new_name, str):
            new_name = None
        new_parent_id, new_parent_path = _normalize_new_parent_args(args)

        payload: Dict[str, Any] = {}
        payload[str(identifier_key)] = identifier_value  # type: ignore[index]
        if new_name:
            payload["new_name"] = new_name
        if new_parent_id:
            payload["new_parent_id"] = new_parent_id
        elif new_parent_path is not None:
            payload["new_parent_path"] = new_parent_path

        return _enqueue_and_maybe_wait(queue, "collection.edit", payload, wait_timeout_sec, deprecation)

    # delete
    if func == "delete":
        payload: Dict[str, Any] = {str(identifier_key): identifier_value}  # type: ignore[index]
        return _enqueue_and_maybe_wait(queue, "collection.remove", payload, wait_timeout_sec, deprecation)

    # Should not reach here
    return {"status": "error", "result": None, "command_id": None, "error": "Unhandled function", "deprecation": deprecation}
