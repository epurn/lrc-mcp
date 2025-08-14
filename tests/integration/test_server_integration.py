"""Integration tests for the lrc-mcp server."""

import pytest
import asyncio
import httpx
from unittest.mock import patch, MagicMock

from lrc_mcp.server import create_server
from lrc_mcp.health import handle_health_tool
from lrc_mcp.services.lrc_bridge import get_store, get_queue
from lrc_mcp.infra.http import create_app


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


class TestHTTPIntegration:
    """HTTP API integration tests."""
    
    @pytest.fixture
    async def client(self):
        """Create async test client."""
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test that health endpoint returns 200."""
        response = await client.post("/plugin/heartbeat", json={
            "plugin_version": "1.0.0-test",
            "lr_version": "13.2",
            "catalog_path": "/test/catalog.lrcat",
            "timestamp": "2024-01-01T00:00:00Z"
        })
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_tool_registration_via_mcp_server(self):
        """Test that all expected tools are registered via MCP server."""
        version = "1.0.0-test"
        server = create_server(version)
        
        # Verify the server has the list_tools method
        assert hasattr(server, 'list_tools')
        assert callable(server.list_tools)
        
        # Test that we can get tool definitions through the individual tool getters
        from lrc_mcp.health import get_health_tool
        from lrc_mcp.lightroom import get_launch_lightroom_tool, get_lightroom_version_tool
        from lrc_mcp.adapters.collections import (
            get_add_collection_tool, get_add_collection_set_tool,
            get_remove_collection_tool, get_edit_collection_tool
        )
        
        # Verify all expected tools can be retrieved
        expected_tools = [
            ("lrc_mcp_health", get_health_tool),
            ("lrc_launch_lightroom", get_launch_lightroom_tool),
            ("lrc_lightroom_version", get_lightroom_version_tool),
            ("lrc_add_collection", get_add_collection_tool),
            ("lrc_add_collection_set", get_add_collection_set_tool),
            ("lrc_remove_collection", get_remove_collection_tool),
            ("lrc_edit_collection", get_edit_collection_tool)
        ]
        
        for expected_name, tool_getter in expected_tools:
            tool = tool_getter()
            assert tool.name == expected_name
            assert tool.description is not None
    
    @pytest.mark.asyncio
    async def test_command_queue_integration(self, client):
        """Test command queue API endpoints."""
        # Test enqueue endpoint
        enqueue_response = await client.post("/plugin/commands/enqueue", json={
            "type": "test_command",
            "payload": {"test": "data"},
            "idempotency_key": "test-key-123"
        })
        assert enqueue_response.status_code == 200
        response_data = enqueue_response.json()
        assert response_data["status"] == "queued"
        assert "command_id" in response_data
        command_id = response_data["command_id"]
        assert isinstance(command_id, str)
        assert len(command_id) > 0
        
        # Test claim endpoint (should return our enqueued command)
        claim_response = await client.post("/plugin/commands/claim", json={
            "worker": "test-worker",
            "max": 10
        })
        assert claim_response.status_code == 200
        claim_data = claim_response.json()
        assert "commands" in claim_data
        commands = claim_data["commands"]
        assert len(commands) >= 1
        
        # Find our command in the claimed commands
        our_command = None
        for cmd in commands:
            if cmd["id"] == command_id:
                our_command = cmd
                break
        
        assert our_command is not None, "Enqueued command not found in claimed commands"
        assert our_command["type"] == "test_command"
        assert our_command["payload"] == {"test": "data"}
        
        # Test result endpoint
        result_response = await client.post(f"/plugin/commands/{command_id}/result", json={
            "ok": True,
            "result": {"success": True, "message": "Test completed"},
            "error": None
        })
        assert result_response.status_code == 200
        assert result_response.json() == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_stable_test_results(self, client):
        """Test that results are stable across multiple runs."""
        # Run the same test 3 times to verify stability
        results = []
        for i in range(3):
            response = await client.post("/plugin/heartbeat", json={
                "plugin_version": f"1.0.{i}-test",
                "lr_version": "13.2",
                "catalog_path": "/test/catalog.lrcat",
                "timestamp": f"2024-01-01T00:00:0{i}Z"
            })
            results.append(response.status_code)
        
        # All runs should succeed
        assert all(status == 200 for status in results)
