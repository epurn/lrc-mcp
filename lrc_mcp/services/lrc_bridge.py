"""Lightroom heartbeat and command-queue bridge service.

Provides:
- An in-memory store of the most recent heartbeat received from the Lightroom
  Classic plugin (Step 3).
- A simple, thread-safe in-memory command queue with result tracking to
  coordinate work between the server and the plugin (Step 4 foundation).

This module avoids persistent storage by design; future steps can swap the
implementation without changing the public API.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Heartbeat store (from Step 3)
# -----------------------------

@dataclass(frozen=True)
class Heartbeat:
    """Structured heartbeat payload stored by the server.

    Attributes:
        plugin_version: Version string of the Lightroom plugin.
        lr_version: Detected Lightroom Classic version.
        catalog_path: Optional path to the open catalog.
        received_at: Server-received UTC timestamp for this heartbeat.
        sent_at: Optional plugin-sent timestamp (if provided by plugin).
    """

    plugin_version: str
    lr_version: str
    catalog_path: Optional[str]
    received_at: datetime
    sent_at: Optional[datetime]


class HeartbeatStore:
    """Thread-safe in-memory store for the most recent heartbeat.

    This class is intentionally minimal. It offers atomic set/get semantics
    protected by a standard threading lock because FastAPI endpoints may be
    executed in different asyncio tasks and threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_heartbeat: Optional[Heartbeat] = None

    def set_heartbeat(
        self,
        *,
        plugin_version: str,
        lr_version: str,
        catalog_path: Optional[str],
        sent_at_iso: Optional[str],
    ) -> Heartbeat:
        """Record a new heartbeat as the most recent one.

        Args:
            plugin_version: Plugin version string.
            lr_version: Lightroom Classic version string.
            catalog_path: Catalog path or None.
            sent_at_iso: Optional ISO-8601 timestamp from the plugin.

        Returns:
            The stored `Heartbeat` instance.
        """
        received_at = datetime.now(timezone.utc)
        sent_at: Optional[datetime] = None
        if sent_at_iso:
            try:
                sent_at = datetime.fromisoformat(sent_at_iso.replace("Z", "+00:00"))
            except Exception:
                # Ignore parse errors; store None to avoid crashing the endpoint
                sent_at = None

        heartbeat = Heartbeat(
            plugin_version=plugin_version,
            lr_version=lr_version,
            catalog_path=catalog_path,
            received_at=received_at,
            sent_at=sent_at,
        )

        with self._lock:
            self._last_heartbeat = heartbeat

        return heartbeat

    def get_last_heartbeat(self) -> Optional[Heartbeat]:
        """Return the most recent heartbeat, if any."""
        with self._lock:
            return self._last_heartbeat


_GLOBAL_STORE: Optional[HeartbeatStore] = None


def get_store() -> HeartbeatStore:
    """Return a process-wide singleton heartbeat store."""
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = HeartbeatStore()
    return _GLOBAL_STORE


# ---------------------------------
# Command queue (Step 4 foundation)
# ---------------------------------

VISIBILITY_TIMEOUT_SECONDS = 30
IDEMPOTENCY_TTL_SECONDS = 30


@dataclass
class Command:
    id: str
    type: str
    payload: Dict[str, Any]
    enqueued_at: datetime
    visibility_deadline: Optional[datetime] = None  # None means available
    claimed_by: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class CommandResult:
    ok: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CommandQueue:
    """Thread-safe in-memory FIFO queue with single-consumer claim semantics.

    Supports basic visibility timeouts, idempotency coalescing, and waiter
    signaling for synchronous callers that want to wait on a result.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._queue: List[str] = []  # FIFO of command ids available to claim
        self._commands: Dict[str, Command] = {}
        self._results: Dict[str, CommandResult] = {}
        self._waiters: Dict[str, List[threading.Event]] = {}
        self._idempotency_index: Dict[str, Tuple[str, datetime]] = {}  # key -> (command_id, timestamp)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _cleanup_idempotency(self) -> None:
        cutoff = self._now() - timedelta(seconds=IDEMPOTENCY_TTL_SECONDS)
        to_delete = [k for k, (_, ts) in self._idempotency_index.items() if ts < cutoff]
        for k in to_delete:
            del self._idempotency_index[k]

    def enqueue(self, *, type: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> str:
        with self._lock:
            self._cleanup_idempotency()
            if idempotency_key and idempotency_key in self._idempotency_index:
                cmd_id, _ = self._idempotency_index[idempotency_key]
                # If the command is still known, return the same id
                if cmd_id in self._commands or cmd_id in self._results:
                    return cmd_id
            cmd_id = str(uuid.uuid4())
            cmd = Command(id=cmd_id, type=type, payload=payload, enqueued_at=self._now(), idempotency_key=idempotency_key)
            self._commands[cmd_id] = cmd
            self._queue.append(cmd_id)
            if idempotency_key:
                self._idempotency_index[idempotency_key] = (cmd_id, self._now())
            self._cv.notify_all()
            return cmd_id

    def claim(self, *, worker: str, max_items: int = 1) -> List[Command]:
        if max_items <= 0:
            return []
        now = self._now()
        claimed: List[Command] = []
        with self._lock:
            # Requeue items whose visibility timed out (if any are still tracked)
            for cmd in list(self._commands.values()):
                if cmd.visibility_deadline and cmd.visibility_deadline <= now:
                    cmd.visibility_deadline = None
                    cmd.claimed_by = None
                    if cmd.id not in self._queue:
                        self._queue.append(cmd.id)

            # Claim up to max_items from available queue
            i = 0
            while i < len(self._queue) and len(claimed) < max_items:
                cmd_id = self._queue.pop(0)
                cmd = self._commands.get(cmd_id)
                if not cmd:
                    continue
                if cmd.visibility_deadline is not None:
                    # Still invisible (shouldn't happen as we reset above), skip
                    continue
                cmd.claimed_by = worker
                cmd.visibility_deadline = now + timedelta(seconds=VISIBILITY_TIMEOUT_SECONDS)
                claimed.append(cmd)
            return claimed

    def complete(self, *, command_id: str, ok: bool, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
        with self._lock:
            # Remove command from active map but keep for a short time for idempotency resolution
            cmd = self._commands.pop(command_id, None)
            self._results[command_id] = CommandResult(ok=ok, result=result, error=error)
            # Signal any waiters
            for evt in self._waiters.pop(command_id, []):
                evt.set()
            # Ensure it is not still in the available queue
            try:
                self._queue.remove(command_id)
            except ValueError:
                pass

    def get_result(self, command_id: str) -> Optional[CommandResult]:
        with self._lock:
            return self._results.get(command_id)

    def wait_for_result(self, command_id: str, timeout_seconds: Optional[float]) -> Optional[CommandResult]:
        """Block the calling thread until result is available or timeout.

        Intended for synchronous tool handlers; FastAPI endpoints should avoid blocking.
        """
        deadline = self._now() + timedelta(seconds=timeout_seconds or 0)
        with self._lock:
            # Fast path
            existing = self._results.get(command_id)
            if existing is not None:
                return existing
            evt = threading.Event()
            self._waiters.setdefault(command_id, []).append(evt)
        remaining: float = max(0.0, (deadline - self._now()).total_seconds())
        if timeout_seconds is None:
            # Wait indefinitely (not recommended here)
            evt.wait()
        else:
            evt.wait(remaining)
        with self._lock:
            return self._results.get(command_id)


_GLOBAL_QUEUE: Optional[CommandQueue] = None


def get_queue() -> CommandQueue:
    global _GLOBAL_QUEUE
    if _GLOBAL_QUEUE is None:
        _GLOBAL_QUEUE = CommandQueue()
    return _GLOBAL_QUEUE
