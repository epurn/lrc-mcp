"""Entrypoint for the lrc-mcp MCP server using stdio transport.

Starts a stdio-based MCP server that exposes a single tool `lrc_mcp_health`.

References:
- MCP docs: https://modelcontextprotocol.io/docs
"""

from __future__ import annotations

import asyncio
import logging
from typing import Tuple

import mcp.server.stdio
from mcp.server import NotificationOptions
from mcp.server.models import InitializationOptions

from . import __version__
from .server import SERVER_NAME, create_server


async def _run_stdio_server() -> None:
    # Configure logging to stderr so we don't interfere with stdio transport
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = create_server(__version__)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    asyncio.run(_run_stdio_server())


if __name__ == "__main__":
    main()


