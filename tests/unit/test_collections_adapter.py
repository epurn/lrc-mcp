"""Unit tests for lrc_mcp.adapters.collections module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from lrc_mcp.adapters.collections import (
    _is_lightroom_running,
    _check_lightroom_dependency,
    get_add_collection_tool,
    get_add_collection_set_tool,
    get_remove_collection_tool,
    get_remove_collection_set_tool,
    get_edit_collection_tool,
    handle_add_collection_tool,
    handle_add_collection_set_tool,
    handle_remove_collection_tool,
    handle_remove_collection_set_tool,
    handle_edit_collection_tool,
)
from lrc_mcp.services.lrc_bridge import Heartbeat


class TestCollectionsAdapter:
    """Tests for collections adapter functions."""

    @patch('lrc_mcp.adapters.collections.get_store')
    def test_is_lightroom_running_no_heartbeat(self, mock_get_store):
        """Test _is_lightroom_running when no heartbeat exists."""
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = None
        mock_get_store.return_value = mock_store
        
        result = _is_lightroom_running()
        assert result is False

    @patch('lrc_mcp.adapters.collections.get_store')
    def test_is_lightroom_running_old_heartbeat(self, mock_get_store):
        """Test _is_lightroom_running when heartbeat is too old."""
        from datetime import datetime, timezone, timedelta
        old_time = datetime.now(timezone.utc) - timedelta(seconds=60)  # 60 seconds ago
        
        mock_heartbeat = Heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            received_at=old_time,
            sent_at=None
        )
        
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = mock_heartbeat
        mock_get_store.return_value = mock_store
        
        result = _is_lightroom_running()
        assert result is False

    @patch('lrc_mcp.adapters.collections.get_store')
    def test_is_lightroom_running_recent_heartbeat(self, mock_get_store):
        """Test _is_lightroom_running when heartbeat is recent."""
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=10)  # 10 seconds ago
        
        mock_heartbeat = Heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            received_at=recent_time,
            sent_at=None
        )
        
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = mock_heartbeat
        mock_get_store.return_value = mock_store
        
        result = _is_lightroom_running()
        assert result is True

    @patch('lrc_mcp.adapters.collections._is_lightroom_running')
    def test_check_lightroom_dependency_not_running(self, mock_is_running):
        """Test _check_lightroom_dependency when Lightroom is not running."""
        mock_is_running.return_value = False
        
        result = _check_lightroom_dependency()
        assert result is not None
        assert result["status"] == "error"
        assert "Lightroom Classic is not running" in result["error"]
        assert result["command_id"] is None

    @patch('lrc_mcp.adapters.collections._is_lightroom_running')
    def test_check_lightroom_dependency_running(self, mock_is_running):
        """Test _check_lightroom_dependency when Lightroom is running."""
        mock_is_running.return_value = True
        
        result = _check_lightroom_dependency()
        assert result is None

    def test_get_add_collection_tool(self):
        """Test getting the add collection tool definition."""
        tool = get_add_collection_tool()
        assert tool.name == "lrc_add_collection"
        assert tool.description is not None
        assert "Does create a new collection" in tool.description
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "name" in tool.inputSchema["properties"]
        assert "parent_path" in tool.inputSchema["properties"]


    def test_get_add_collection_set_tool(self):
        """Test getting the add collection set tool definition."""
        tool = get_add_collection_set_tool()
        assert tool.name == "lrc_add_collection_set"
        assert tool.description is not None
        assert "Does create a new collection set" in tool.description
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None


    def test_get_remove_collection_tool(self):
        """Test getting the remove collection tool definition."""
        tool = get_remove_collection_tool()
        assert tool.name == "lrc_remove_collection"
        assert tool.description is not None
        assert "Does remove a collection" in tool.description
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "collection_path" in tool.inputSchema["properties"]


    def test_get_edit_collection_tool(self):
        """Test getting the edit collection tool definition."""
        tool = get_edit_collection_tool()
        assert tool.name == "lrc_edit_collection"
        assert tool.description is not None
        assert "Does edit (rename/move) a collection" in tool.description
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "collection_path" in tool.inputSchema["properties"]


    def test_get_remove_collection_set_tool(self):
        """Test getting the remove collection set tool definition."""
        tool = get_remove_collection_set_tool()
        assert tool.name == "lrc_remove_collection_set"
        assert tool.description is not None
        assert "Does remove a collection set" in tool.description
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "collection_set_path" in tool.inputSchema["properties"]


    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    def test_handle_add_collection_tool_dependency_error(self, mock_check):
        """Test handle_add_collection_tool when Lightroom dependency check fails."""
        error_response = {
            "status": "error",
            "error": "Lightroom not running",
            "command_id": None,
            "created": None,
            "collection": None
        }
        mock_check.return_value = error_response
        
        result = handle_add_collection_tool({"name": "Test Collection"})
        assert result == error_response

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_add_collection_tool_no_arguments(self, mock_get_queue, mock_check):
        """Test handle_add_collection_tool with no arguments."""
        mock_check.return_value = None  # No dependency error
        
        result = handle_add_collection_tool(None)
        assert result["status"] == "error"
        assert result["command_id"] is None
        assert "No arguments provided" in result["error"]

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_add_collection_tool_missing_name(self, mock_get_queue, mock_check):
        """Test handle_add_collection_tool with missing name."""
        mock_check.return_value = None  # No dependency error
        
        result = handle_add_collection_tool({"parent_path": "Sets/Nature"})
        assert result["status"] == "error"
        assert result["command_id"] is None
        assert "Collection name is required" in result["error"]

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_add_collection_tool_success(self, mock_get_queue, mock_check):
        """Test handle_add_collection_tool success case."""
        mock_check.return_value = None  # No dependency error
        
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "test-command-id"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"created": True, "collection": {"id": "123", "name": "Test", "path": "Test"}}
        )
        mock_get_queue.return_value = mock_queue
        
        arguments = {"name": "Test Collection", "parent_path": "Sets/Nature"}
        result = handle_add_collection_tool(arguments)
        
        assert result["status"] == "ok"
        assert result["command_id"] == "test-command-id"
        assert result["created"] is True
        mock_queue.enqueue.assert_called_once()
        mock_queue.wait_for_result.assert_called_once_with("test-command-id", 5)

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_remove_collection_tool_success(self, mock_get_queue, mock_check):
        """Test handle_remove_collection_tool success case."""
        mock_check.return_value = None  # No dependency error
        
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "test-command-id"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"removed": True}
        )
        mock_get_queue.return_value = mock_queue
        
        arguments = {"collection_path": "Test Collection"}
        result = handle_remove_collection_tool(arguments)
        
        assert result["status"] == "ok"
        assert result["command_id"] == "test-command-id"
        assert result["removed"] is True

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_edit_collection_tool_success(self, mock_get_queue, mock_check):
        """Test handle_edit_collection_tool success case."""
        mock_check.return_value = None  # No dependency error
        
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "test-command-id"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"updated": True, "collection": {"id": "123", "name": "Renamed", "path": "Renamed"}}
        )
        mock_get_queue.return_value = mock_queue
        
        arguments = {
            "collection_path": "Old Name",
            "new_name": "New Name",
            "new_parent_path": "Sets/New Location"
        }
        result = handle_edit_collection_tool(arguments)
        
        assert result["status"] == "ok"
        assert result["command_id"] == "test-command-id"
        assert result["updated"] is True

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_add_collection_set_tool_success(self, mock_get_queue, mock_check):
        """Test handle_add_collection_set_tool success case."""
        mock_check.return_value = None  # No dependency error
        
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "test-command-id"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"created": True, "collection_set": {"id": "123", "name": "Test Set", "path": "Test Set"}}
        )
        mock_get_queue.return_value = mock_queue
        
        arguments = {"name": "Test Set", "parent_path": "Sets/Parent"}
        result = handle_add_collection_set_tool(arguments)
        
        assert result["status"] == "ok"
        assert result["command_id"] == "test-command-id"
        assert result["created"] is True

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_remove_collection_set_tool_success(self, mock_get_queue, mock_check):
        """Test handle_remove_collection_set_tool success case."""
        mock_check.return_value = None  # No dependency error
        
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "test-command-id"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"removed": True}
        )
        mock_get_queue.return_value = mock_queue
        
        arguments = {"collection_set_path": "Test Set"}
        result = handle_remove_collection_set_tool(arguments)
        
        assert result["status"] == "ok"
        assert result["command_id"] == "test-command-id"
        assert result["removed"] is True
