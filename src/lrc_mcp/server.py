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
    get_kill_lightroom_tool,
    handle_launch_lightroom_tool,
    handle_lightroom_version_tool,
    handle_kill_lightroom_tool,
)
from lrc_mcp.adapters.collections import (
    get_collection_set_tool,
    get_collection_tool,
    handle_collection_set_tool,
    handle_collection_tool,
)

from lrc_mcp.adapters.lightroom import (
    get_check_command_status_tool,
    handle_check_command_status_tool,
)

from lrc_mcp.adapters.test import (
    get_run_tests_tool,
    handle_run_tests_tool,
)

from lrc_mcp.adapters.photo_metadata import (
    get_photo_metadata_tool,
    handle_photo_metadata_tool,
)
from lrc_mcp import resources as lrc_resources
from pydantic import AnyUrl
from lrc_mcp.notifications import get_notifier

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
        # Attach session to notifier for resource updates
        await get_notifier().attach_session(server.request_context.session)
        return [
            get_health_tool(),
            get_launch_lightroom_tool(),
            get_lightroom_version_tool(),
            get_kill_lightroom_tool(),
            get_collection_set_tool(),
            get_collection_tool(),
            get_check_command_status_tool(),
            get_run_tests_tool(),
            get_photo_metadata_tool(),
        ]

    @server.list_resources()
    async def list_resources() -> List[mcp_types.Resource]:
        logger.debug("list_resources called; returning available resources")
        await get_notifier().attach_session(server.request_context.session)
        return lrc_resources.list_resources()

    @server.list_resource_templates()
    async def list_resource_templates() -> List[mcp_types.ResourceTemplate]:
        logger.debug("list_resource_templates called; returning resource templates")
        await get_notifier().attach_session(server.request_context.session)
        return lrc_resources.list_resource_templates()

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> str:
        logger.debug("read_resource called", extra={"uri": str(uri)})
        await get_notifier().attach_session(server.request_context.session)
        # Delegate to our resources module (returns text or JSON string)
        return await lrc_resources.read_resource(str(uri))

    @server.subscribe_resource()
    async def subscribe_resource(uri: AnyUrl) -> None:
        logger.debug("subscribe_resource called", extra={"uri": str(uri)})
        await get_notifier().subscribe(str(uri))

    @server.unsubscribe_resource()
    async def unsubscribe_resource(uri: AnyUrl) -> None:
        logger.debug("unsubscribe_resource called", extra={"uri": str(uri)})
        await get_notifier().unsubscribe(str(uri))

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any] | None) -> Dict[str, Any]:
        logger.debug("call_tool invoked", extra={"tool": name, "arguments": arguments})
        await get_notifier().attach_session(server.request_context.session)
        if name == "lrc_mcp_health":
            result = handle_health_tool(version)
            logger.info("lrc_mcp_health returning ok", extra={"payload": result})
            return result
        if name == "lrc_launch_lightroom":
            return handle_launch_lightroom_tool(arguments)
        if name == "lrc_lightroom_version":
            return handle_lightroom_version_tool()
        if name == "lrc_kill_lightroom":
            return handle_kill_lightroom_tool(arguments)
        if name == "lrc_collection_set":
            return handle_collection_set_tool(arguments)
        if name == "lrc_collection":
            return handle_collection_tool(arguments)
        if name == "check_command_status":
            return handle_check_command_status_tool(arguments)
        if name == "lrc_run_tests":
            return handle_run_tests_tool(arguments)
        if name == "lrc_photo_metadata":
            return handle_photo_metadata_tool(arguments)
        raise ValueError(f"Unknown tool: {name}")

    return server
