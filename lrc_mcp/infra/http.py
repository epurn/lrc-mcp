"""Local FastAPI app exposing a heartbeat endpoint for the LrC plugin.

This module defines a FastAPI application to receive heartbeat beacons from
the Lightroom Classic Lua plugin. It is intended to run on localhost only.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..services.lrc_bridge import get_store

logger = logging.getLogger(__name__)


class HeartbeatPayload(BaseModel):
    plugin_version: str = Field(..., description="Version of the LrC plugin")
    lr_version: str = Field(..., description="Detected Lightroom Classic version")
    catalog_path: Optional[str] = Field(None, description="Path to current catalog")
    timestamp: Optional[str] = Field(
        None, description="Plugin-sent ISO-8601 timestamp (optional)")


def _get_expected_token() -> Optional[str]:
    return os.getenv("LRC_MCP_PLUGIN_TOKEN") or None


async def _require_token(x_plugin_token: Optional[str] = Header(default=None)) -> None:
    expected = _get_expected_token()
    if expected is None:
        # Dev mode: accept without token
        return
    if not x_plugin_token or x_plugin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid plugin token")


def create_app() -> FastAPI:
    app = FastAPI(title="lrc-mcp plugin bridge", docs_url=None, redoc_url=None)

    @app.post("/plugin/heartbeat")
    async def plugin_heartbeat(
        request: Request,
        payload: HeartbeatPayload,
        _: None = Depends(_require_token),
    ) -> Dict[str, Any]:
        store = get_store()
        hb = store.set_heartbeat(
            plugin_version=payload.plugin_version,
            lr_version=payload.lr_version,
            catalog_path=payload.catalog_path,
            sent_at_iso=payload.timestamp,
        )
        logger.info(
            "heartbeat accepted",
            extra={
                "remote": getattr(request.client, "host", None),
                "lr_version": hb.lr_version,
            },
        )
        return {"status": "ok"}

    return app


