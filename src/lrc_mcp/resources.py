"""MCP Resources implementation for lrc-mcp (Phase 2).

Provides:
- Static resources:
  - lrc://logs/plugin        (plugin log text)
  - lrc://status/lightroom   (server+plugin status as JSON)
  - lrc://catalog/collections (JSON snapshot of collections tree; server-side assembled)

- Resource templates:
  - lrc://collection/{id}
  - lrc://collection_set/{id}

Design notes:
- Uses mcp.types Resources API shapes.
- Avoids circular imports with adapters by re-implementing a small heartbeat freshness
  check and using only the lrc_bridge service to access state/queue.
- Snapshot reading uses the command queue and may block briefly while waiting for results.
  This is executed via anyio.to_thread.run_sync to avoid blocking the event loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional, Tuple
import json
import anyio
import asyncio
import mcp.types as mcp_types
from datetime import datetime, timedelta, timezone
from pydantic import AnyUrl
from typing import cast
from urllib.parse import unquote

from lrc_mcp.services.lrc_bridge import get_store, get_queue


# -------------------------
# Helpers and configuration
# -------------------------

def _project_root() -> Path:
    # src/lrc_mcp/resources.py -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _plugin_log_path() -> Path:
    return _project_root() / "plugin" / "lrc-mcp.lrplugin" / "logs" / "lrc_mcp.log"


def _heartbeat_fresh(seconds: int = 30) -> Tuple[bool, Optional[int]]:
    """Return (is_fresh, age_seconds_or_none)."""
    store = get_store()
    hb = store.get_last_heartbeat()
    if not hb:
        return False, None
    now = datetime.now(timezone.utc)
    age = int((now - hb.received_at).total_seconds())
    return (age <= seconds), age


def _is_lightroom_running() -> bool:
    fresh, _ = _heartbeat_fresh()
    return fresh


# ---------------------------------
# Public resource list / templates
# ---------------------------------

def list_resources() -> list[mcp_types.Resource]:
    """Return static resources available."""
    return [
        mcp_types.Resource(
            name="logs/plugin",
            title="Plugin Log",
            uri=cast(AnyUrl, "lrc://logs/plugin"),
            description="Latest Lightroom MCP plugin log output.",
            mimeType="text/plain",
            annotations=mcp_types.Annotations(audience=["assistant", "user"], priority=0.7),
        ),
        mcp_types.Resource(
            name="status/lightroom",
            title="Lightroom Status",
            uri=cast(AnyUrl, "lrc://status/lightroom"),
            description="Current Lightroom and plugin connection status as JSON.",
            mimeType="application/json",
            annotations=mcp_types.Annotations(audience=["assistant", "user"], priority=0.9),
        ),
        mcp_types.Resource(
            name="catalog/collections",
            title="Collections Snapshot",
            uri=cast(AnyUrl, "lrc://catalog/collections"),
            description="Snapshot JSON of the current collections tree (server-side assembled).",
            mimeType="application/json",
            annotations=mcp_types.Annotations(audience=["assistant", "user"], priority=0.6),
        ),
    ]


def list_resource_templates() -> list[mcp_types.ResourceTemplate]:
    """Return resource templates."""
    return [
        mcp_types.ResourceTemplate(
            name="collection",
            title="Collection by ID",
            uriTemplate="lrc://collection/{id}",
            description="Represents a single Lightroom collection by its internal ID.",
            mimeType="application/json",
            annotations=mcp_types.Annotations(audience=["assistant", "user"], priority=0.5),
        ),
        mcp_types.ResourceTemplate(
            name="collection_set",
            title="Collection Set by ID",
            uriTemplate="lrc://collection_set/{id}",
            description="Represents a single Lightroom collection set by its internal ID.",
            mimeType="application/json",
            annotations=mcp_types.Annotations(audience=["assistant", "user"], priority=0.5),
        ),
        mcp_types.ResourceTemplate(
            name="collection.by_path",
            title="Collection by Path",
            uriTemplate="lrc://collection/by-path/{path}",
            description="Represents a single Lightroom collection by its hierarchical path (e.g., 'Sets/Sub/Col').",
            mimeType="application/json",
            annotations=mcp_types.Annotations(audience=["assistant", "user"], priority=0.4),
        ),
        mcp_types.ResourceTemplate(
            name="collection_set.by_path",
            title="Collection Set by Path",
            uriTemplate="lrc://collection_set/by-path/{path}",
            description="Represents a single Lightroom collection set by its hierarchical path.",
            mimeType="application/json",
            annotations=mcp_types.Annotations(audience=["assistant", "user"], priority=0.4),
        ),
    ]


# -------------------
# Resource read logic
# -------------------

async def read_resource(uri: str) -> str:
    """Read a resource by URI and return textual content.

    For binary content, this function would return bytes; currently all resources are text.
    """
    if uri.startswith("lrc://logs/plugin"):
        return await _read_plugin_log()
    if uri.startswith("lrc://status/lightroom"):
        return await _read_lightroom_status_json()
    if uri.startswith("lrc://catalog/collections"):
        return await _read_collections_snapshot()
    if uri.startswith("lrc://collection/by-path/"):
        raw = uri[len("lrc://collection/by-path/"):]
        path = unquote(raw)
        return await _read_collection_by_path(path)
    if uri.startswith("lrc://collection_set/by-path/"):
        raw = uri[len("lrc://collection_set/by-path/"):]
        path = unquote(raw)
        return await _read_collection_set_by_path(path)
    if uri.startswith("lrc://collection/"):
        coll_id = uri.rsplit("/", 1)[-1]
        return await _read_single_collection(coll_id)
    if uri.startswith("lrc://collection_set/"):
        set_id = uri.rsplit("/", 1)[-1]
        return await _read_single_collection_set(set_id)
    return f"Unsupported resource: {uri}"


async def _read_plugin_log() -> str:
    path = _plugin_log_path()
    if not path.exists():
        return "Plugin log not found."
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading plugin log: {e}"


async def _read_lightroom_status_json() -> str:
    running, age = _heartbeat_fresh()
    store = get_store()
    hb = store.get_last_heartbeat()
    payload: dict[str, Any] = {
        "running": running,
        "plugin_connected": running,  # In this design, heartbeat freshness implies plugin connection
        "last_seen_age_s": age,
        "catalog_path": hb.catalog_path if hb else None,
        "lightroom_version": hb.lr_version if hb else None,
        "plugin_version": hb.plugin_version if hb else None,
    }
    return json.dumps(payload, indent=2)


async def _read_collections_snapshot() -> str:
    if not _is_lightroom_running():
        return json.dumps({"error": "Lightroom Classic not running or plugin not connected"}, indent=2)

    # Use the queue to request a full collections list; wait briefly
    queue = get_queue()
    command_id = queue.enqueue(type="collection.list", payload={})

    def _wait() -> Optional[dict]:
        result = queue.wait_for_result(command_id, timeout_seconds=3)
        if result and result.ok and isinstance(result.result, dict):
            return result.result
        return None

    data = await asyncio.to_thread(_wait)
    if data is None:
        return json.dumps({"status": "pending", "message": "No snapshot available yet"}, indent=2)

    # Expecting data like { "collections": [...] }
    return json.dumps(data, indent=2)


async def _read_single_collection(collection_id: str) -> str:
    if not _is_lightroom_running():
        return json.dumps({"error": "Lightroom Classic not running or plugin not connected"}, indent=2)
    queue = get_queue()
    command_id = queue.enqueue(type="collection.list", payload={"id": collection_id})

    def _wait() -> Optional[dict]:
        result = queue.wait_for_result(command_id, timeout_seconds=3)
        if result and result.ok and isinstance(result.result, dict):
            return result.result
        return None

    data = await asyncio.to_thread(_wait)
    return json.dumps(data if data is not None else {"status": "pending"}, indent=2)


async def _read_single_collection_set(collection_set_id: str) -> str:
    if not _is_lightroom_running():
        return json.dumps({"error": "Lightroom Classic not running or plugin not connected"}, indent=2)
    queue = get_queue()
    command_id = queue.enqueue(type="collection_set.list", payload={"id": collection_set_id})

    def _wait() -> Optional[dict]:
        result = queue.wait_for_result(command_id, timeout_seconds=3)
        if result and result.ok and isinstance(result.result, dict):
            return result.result
        return None

    data = await asyncio.to_thread(_wait)
    return json.dumps(data if data is not None else {"status": "pending"}, indent=2)


async def _read_collection_by_path(path: str) -> str:
    if not _is_lightroom_running():
        return json.dumps({"error": "Lightroom Classic not running or plugin not connected"}, indent=2)
    queue = get_queue()
    command_id = queue.enqueue(type="collection.list", payload={})

    def _wait() -> Optional[dict]:
        result = queue.wait_for_result(command_id, timeout_seconds=3)
        if result and result.ok and isinstance(result.result, dict):
            return result.result
        return None

    data = await asyncio.to_thread(_wait)
    if data is None:
        return json.dumps({"status": "pending"}, indent=2)

    items = data.get("collections") or []
    match = None
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and (it.get("path") == path or it.get("name") == path):
                match = it
                break
    return json.dumps({"collection": match} if match else {"status": "not_found"}, indent=2)


async def _read_collection_set_by_path(path: str) -> str:
    if not _is_lightroom_running():
        return json.dumps({"error": "Lightroom Classic not running or plugin not connected"}, indent=2)
    queue = get_queue()
    command_id = queue.enqueue(type="collection_set.list", payload={})

    def _wait() -> Optional[dict]:
        result = queue.wait_for_result(command_id, timeout_seconds=3)
        if result and result.ok and isinstance(result.result, dict):
            return result.result
        return None

    data = await asyncio.to_thread(_wait)
    if data is None:
        return json.dumps({"status": "pending"}, indent=2)

    items = data.get("collection_sets") or data.get("collectionSets") or []
    match = None
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and (it.get("path") == path or it.get("name") == path):
                match = it
                break
    return json.dumps({"collection_set": match} if match else {"status": "not_found"}, indent=2)
