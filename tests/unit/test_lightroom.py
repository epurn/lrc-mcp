"""Unit tests for lrc_mcp.lightroom module."""

import pytest
from unittest.mock import patch, MagicMock

from lrc_mcp.lightroom import (
    get_launch_lightroom_tool,
    get_lightroom_version_tool,
    handle_launch_lightroom_tool,
    handle_lightroom_version_tool,
)
from lrc_mcp.services.lrc_bridge import Heartbeat


class TestLightroomTools:
    """Tests for Lightroom tool functions."""

    def test_get_launch_lightroom_tool(self):
        """Test getting the launch Lightroom tool definition."""
        tool = get_launch_lightroom_tool()
        assert tool.name == "lrc_launch_lightroom"
        assert tool.description is not None
        assert "Launch Lightroom Classic" in tool.description
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
        assert "last known Lightroom Classic version" in tool.description
        assert tool.inputSchema == {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        assert tool.outputSchema is not None
        assert "status" in tool.outputSchema["properties"]
        assert "lr_version" in tool.outputSchema["properties"]
        assert "last_seen" in tool.outputSchema["properties"]

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

    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_no_heartbeat(self, mock_get_store):
        """Test handling the version tool when no heartbeat exists."""
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = None
        mock_get_store.return_value = mock_store
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "waiting"
        assert result["lr_version"] is None
        assert result["last_seen"] is None

    @patch('lrc_mcp.lightroom.get_store')
    def test_handle_lightroom_version_tool_with_heartbeat(self, mock_get_store):
        """Test handling the version tool when heartbeat exists."""
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
        
        result = handle_lightroom_version_tool()
        
        assert result["status"] == "ok"
        assert result["lr_version"] == "13.2"
        assert result["last_seen"] is not None
        assert result["last_seen"].endswith("Z")
