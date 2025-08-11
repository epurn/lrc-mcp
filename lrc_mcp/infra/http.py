"""Local FastAPI app exposing plugin endpoints for the LrC bridge.

This app binds to localhost only via the uvicorn server in main.py.
"""

from __future__ import annotations

from fastapi import FastAPI

from lrc_mcp.api.routes import router as plugin_router


def create_app() -> FastAPI:
    app = FastAPI(title="lrc-mcp plugin bridge", docs_url=None, redoc_url=None)
    app.include_router(plugin_router)
    return app
