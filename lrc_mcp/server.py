"""MCP server setup and tool registration for lrc-mcp.

Exposes a single health tool `lrc_mcp_health` to verify the server is running.

References:
- MCP docs: https://modelcontextprotocol.io/docs
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Dict, List

import mcp.types as mcp_types
from mcp.server import Server


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
        logger.debug("list_tools called; returning lrc_mcp_health")
        return [
            mcp_types.Tool(
                name="lrc_mcp_health",
                description="Check the health status of the MCP server.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                outputSchema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["ok"]},
                        "serverTime": {"type": "string", "format": "date-time"},
                        "version": {"type": "string"},
                    },
                    "required": ["status", "serverTime", "version"],
                    "additionalProperties": False,
                },
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any] | None) -> Dict[str, Any]:
        logger.debug("call_tool invoked", extra={"tool": name, "arguments": arguments})
        if name == "lrc_mcp_health":
            payload: Dict[str, Any] = {
                "status": "ok",
                "serverTime": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "version": version,
            }
            logger.info("lrc_mcp_health returning ok", extra={"payload": payload})
            # Return structured content only; framework will attach JSON text content
            # and validate against outputSchema automatically.
            return payload
        raise ValueError(f"Unknown tool: {name}")

    return server


