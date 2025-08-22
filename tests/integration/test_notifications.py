import asyncio
from pathlib import Path
from typing import List, cast

import httpx
import pytest

from mcp.server.session import ServerSession

import lrc_mcp.notifications as notifications
from lrc_mcp.notifications import (
    get_notifier,
    start_watchers,
    stop_watchers,
)
from lrc_mcp.infra.http import create_app


class DummySession:
    """
    Minimal async-compatible session capturing notifications/resources/updated calls.
    """

    def __init__(self, target_uri: str | None = None) -> None:
        self.events: List[str] = []
        self._target_uri = target_uri
        self._event = asyncio.Event()

    async def send_resource_updated(self, uri) -> None:
        uri_str = str(uri)
        self.events.append(uri_str)
        # If a specific target is set, gate the event; else, any event triggers.
        if self._target_uri is None or uri_str == self._target_uri:
            self._event.set()

    async def wait_for_event(self, timeout: float = 3.0) -> List[str]:
        await asyncio.wait_for(self._event.wait(), timeout=timeout)
        # Small yield to let any queued notifications settle
        await asyncio.sleep(0)
        return list(self.events)


@pytest.fixture
async def http_client():
    """
    Async HTTP client for FastAPI bridge endpoints.
    """
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_watchers_lifecycle_start_stop():
    """
    Verify that start_watchers/stop_watchers run and teardown cleanly and idempotently.
    """
    # Ensure clean start
    await stop_watchers()

    start_watchers()
    # Give the event loop a moment to start tasks
    await asyncio.sleep(0.05)

    # First stop
    await stop_watchers()
    # Second stop should be idempotent/no-op
    await stop_watchers()


@pytest.mark.asyncio
async def test_notifications_logs_plugin(monkeypatch):
    """
    Subscribe to lrc://logs/plugin, append to the log file, and assert a notifications/resources/updated event.
    Uses accelerated polling via monkeypatch.
    """
    target_uri = "lrc://logs/plugin"

    # Accelerate log watcher polling
    orig = notifications._watch_plugin_log

    async def fast_watch_plugin_log(state, poll_interval: float = 0.1):
        return await orig(state, poll_interval=poll_interval)

    monkeypatch.setattr(notifications, "_watch_plugin_log", fast_watch_plugin_log)

    # Attach dummy session and subscribe
    session = DummySession(target_uri=target_uri)
    await get_notifier().attach_session(cast(ServerSession, session))
    await get_notifier().subscribe(target_uri)

    # Start watchers (includes our patched fast log watcher)
    start_watchers()

    try:
        # Ensure log file exists then append
        log_path = Path(__file__).resolve().parents[2] / "plugin" / "lrc-mcp.lrplugin" / "logs" / "lrc_mcp.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            log_path.touch(exist_ok=True)

        # Write baseline then append to ensure watcher detects a change
        log_path.write_text("BASELINE\n", encoding="utf-8")
        await asyncio.sleep(0.2)
        existing = log_path.read_text(encoding="utf-8", errors="ignore")
        log_path.write_text(existing + "TEST LOG APPEND\n", encoding="utf-8")

        events = await session.wait_for_event(timeout=5.0)
        assert target_uri in events
    finally:
        await stop_watchers()


@pytest.mark.asyncio
async def test_notifications_status_lightroom(monkeypatch, http_client):
    """
    Subscribe to lrc://status/lightroom, trigger a heartbeat via HTTP, and assert a notifications/resources/updated event.
    Uses accelerated polling via monkeypatch.
    """
    target_uri = "lrc://status/lightroom"

    # Accelerate status watcher polling
    orig = notifications._watch_status

    async def fast_watch_status(state, poll_interval: float = 0.1):
        return await orig(state, poll_interval=poll_interval)

    monkeypatch.setattr(notifications, "_watch_status", fast_watch_status)

    # Attach dummy session and subscribe
    session = DummySession(target_uri=target_uri)
    await get_notifier().attach_session(cast(ServerSession, session))
    await get_notifier().subscribe(target_uri)

    # Start watchers (includes our patched fast status watcher)
    start_watchers()

    try:
        # Post a heartbeat to update the store
        resp = await http_client.post(
            "/plugin/heartbeat",
            json={
                "plugin_version": "test-1.0.0",
                "lr_version": "14.5",
                "catalog_path": "/test/catalog.lrcat",
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )
        assert resp.status_code == 200

        events = await session.wait_for_event(timeout=5.0)
        assert target_uri in events
    finally:
        await stop_watchers()


@pytest.mark.asyncio
async def test_notifications_catalog_collections(monkeypatch, http_client):
    """
    Subscribe to lrc://catalog/collections, simulate a snapshot change, and assert a notifications/resources/updated event.
    Uses:
      - accelerated polling via monkeypatch
      - monkeypatched snapshot reader to alternate return values
      - a heartbeat to satisfy _is_lightroom_running()
    """
    target_uri = "lrc://catalog/collections"

    # Accelerate collections watcher polling
    orig = notifications._watch_collections

    async def fast_watch_collections(state, poll_interval: float = 0.1):
        return await orig(state, poll_interval=poll_interval)

    monkeypatch.setattr(notifications, "_watch_collections", fast_watch_collections)

    # Make snapshot alternate to trigger a detected change
    call_count = {"n": 0}

    async def fake_snapshot(timeout_seconds: float = 2.0):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"collections": [{"id": "1", "name": "A"}]}
        else:
            return {"collections": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]}

    monkeypatch.setattr(notifications, "_read_collections_snapshot", fake_snapshot)

    # Attach dummy session and subscribe
    session = DummySession(target_uri=target_uri)
    await get_notifier().attach_session(cast(ServerSession, session))
    await get_notifier().subscribe(target_uri)

    # Start watchers (includes patched fast collections watcher)
    start_watchers()

    try:
        # Send a heartbeat so _is_lightroom_running() returns True
        resp = await http_client.post(
            "/plugin/heartbeat",
            json={
                "plugin_version": "test-1.0.0",
                "lr_version": "14.5",
                "catalog_path": "/test/catalog.lrcat",
                "timestamp": "2024-01-01T00:00:01Z",
            },
        )
        assert resp.status_code == 200

        events = await session.wait_for_event(timeout=5.0)
        assert target_uri in events
    finally:
        await stop_watchers()
