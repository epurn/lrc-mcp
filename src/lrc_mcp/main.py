"""Entrypoint for the lrc-mcp MCP server using stdio transport.

Starts a stdio-based MCP server that exposes tools over stdio and runs a
local FastAPI app to receive heartbeats from the Lightroom Classic plugin.

References:
- MCP docs: https://modelcontextprotocol.io/docs
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Tuple

import mcp.server.stdio
from mcp.server import NotificationOptions
from mcp.server.models import InitializationOptions
from lrc_mcp.notifications import start_watchers

import uvicorn
from dotenv import load_dotenv

from lrc_mcp import __version__
from lrc_mcp.infra.http import create_app
from lrc_mcp.server import SERVER_NAME, create_server
from lrc_mcp.uvicorn_config import UVICORN_CONFIG, DEV_CONFIG


async def _run_stdio_server() -> None:
    # Configure logging to stderr so we don't interfere with stdio transport
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = create_server(__version__)
    # Start background resource watchers (logs/status/catalog)
    start_watchers()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(resources_changed=True),
                    experimental_capabilities={},
                ),
            ),
        )


async def _run_http_server() -> None:
    app = create_app()
    config = uvicorn.Config(app, **UVICORN_CONFIG)
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except OSError as exc:  # Port in use or bind failure
        # WinError 10048 (Windows) or Errno 98 (POSIX) -> address in use
        logging.warning("HTTP server disabled: %s", exc)
        return


async def _run_all() -> None:
    # Load environment variables from .env if present
    load_dotenv()
    await asyncio.gather(
        _run_stdio_server(),
        _run_http_server(),
    )


def main() -> None:
    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
