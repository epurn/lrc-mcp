"""Unit tests for lrc_mcp.lightroom module."""

import pytest
from unittest.mock import patch, MagicMock

from lrc_mcp.lightroom import (
    get_launch_lightroom_tool,
    get_lightroom_version_tool,
    get_kill_lightroom_tool,
    handle_launch_lightroom_tool,
    handle_lightroom_version_tool,
    handle_kill_lightroom_tool,
)
from lrc_mcp.services.lrc_bridge import Heartbeat


class TestLightroomTools:
    """Tests for Lightroom tool functions."""

    def test_get_launch_lightroom_tool(self):
        """Test getting the launch Lightroom tool definition."""
        tool = get_launch_lightroom_tool()
        assert tool.name == "lrc_launch_lightroom"
        assert tool.description is not None
        assert "Does launch Lightroom Classic" in tool.description
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "launched" in tool.outputSchema["properties"]
        assert "pid" in tool.outputSchema["properties"]
        assert "path" in tool.outputSchema["properties"]


    def test_get_lightroom_version_tool(self):
        """Test getting the Lightroom version tool definition."""
        tool = get_lightroom_version_tool()
        assert tool.name == "lrc_lightroom_version"
        assert tool.description is not None
        assert "enhanced process status information" in tool.description
        assert tool.inputSchema == {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        assert tool.outputSchema is not None
        assert "status" in tool.outputSchema["properties"]
        assert "running" in tool.outputSchema["properties"]
        assert "lr_version" in tool.outputSchema["properties"]
        assert "last_seen" in tool.outputSchema["properties"]
        # Check that status now includes "not_running"
        status_prop = tool.outputSchema["properties"]["status"]
        assert "not_running" in status_prop["enum"]



    def test_get_kill_lightroom_tool(self):
        """Test getting the kill Lightroom tool definition."""
        tool = get_kill_lightroom_tool()
        assert tool.name == "lrc_kill_lightroom"
        assert tool.description is not None
        assert "gracefully terminate" in tool.description
        assert tool.inputSchema == {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        assert tool.outputSchema is not None
        assert "killed" in tool.outputSchema["properties"]
        assert "previous_pid" in tool.outputSchema["properties"]
        assert "duration_ms" in tool.outputSchema["properties"]


    @patch('lrc_mcp.lightroom.launch_lightroom')
    def test_handle_launch_lightroom_tool(self, mock_launch):
        """Test handling the launch Lightroom tool call."""
        # Mock the launch result
        mock_result = MagicMock()
        mock_result.launched = True
        mock_result.pid = 12345
        mock_result.path = "/path/to/lightroom.exe"
        mock_launch.return_value = mock_result
        
        arguments = {"path": "/custom/path/to/lightroom.exe"}
        result = handle_launch_lightroom_tool(arguments)
        
        assert result["launched"] is True
        assert result["pid"] == 12345
        assert result["path"] == "/path/to/lightroom.exe"
        mock_launch.assert_called_once_with("/custom/path/to/lightroom.exe")

    @patch('lrc_mcp.lightroom.launch_lightroom')
    def test_handle_launch_lightroom_tool_no_arguments(self, mock_launch):
        """Test handling the launch Lightroom tool call with no arguments."""
        mock_result = MagicMock()
        mock_result.launched = False
        mock_result.pid = None
        mock_result.path = "/default/path/to/lightroom.exe"
        mock_launch.return_value = mock_result
        
        result = handle_launch_lightroom_tool(None)
        
        assert result["launched"] is False
        assert result["pid"] is None
        assert result["path"] == "/default/path/to/lightroom.exe"
        mock_launch.assert_called_once_with(None)

    @patch('lrc_mcp.lightroom.is_lightroom_process_running')
    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_no_heartbeat_no_process(self, mock_get_store, mock_is_running):
        """Test handling the version tool when no heartbeat exists and no process running."""
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = None
        mock_get_store.return_value = mock_store
        mock_is_running.return_value = False
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "not_running"
        assert result["running"] is False
        assert result["lr_version"] is None
        assert result["last_seen"] is None

    @patch('lrc_mcp.lightroom.is_lightroom_process_running')
    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_no_heartbeat_with_process(self, mock_get_store, mock_is_running):
        """Test handling the version tool when no heartbeat exists but process is running."""
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = None
        mock_get_store.return_value = mock_store
        mock_is_running.return_value = True
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "waiting"
        assert result["running"] is True
        assert result["lr_version"] is None
        assert result["last_seen"] is None

    @patch('lrc_mcp.lightroom.is_lightroom_process_running')
    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_recent_heartbeat_with_process(self, mock_get_store, mock_is_running):
        """Test handling the version tool with recent heartbeat and running process."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        mock_heartbeat = Heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            received_at=now,
            sent_at=None
        )
        
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = mock_heartbeat
        mock_get_store.return_value = mock_store
        mock_is_running.return_value = True
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "ok"
        assert result["running"] is True
        assert result["lr_version"] == "13.2"
        assert result["last_seen"] is not None
        assert result["last_seen"].endswith("Z")

    @patch('lrc_mcp.lightroom.is_lightroom_process_running')
    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_recent_heartbeat_no_process(self, mock_get_store, mock_is_running):
        """Test handling the version tool with recent heartbeat but no process running."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        recent_time = now - timedelta(seconds=30)  # 30 seconds ago
        
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
        mock_is_running.return_value = False
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "waiting"
        assert result["running"] is False
        assert result["lr_version"] == "13.2"
        assert result["last_seen"] is not None

    @patch('lrc_mcp.lightroom.is_lightroom_process_running')
    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_old_heartbeat_with_process(self, mock_get_store, mock_is_running):
        """Test handling the version tool with old heartbeat but process running."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=90)  # 90 seconds ago
        
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
        mock_is_running.return_value = True
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "waiting"
        assert result["running"] is True
        assert result["lr_version"] == "13.2"
        assert result["last_seen"] is not None

    @patch('lrc_mcp.lightroom.is_lightroom_process_running')
    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_old_heartbeat_no_process(self, mock_get_store, mock_is_running):
        """Test handling the version tool with old heartbeat and no process running."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=90)  # 90 seconds ago
        
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
        mock_is_running.return_value = False
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "not_running"
        assert result["running"] is False
        assert result["lr_version"] == "13.2"
        assert result["last_seen"] is not None

    @patch('lrc_mcp.lightroom.kill_lightroom')
    def test_handle_kill_lightroom_tool(self, mock_kill):
        """Test handling the kill Lightroom tool call."""
        # Mock the kill result
        mock_result = {
            "killed": True,
            "previous_pid": 12345,
            "duration_ms": 1500
        }
        mock_kill.return_value = mock_result
        
        result = handle_kill_lightroom_tool(None)
        
        assert result["killed"] is True
        assert result["previous_pid"] == 12345
        assert result["duration_ms"] == 1500
        mock_kill.assert_called_once_with()
