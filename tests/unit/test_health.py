"""Unit tests for lrc_mcp.health module."""

import pytest
from unittest.mock import patch

from lrc_mcp.health import get_health_tool, handle_health_tool


class TestHealthTool:
    """Tests for health tool functions."""

    def test_get_health_tool(self):
        """Test getting the health tool definition."""
        tool = get_health_tool()
        assert tool.name == "lrc_mcp_health"
        assert tool.description == "Check the health status of the MCP server."
        assert tool.inputSchema == {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        assert tool.outputSchema is not None
        assert "status" in tool.outputSchema["properties"]
        assert "serverTime" in tool.outputSchema["properties"]
        assert "version" in tool.outputSchema["properties"]

    def test_handle_health_tool(self):
        """Test handling the health tool call."""
        version = "1.2.3"
        result = handle_health_tool(version)
        
        assert result["status"] == "ok"
        assert "serverTime" in result
        assert result["version"] == version
        # Verify serverTime is a valid ISO format string ending with Z
        assert result["serverTime"].endswith("Z")
        # Verify it can be parsed as ISO format
        import datetime
        try:
            datetime.datetime.fromisoformat(result["serverTime"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("serverTime should be valid ISO format")
