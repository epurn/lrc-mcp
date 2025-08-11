"""MCP server setup and tool registration for lrc-mcp.

References:
- MCP docs: https://modelcontextprotocol.io/docs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import mcp.types as mcp_types
from mcp.server import Server

from lrc_mcp.health import get_health_tool, handle_health_tool
from lrc_mcp.lightroom import (
    get_launch_lightroom_tool,
    get_lightroom_version_tool,
    handle_launch_lightroom_tool,
    handle_lightroom_version_tool,
)
from lrc_mcp.adapters.collections import (
    get_add_collection_tool,
    get_remove_collection_tool,
    get_edit_collection_tool,
    handle_add_collection_tool,
    handle_remove_collection_tool,
    handle_edit_collection_tool,
)

SERVER_NAME = "lrc_mcp"
logger = logging.getLogger(__name__)


def create_server(version: str) -> Server:
    """Create and return a configured MCP Server instance.

    Args:
        version: The semantic version string for the server.

    Returns:
        A configured `Server` instance with tools registered.
    """

    server = Server(SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> List[mcp_types.Tool]:
        logger.debug("list_tools called; returning available tools")
        return [
            get_health_tool(),
            get_launch_lightroom_tool(),
            get_lightroom_version_tool(),
            get_add_collection_tool(),
            get_remove_collection_tool(),
            get_edit_collection_tool(),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any] | None) -> Dict[str, Any]:
        logger.debug("call_tool invoked", extra={"tool": name, "arguments": arguments})
        if name == "lrc_mcp_health":
            result = handle_health_tool(version)
            logger.info("lrc_mcp_health returning ok", extra={"payload": result})
            return result
        if name == "lrc_launch_lightroom":
            return handle_launch_lightroom_tool(arguments)
        if name == "lrc_lightroom_version":
            return handle_lightroom_version_tool()
        if name == "lrc_add_collection":
            return handle_add_collection_tool(arguments)
        if name == "lrc_remove_collection":
            return handle_remove_collection_tool(arguments)
        if name == "lrc_edit_collection":
            return handle_edit_collection_tool(arguments)
        raise ValueError(f"Unknown tool: {name}")

    return server
