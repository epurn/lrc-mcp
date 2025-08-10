"""Lightroom heartbeat bridge service.

Provides an in-memory store of the most recent heartbeat received from the
Lightroom Classic plugin. Designed to be simple, thread-safe, and deterministic.

This module avoids persistent storage by design in Step 3; future steps can
swap the implementation without changing the public API.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


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


