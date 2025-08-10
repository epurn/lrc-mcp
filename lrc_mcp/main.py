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

import uvicorn
from dotenv import load_dotenv

from . import __version__
from .infra.http import create_app
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


async def _run_http_server() -> None:
    app = create_app()
    port = int(os.getenv("LRC_MCP_HTTP_PORT", "8765"))
    # Ensure all HTTP server logs go to stderr and avoid noisy access logs to keep MCP stdio clean
    LOG_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": False,
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            # Reduce access logs and send them to stderr as well (we also disable via access_log=False)
            "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        },
    }
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_config=LOG_CONFIG,
        access_log=False,
        log_level="info",
    )
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


