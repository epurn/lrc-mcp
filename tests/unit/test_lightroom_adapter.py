"""Unit tests for lrc_mcp.adapters.lightroom module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from lrc_mcp.adapters.lightroom import (
    get_check_command_status_tool,
    handle_check_command_status_tool,
)
from lrc_mcp.services.lrc_bridge import CommandResult


class TestLightroomAdapter:
    """Tests for lightroom adapter functions."""

    def test_get_check_command_status_tool(self):
        """Test getting the check command status tool definition."""
        tool = get_check_command_status_tool()
        assert tool.name == "check_command_status"
        assert tool.description is not None
        assert "Does check the status of a previously submitted asynchronous command" in tool.description
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "command_id" in tool.inputSchema["properties"]
        assert "status" in tool.outputSchema["properties"]
        assert "result" in tool.outputSchema["properties"]
        assert "error" in tool.outputSchema["properties"]
        assert "progress" in tool.outputSchema["properties"]

    @patch('lrc_mcp.adapters.lightroom.get_queue')
    def test_handle_check_command_status_tool_no_arguments(self, mock_get_queue):
        """Test handle_check_command_status_tool with no arguments."""
        result = handle_check_command_status_tool(None)
        assert result["status"] == "failed"
        assert "No arguments provided" in result["error"]
        assert result["result"] is None
        assert result["progress"] is None

    @patch('lrc_mcp.adapters.lightroom.get_queue')
    def test_handle_check_command_status_tool_missing_command_id(self, mock_get_queue):
        """Test handle_check_command_status_tool with missing command_id."""
        result = handle_check_command_status_tool({"some_other_field": "value"})
        assert result["status"] == "failed"
        assert "command_id is required" in result["error"]
        assert result["result"] is None
        assert result["progress"] is None

    @patch('lrc_mcp.adapters.lightroom.get_queue')
    def test_handle_check_command_status_tool_invalid_command_id(self, mock_get_queue):
        """Test handle_check_command_status_tool with invalid command_id."""
        result = handle_check_command_status_tool({"command_id": 123})
        assert result["status"] == "failed"
        assert "command_id is required and must be a string" in result["error"]
        assert result["result"] is None
        assert result["progress"] is None

    @patch('lrc_mcp.adapters.lightroom.get_queue')
    def test_handle_check_command_status_tool_completed_success(self, mock_get_queue):
        """Test handle_check_command_status_tool with completed successful command."""
        mock_queue = MagicMock()
        mock_result = CommandResult(
            ok=True,
            result={"test": "data"},
            error=None
        )
        mock_queue.get_result.return_value = mock_result
        mock_get_queue.return_value = mock_queue
        
        result = handle_check_command_status_tool({"command_id": "test-command-id"})
        assert result["status"] == "completed"
        assert result["result"] == {"test": "data"}
        assert result["error"] is None
        assert result["progress"] is None

    @patch('lrc_mcp.adapters.lightroom.get_queue')
    def test_handle_check_command_status_tool_completed_failed(self, mock_get_queue):
        """Test handle_check_command_status_tool with completed failed command."""
        mock_queue = MagicMock()
        mock_result = CommandResult(
            ok=False,
            result=None,
            error="Test error message"
        )
        mock_queue.get_result.return_value = mock_result
        mock_get_queue.return_value = mock_queue
        
        result = handle_check_command_status_tool({"command_id": "test-command-id"})
        assert result["status"] == "failed"
        assert result["result"] is None
        assert result["error"] == "Test error message"
        assert result["progress"] is None

    @patch('lrc_mcp.adapters.lightroom.get_queue')
    def test_handle_check_command_status_tool_pending(self, mock_get_queue):
        """Test handle_check_command_status_tool with pending command."""
        mock_queue = MagicMock()
        mock_queue.get_result.return_value = None
        mock_get_queue.return_value = mock_queue
        
        result = handle_check_command_status_tool({"command_id": "test-command-id"})
        assert result["status"] == "pending"
        assert result["result"] is None
        assert result["error"] is None
        assert result["progress"] is None
