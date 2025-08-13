"""Integration tests for the lrc-mcp server."""

import pytest
from unittest.mock import patch, MagicMock

from lrc_mcp.server import create_server
from lrc_mcp.health import handle_health_tool
from lrc_mcp.services.lrc_bridge import get_store, get_queue


class TestServerIntegration:
    """Integration tests for the MCP server."""

    def test_server_creation(self):
        """Test that the server can be created successfully."""
        version = "0.1.0"
        server = create_server(version)
        assert server is not None
        assert hasattr(server, 'list_tools')
        assert hasattr(server, 'call_tool')

    def test_server_tool_registration(self):
        """Test that the server registers tools correctly."""
        version = "0.1.0"
        server = create_server(version)
        
        # Verify the decorated functions exist
        assert hasattr(server, 'list_tools')
        assert callable(server.list_tools)
        assert hasattr(server, 'call_tool')
        assert callable(server.call_tool)

    def test_health_tool_integration(self):
        """Test the health tool integration."""
        version = "1.2.3-test"
        result = handle_health_tool(version)
        assert result["status"] == "ok"
        assert result["version"] == version
        assert "serverTime" in result
        assert result["serverTime"].endswith("Z")

    def test_bridge_services_singleton(self):
        """Test that bridge services return singletons."""
        store1 = get_store()
        store2 = get_store()
        assert store1 is store2
        
        queue1 = get_queue()
        queue2 = get_queue()
        assert queue1 is queue2

    def test_server_tool_definitions(self):
        """Test that all expected tools are defined."""
        from lrc_mcp.health import get_health_tool
        from lrc_mcp.lightroom import get_launch_lightroom_tool, get_lightroom_version_tool
        from lrc_mcp.adapters.collections import (
            get_add_collection_tool, get_add_collection_set_tool,
            get_remove_collection_tool, get_edit_collection_tool
        )
        
        # Test that all tool definition functions work
        health_tool = get_health_tool()
        assert health_tool.name == "lrc_mcp_health"
        assert health_tool.description is not None
        
        launch_tool = get_launch_lightroom_tool()
        assert launch_tool.name == "lrc_launch_lightroom"
        
        version_tool = get_lightroom_version_tool()
        assert version_tool.name == "lrc_lightroom_version"
        
        add_collection_tool = get_add_collection_tool()
        assert add_collection_tool.name == "lrc_add_collection"
        
        add_collection_set_tool = get_add_collection_set_tool()
        assert add_collection_set_tool.name == "lrc_add_collection_set"
        
        remove_collection_tool = get_remove_collection_tool()
        assert remove_collection_tool.name == "lrc_remove_collection"
        
        edit_collection_tool = get_edit_collection_tool()
        assert edit_collection_tool.name == "lrc_edit_collection"
