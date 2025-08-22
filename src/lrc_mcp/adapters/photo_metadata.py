"""Photo metadata read tools for the lrc-mcp server (E9-S1).

Implements read-only MCP tool "lrc_photo_metadata" with functions:
- get: fetch normalized metadata for a single photo
- bulk_get: fetch for multiple photos with partial success aggregation

Contracts and behavior follow the plan for E9-S1 and existing adapter patterns
(e.g., collections adapter) to ensure consistency across tools.

References:
- MCP docs (tool schemas, determinism): https://modelcontextprotocol.io/docs
  Also see local docs under .resources/MCP-docs
- Adobe Lightroom Classic SDK (photo metadata APIs, catalog access rules):
  See local docs under .resources/LrC

Notes:
- This module only enqueues commands to the Lightroom plugin and optionally
  waits for results. Actual metadata reads happen in the plugin to avoid
  violating Lightroom SDK threading/catalog rules.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

import mcp.types as mcp_types

from lrc_mcp.services.lrc_bridge import get_queue

# Reuse dependency checks, wait normalization, and enqueue helper from collections adapter
from lrc_mcp.adapters.collections import (  # type: ignore
    _check_lightroom_dependency,
    _normalize_wait_timeout,
    _enqueue_and_maybe_wait,
)

logger = logging.getLogger(__name__)


# -----------------------------
# Tool schemas and definitions
# -----------------------------

_FIELDS_ENUM = [
    "title",
    "caption",
    "keywords",
    "rating",
    "color_label",
    "flag",
    "gps",
    "capture_time",
]


def get_photo_metadata_tool() -> mcp_types.Tool:
    """Get the lrc_photo_metadata tool definition (read-only, E9-S1).

    Provides get and bulk_get functions for reading common IPTC/EXIF and Lightroom fields.
    Deterministic schemas, strict validation, partial success aggregation, and timeouts are honored.
    """
    return mcp_types.Tool(
        name="lrc_photo_metadata",
        title="Lightroom Photo Metadata",
        description=(
            "Does read-only photo metadata retrieval for single or multiple photos. "
            "Functions: get, bulk_get. Inputs include photo identifier(s) and requested field set; optional wait_timeout_sec controls sync/async behavior. "
            "Returns deterministic normalized results with per-item errors for bulk and honors timeouts."
        ),
        annotations=mcp_types.ToolAnnotations(
            title="Photo Metadata",
            readOnlyHint=True,
            idempotentHint=True,
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "function": {
                    "type": "string",
                    "enum": ["get", "bulk_get"],
                    "description": "Metadata function to perform",
                },
                "args": {
                    "type": "object",
                    "description": "Function-specific arguments",
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
            "oneOf": [
                {
                    "properties": {
                        "function": {"const": "get"},
                        "args": {
                            "type": "object",
                            "properties": {
                                "photo": {
                                    "type": "object",
                                    "title": "Photo Identifier",
                                    "description": "Identify the photo by local_id or file_path",
                                    "properties": {
                                        "local_id": {"type": "string", "title": "Local ID"},
                                        "file_path": {"type": "string", "title": "File Path"},
                                    },
                                    "additionalProperties": False,
                                },
                                "fields": {
                                    "type": "array",
                                    "title": "Fields",
                                    "description": "Subset of fields to retrieve; defaults to all when omitted",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["photo"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["args"],
                },
                {
                    "properties": {
                        "function": {"const": "bulk_get"},
                        "args": {
                            "type": "object",
                            "properties": {
                                "photos": {
                                    "type": "array",
                                    "title": "Photo Identifiers",
                                    "description": "Array of photo identifiers; each requires local_id or file_path",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "local_id": {"type": "string", "title": "Local ID"},
                                            "file_path": {"type": "string", "title": "File Path"},
                                        },
                                        "additionalProperties": False,
                                    },
                                    "minItems": 1,
                                },
                                "fields": {
                                    "type": "array",
                                    "title": "Fields",
                                    "description": "Subset of fields to retrieve; defaults to all when omitted",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["photos"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["args"],
                },
            ],
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
                        "get: { photo, result, error }. "
                        "bulk_get: { items: [...], errors_aggregated: [...], stats: { requested, succeeded, failed, duration_ms } }"
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
                "errorCode": {
                    "type": ["string", "null"],
                    "enum": ["NOT_FOUND", "VALIDATION", "DEPENDENCY_NOT_RUNNING", "TIMEOUT", "UNKNOWN"],
                    "description": "Structured error code for non-transport errors (optional)"
                },
            },
            "required": ["status", "result", "command_id", "error"],
            "additionalProperties": False,
        },
    )


# -----------------------------
# Handler implementation
# -----------------------------

def _validate_get_args(args: Dict[str, Any]) -> Optional[str]:
    """Validate args for get function. Returns error string or None if ok."""
    if not isinstance(args, dict):
        return "args must be an object"

    photo = args.get("photo")
    if not isinstance(photo, dict):
        return "photo must be an object with 'local_id' or 'file_path'"

    local_id = photo.get("local_id")
    file_path = photo.get("file_path")
    if not (isinstance(local_id, str) and local_id.strip()) and not (isinstance(file_path, str) and file_path.strip()):
        return "photo.local_id or photo.file_path is required"

    fields = args.get("fields")
    if fields is not None:
        if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
            return "fields must be an array of strings"
        # Strict validation: reject unknown fields
        unknown = [f for f in fields if f not in _FIELDS_ENUM]
        if unknown:
            return f"Unknown field(s): {', '.join(unknown)}"
    return None


def _normalize_get_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build payload for get with deterministic shape."""
    photo = args.get("photo") or {}
    fields = args.get("fields")
    payload: Dict[str, Any] = {
        "photo": {
            "local_id": photo.get("local_id") if isinstance(photo.get("local_id"), str) else None,
            "file_path": photo.get("file_path") if isinstance(photo.get("file_path"), str) else None,
        }
    }
    if isinstance(fields, list) and fields:
        payload["fields"] = [f for f in fields if isinstance(f, str)]
    else:
        payload["fields"] = _FIELDS_ENUM[:]  # default to all fields
    return payload


def _validate_bulk_get_args(args: Dict[str, Any]) -> Optional[str]:
    """Validate args for bulk_get function. Returns error string or None if ok."""
    if not isinstance(args, dict):
        return "args must be an object"

    photos = args.get("photos")
    if not isinstance(photos, list) or not photos:
        return "photos must be a non-empty array of photo objects"
    for idx, p in enumerate(photos):
        if not isinstance(p, dict):
            return f"photos[{idx}] must be an object"
        local_id = p.get("local_id")
        file_path = p.get("file_path")
        if not (isinstance(local_id, str) and local_id.strip()) and not (isinstance(file_path, str) and file_path.strip()):
            return f"photos[{idx}].local_id or photos[{idx}].file_path is required"

    fields = args.get("fields")
    if fields is not None:
        if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
            return "fields must be an array of strings"
        unknown = [f for f in fields if f not in _FIELDS_ENUM]
        if unknown:
            return f"Unknown field(s): {', '.join(unknown)}"
    return None


def _normalize_bulk_get_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build payload for bulk_get with deterministic shape."""
    photos = args.get("photos") or []
    fields = args.get("fields")
    payload: Dict[str, Any] = {
        "photos": [
            {
                "local_id": p.get("local_id") if isinstance(p.get("local_id"), str) else None,
                "file_path": p.get("file_path") if isinstance(p.get("file_path"), str) else None,
            }
            for p in photos
            if isinstance(p, dict)
        ]
    }
    if isinstance(fields, list) and fields:
        payload["fields"] = [f for f in fields if isinstance(f, str)]
    else:
        payload["fields"] = _FIELDS_ENUM[:]
    return payload


def handle_photo_metadata_tool(arguments: Dict[str, Any] | None) -> Dict[str, Any]:
    """Handle the lrc_photo_metadata tool call.

    Supports function=get|bulk_get with corresponding args. Validates inputs,
    checks Lightroom dependency, enqueues command(s), and optionally waits.
    """
    if not arguments or not isinstance(arguments, dict):
        return {"status": "error", "result": None, "command_id": None, "error": "No arguments provided", "errorCode": "VALIDATION"}

    func = arguments.get("function")
    if func not in {"get", "bulk_get"}:
        return {"status": "error", "result": None, "command_id": None, "error": "Invalid function. Expected one of: get, bulk_get", "errorCode": "VALIDATION"}

    args = arguments.get("args") or {}
    if func == "get":
        err = _validate_get_args(args)
        if err:
            return {"status": "error", "result": None, "command_id": None, "error": err, "errorCode": "VALIDATION"}
    else:
        err = _validate_bulk_get_args(args)
        if err:
            return {"status": "error", "result": None, "command_id": None, "error": err, "errorCode": "VALIDATION"}

    # Dependency check after basic validation
    dependency_error = _check_lightroom_dependency()
    if dependency_error:
        return {
            "status": "error",
            "result": None,
            "command_id": None,
            "error": dependency_error.get("error") if isinstance(dependency_error, dict) else "Lightroom dependency check failed",
            "errorCode": "DEPENDENCY_NOT_RUNNING",
        }

    wait_timeout_sec = _normalize_wait_timeout(arguments.get("wait_timeout_sec"))
    queue = get_queue()

    if func == "get":
        payload = _normalize_get_payload(args)
        return _enqueue_and_maybe_wait(queue, "photo_metadata.get", payload, wait_timeout_sec)

    # bulk_get
    payload = _normalize_bulk_get_payload(args)
    return _enqueue_and_maybe_wait(queue, "photo_metadata.bulk_get", payload, wait_timeout_sec)
