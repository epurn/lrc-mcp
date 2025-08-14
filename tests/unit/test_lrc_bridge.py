"""Unit tests for lrc_mcp.services.lrc_bridge module."""

import pytest
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from lrc_mcp.services.lrc_bridge import (
    Heartbeat,
    HeartbeatStore,
    Command,
    CommandResult,
    CommandQueue,
    get_store,
    get_queue,
)


class TestHeartbeat:
    """Tests for Heartbeat dataclass."""

    def test_heartbeat_creation(self):
        """Test creating a Heartbeat instance."""
        now = datetime.now(timezone.utc)
        heartbeat = Heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            received_at=now,
            sent_at=now
        )
        assert heartbeat.plugin_version == "1.0.0"
        assert heartbeat.lr_version == "13.2"
        assert heartbeat.catalog_path == "/path/to/catalog"
        assert heartbeat.received_at == now
        assert heartbeat.sent_at == now


class TestHeartbeatStore:
    """Tests for HeartbeatStore class."""

    def test_store_creation(self):
        """Test creating a HeartbeatStore."""
        store = HeartbeatStore()
        assert store._last_heartbeat is None
        assert isinstance(store._lock, threading.Lock)

    def test_set_heartbeat(self):
        """Test setting a heartbeat."""
        store = HeartbeatStore()
        now = datetime.now(timezone.utc)
        
        heartbeat = store.set_heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            sent_at_iso=now.isoformat()
        )
        
        assert heartbeat.plugin_version == "1.0.0"
        assert heartbeat.lr_version == "13.2"
        assert heartbeat.catalog_path == "/path/to/catalog"
        assert heartbeat.sent_at == now

    def test_set_heartbeat_invalid_iso(self):
        """Test setting a heartbeat with invalid ISO timestamp."""
        store = HeartbeatStore()
        
        heartbeat = store.set_heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            sent_at_iso="invalid"
        )
        
        assert heartbeat.sent_at is None

    def test_get_last_heartbeat(self):
        """Test getting the last heartbeat."""
        store = HeartbeatStore()
        assert store.get_last_heartbeat() is None
        
        # Set a heartbeat
        heartbeat = store.set_heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            sent_at_iso=None
        )
        
        retrieved = store.get_last_heartbeat()
        assert retrieved is not None
        assert retrieved.plugin_version == "1.0.0"

    def test_thread_safety(self):
        """Test that the store is thread-safe."""
        store = HeartbeatStore()
        results = []
        
        def set_heartbeat(index):
            heartbeat = store.set_heartbeat(
                plugin_version=f"1.0.{index}",
                lr_version="13.2",
                catalog_path="/path/to/catalog",
                sent_at_iso=None
            )
            results.append(heartbeat)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=set_heartbeat, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All operations should succeed
        assert len(results) == 10
        # Last heartbeat should be one of them
        last_heartbeat = store.get_last_heartbeat()
        assert last_heartbeat is not None


class TestCommandQueue:
    """Tests for CommandQueue class."""

    def test_queue_creation(self):
        """Test creating a CommandQueue."""
        queue = CommandQueue()
        assert queue._queue == []
        assert queue._commands == {}
        assert queue._results == {}
        assert queue._waiters == {}
        assert queue._idempotency_index == {}

    def test_enqueue_command(self):
        """Test enqueuing a command."""
        queue = CommandQueue()
        command_id = queue.enqueue(
            type="test.command",
            payload={"key": "value"}
        )
        
        assert command_id is not None
        assert isinstance(command_id, str)
        assert command_id in queue._commands
        assert command_id in queue._queue
        assert len(queue._queue) == 1

    def test_enqueue_with_idempotency(self):
        """Test enqueuing with idempotency key."""
        queue = CommandQueue()
        idempotency_key = "test-key"
        
        # First enqueue
        command_id1 = queue.enqueue(
            type="test.command",
            payload={"key": "value"},
            idempotency_key=idempotency_key
        )
        
        # Second enqueue with same key should return same ID
        command_id2 = queue.enqueue(
            type="test.command",
            payload={"key": "value2"},
            idempotency_key=idempotency_key
        )
        
        assert command_id1 == command_id2
        # Should have the payload from the first command
        command = queue._commands[command_id1]
        assert command.payload == {"key": "value"}

    def test_claim_commands(self):
        """Test claiming commands."""
        queue = CommandQueue()
        
        # Enqueue some commands
        command_id1 = queue.enqueue(type="test.command1", payload={})
        command_id2 = queue.enqueue(type="test.command2", payload={})
        
        # Claim one command
        claimed = queue.claim(worker="test-worker", max_items=1)
        assert len(claimed) == 1
        assert claimed[0].id == command_id1
        assert claimed[0].claimed_by == "test-worker"
        assert claimed[0].visibility_deadline is not None
        
        # Claim remaining commands
        claimed = queue.claim(worker="test-worker2", max_items=5)
        assert len(claimed) == 1
        assert claimed[0].id == command_id2

    def test_claim_with_timeout(self):
        """Test claiming commands with visibility timeout."""
        queue = CommandQueue()
        command_id = queue.enqueue(type="test.command", payload={})
        
        # Claim the command
        claimed = queue.claim(worker="test-worker", max_items=1)
        assert len(claimed) == 1
        original_deadline = claimed[0].visibility_deadline
        
        # Wait a bit and claim again - should get nothing since it's still invisible
        claimed = queue.claim(worker="test-worker2", max_items=1)
        assert len(claimed) == 0
        
        # Manually expire the visibility deadline
        queue._commands[command_id].visibility_deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        # Now it should be claimable again
        claimed = queue.claim(worker="test-worker2", max_items=1)
        assert len(claimed) == 1

    def test_complete_command(self):
        """Test completing a command."""
        queue = CommandQueue()
        command_id = queue.enqueue(type="test.command", payload={"test": "data"})
        
        # Claim the command
        claimed = queue.claim(worker="test-worker", max_items=1)
        assert len(claimed) == 1
        
        # Complete the command
        queue.complete(
            command_id=command_id,
            ok=True,
            result={"success": True},
            error=None
        )
        
        # Command should be removed from active commands
        assert command_id not in queue._commands
        # Result should be stored
        result = queue.get_result(command_id)
        assert result is not None
        assert result.ok is True
        assert result.result == {"success": True}

    def test_get_result(self):
        """Test getting command results."""
        queue = CommandQueue()
        command_id = queue.enqueue(type="test.command", payload={})
        
        # Complete the command
        queue.complete(
            command_id=command_id,
            ok=False,
            result=None,
            error="Something went wrong"
        )
        
        # Get the result
        result = queue.get_result(command_id)
        assert result is not None
        assert result.ok is False
        assert result.error == "Something went wrong"
        assert result.result is None

    def test_wait_for_result(self):
        """Test waiting for command results."""
        queue = CommandQueue()
        command_id = queue.enqueue(type="test.command", payload={})
        
        # Wait for result with timeout (should return None since no result yet)
        result = queue.wait_for_result(command_id, timeout_seconds=0.1)
        assert result is None
        
        # Complete the command in another thread
        def complete_command():
            import time
            time.sleep(0.1)
            queue.complete(
                command_id=command_id,
                ok=True,
                result={"completed": True},
                error=None
            )
        
        thread = threading.Thread(target=complete_command)
        thread.start()
        
        # Wait for result (should get it now)
        result = queue.wait_for_result(command_id, timeout_seconds=1.0)
        assert result is not None
        assert result.ok is True
        assert result.result == {"completed": True}
        
        thread.join()


class TestGlobalFunctions:
    """Tests for global functions."""

    def test_get_store_singleton(self):
        """Test that get_store returns a singleton."""
        store1 = get_store()
        store2 = get_store()
        assert store1 is store2

    def test_get_queue_singleton(self):
        """Test that get_queue returns a singleton."""
        queue1 = get_queue()
        queue2 = get_queue()
        assert queue1 is queue2
