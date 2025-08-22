"""Background resource watchers and subscription-aware notifier for lrc-mcp.

Implements Phase 3a (Resource subscriptions and change notifications):

- Tracks client resource subscriptions (best-effort; notifications still broadcast
  when no explicit subscriptions are present).
- Provides a singleton ResourceNotifier that buffers notifications until a ServerSession
  is available, then flushes.
- Starts background watchers that emit notifications/resources/updated for:
  - lrc://logs/plugin on file append/mtime changes
  - lrc://status/lightroom on heartbeat updates
  - lrc://catalog/collections on detectable snapshot changes (poll/diff)
- Exposes start_watchers() to be called from main before server.run().
- Server code should register subscribe/unsubscribe handlers and attach session
  on first request via server.request_context.session.

Notes:
- The MCP lowlevel Server currently advertises resources_capability.subscribe as False
  in get_capabilities(). We still implement subscribe/unsubscribe for forward-compat.
- Notifications are emitted to the active session. If no session is attached yet,
  URIs are buffered and flushed when the session becomes available.

Project rules:
- Use asyncio tasks (non-blocking) and asyncio.to_thread for blocking queue waits.
- Logging at info level to persist to file if configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from pydantic import AnyUrl
from typing import cast

from mcp.server.session import ServerSession

from lrc_mcp.services.lrc_bridge import get_store, get_queue

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    # src/lrc_mcp/notifications.py -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _plugin_log_path() -> Path:
    return _project_root() / "plugin" / "lrc-mcp.lrplugin" / "logs" / "lrc_mcp.log"


def _is_lightroom_running(fresh_seconds: int = 30) -> bool:
    """Heartbeat freshness as proxy for LrC/plugin running."""
    store = get_store()
    hb = store.get_last_heartbeat()
    if not hb:
        return False
    now = datetime.now(timezone.utc)
    age_s = (now - hb.received_at).total_seconds()
    return age_s <= fresh_seconds


@dataclass
class _WatcherState:
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    tasks: List[asyncio.Task] = field(default_factory=list)


class ResourceNotifier:
    """Subscription-aware notifier with session attachment and buffering."""

    def __init__(self) -> None:
        self._session: Optional[ServerSession] = None
        self._lock = asyncio.Lock()
        self._subscribed_uris: Set[str] = set()
        self._buffered: Set[str] = set()

    async def attach_session(self, session: ServerSession) -> None:
        """Attach the current ServerSession and flush buffered notifications."""
        async with self._lock:
            if self._session is session:
                return
            self._session = session
            # Flush buffered notifications
            if self._buffered:
                uris = list(self._buffered)
                self._buffered.clear()
                # Fire and forget flush to avoid holding lock while awaiting
                asyncio.create_task(self._flush_many(uris))

    async def _flush_many(self, uris: List[str]) -> None:
        for uri in uris:
            try:
                await self._emit(uri)
            except Exception:
                logger.exception("Failed sending buffered notification for %s", uri)

    async def subscribe(self, uri: str) -> None:
        async with self._lock:
            self._subscribed_uris.add(uri)

    async def unsubscribe(self, uri: str) -> None:
        async with self._lock:
            self._subscribed_uris.discard(uri)

    async def notify_updated(self, uri: str) -> None:
        """Notify that a resource was updated, honoring subscriptions when present.

        Semantics:
        - If no session is available yet, buffer the URI.
        - If any subscription exists, only notify for URIs in the subscribed set.
        - If no subscriptions exist, broadcast updates for all URIs.
        """
        async with self._lock:
            # Apply subscription filter when present
            if self._subscribed_uris and uri not in self._subscribed_uris:
                return

            if not self._session:
                self._buffered.add(uri)
                return

            session = self._session

        # Emit outside the lock
        await self._emit(uri, session=session)

    async def _emit(self, uri: str, *, session: Optional[ServerSession] = None) -> None:
        sess = session or self._session
        if not sess:
            # Should not happen; buffer to be safe
            async with self._lock:
                self._buffered.add(uri)
            return
        try:
            await sess.send_resource_updated(cast(AnyUrl, uri))
            logger.info("Sent notifications/resources/updated for %s", uri)
        except Exception:
            logger.exception("Error sending resource updated notification for %s", uri)


# Singleton notifier
_NOTIFIER: Optional[ResourceNotifier] = None
_WATCHERS: Optional[_WatcherState] = None


def get_notifier() -> ResourceNotifier:
    global _NOTIFIER
    if _NOTIFIER is None:
        _NOTIFIER = ResourceNotifier()
    return _NOTIFIER


async def _watch_plugin_log(state: _WatcherState, poll_interval: float = 1.0) -> None:
    """Watch plugin log file for changes."""
    path = _plugin_log_path()
    last_sig: Optional[tuple[float, int]] = None  # (mtime, size)
    uri = "lrc://logs/plugin"
    notifier = get_notifier()

    while not state.stop_event.is_set():
        try:
            if path.exists():
                stat = path.stat()
                sig = (stat.st_mtime, stat.st_size)
                if last_sig is None:
                    last_sig = sig
                elif sig != last_sig:
                    last_sig = sig
                    await notifier.notify_updated(uri)
        except Exception:
            logger.exception("Plugin log watcher error")
        try:
            await asyncio.wait_for(state.stop_event.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass


async def _watch_status(state: _WatcherState, poll_interval: float = 1.0) -> None:
    """Watch heartbeat changes to update lrc://status/lightroom."""
    last_seen: Optional[datetime] = None
    uri = "lrc://status/lightroom"
    notifier = get_notifier()
    store = get_store()

    while not state.stop_event.is_set():
        try:
            hb = store.get_last_heartbeat()
            current = hb.received_at if hb else None
            if current and (last_seen is None or current != last_seen):
                last_seen = current
                await notifier.notify_updated(uri)
        except Exception:
            logger.exception("Status watcher error")
        try:
            await asyncio.wait_for(state.stop_event.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass


async def _read_collections_snapshot(timeout_seconds: float = 2.0) -> Optional[Dict[str, Any]]:
    """Helper to fetch a collections snapshot dict from the queue."""
    queue = get_queue()
    command_id = queue.enqueue(type="collection.list", payload={})

    def _wait() -> Optional[Dict[str, Any]]:
        res = queue.wait_for_result(command_id, timeout_seconds)
        if res and res.ok and isinstance(res.result, dict):
            return res.result
        return None

    return await asyncio.to_thread(_wait)


async def _watch_collections(state: _WatcherState, poll_interval: float = 5.0) -> None:
    """Poll for catalog/collections changes and notify on diffs."""
    uri = "lrc://catalog/collections"
    notifier = get_notifier()
    last_hash: Optional[str] = None

    while not state.stop_event.is_set():
        try:
            if _is_lightroom_running():
                data = await _read_collections_snapshot(timeout_seconds=2.0)
                if data is not None:
                    try:
                        # Stable hash to detect any structural/surface changes
                        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
                        h = hashlib.md5(payload.encode("utf-8")).hexdigest()
                    except Exception:
                        # Fallback: length-based hash
                        items = data.get("collections") or []
                        h = f"len:{len(items)}"
                    if last_hash is None:
                        last_hash = h
                    elif h != last_hash:
                        last_hash = h
                        await notifier.notify_updated(uri)
        except Exception:
            logger.exception("Collections watcher error")
        try:
            await asyncio.wait_for(state.stop_event.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass


def start_watchers() -> None:
    """Start all background watchers if not already running."""
    global _WATCHERS
    if _WATCHERS is not None:
        return
    state = _WatcherState()
    _WATCHERS = state

    loop = asyncio.get_running_loop()
    state.tasks.append(loop.create_task(_watch_plugin_log(state)))
    state.tasks.append(loop.create_task(_watch_status(state)))
    state.tasks.append(loop.create_task(_watch_collections(state)))
    logger.info("Started resource watchers: %s", [t.get_name() for t in state.tasks])


async def stop_watchers() -> None:
    """Request watcher stop and await task completion."""
    global _WATCHERS
    if _WATCHERS is None:
        return
    _WATCHERS.stop_event.set()
    await asyncio.gather(*_WATCHERS.tasks, return_exceptions=True)
    _WATCHERS = None
    logger.info("Stopped resource watchers")
