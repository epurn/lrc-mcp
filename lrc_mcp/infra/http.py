"""Local FastAPI app exposing plugin endpoints for the LrC bridge.

Endpoints:
- POST /plugin/heartbeat          (Step 3)
- POST /plugin/commands/enqueue   (Step 4)
- POST /plugin/commands/claim     (Step 4)
- POST /plugin/commands/{id}/result (Step 4)

This app binds to localhost only via the uvicorn server in main.py.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
import json

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..services.lrc_bridge import get_store, get_queue

logger = logging.getLogger(__name__)


class HeartbeatPayload(BaseModel):
    plugin_version: str = Field(..., description="Version of the LrC plugin")
    lr_version: str = Field(..., description="Detected Lightroom Classic version")
    catalog_path: Optional[str] = Field(None, description="Path to current catalog")
    timestamp: Optional[str] = Field(
        None, description="Plugin-sent ISO-8601 timestamp (optional)")


class EnqueuePayload(BaseModel):
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class ClaimPayload(BaseModel):
    worker: str = Field(..., pattern="^[A-Za-z0-9_.-]+$")
    max: int = Field(1, ge=1, le=10)


class ResultPayload(BaseModel):
    ok: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


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
        _: None = Depends(_require_token),
    ) -> Dict[str, Any]:
        # Accept both proper JSON objects and a JSON string containing an object (some LrC environments double-encode)
        raw_bytes = await request.body()
        try:
            parsed: Any = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else {}
            if isinstance(parsed, str):
                # Handle double-encoded JSON
                parsed = json.loads(parsed)
            payload = HeartbeatPayload.model_validate(parsed)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid payload: {exc}")

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

    @app.post("/plugin/commands/enqueue")
    async def enqueue_command(
        request: Request,
        _: None = Depends(_require_token),
    ) -> Dict[str, Any]:
        # Accept both proper JSON objects and a JSON string containing an object (some LrC environments double-encode)
        raw_bytes = await request.body()
        try:
            parsed: Any = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else {}
            if isinstance(parsed, str):
                # Handle double-encoded JSON
                parsed = json.loads(parsed)
            body = EnqueuePayload.model_validate(parsed)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid payload: {exc}")
        
        q = get_queue()
        cmd_id = q.enqueue(type=body.type, payload=body.payload, idempotency_key=body.idempotency_key)
        logger.info("command queued", extra={"command_id": cmd_id, "type": body.type})
        return {"status": "queued", "command_id": cmd_id}

    @app.post("/plugin/commands/claim")
    async def claim_commands(
        request: Request,
        _: None = Depends(_require_token),
    ) -> Any:
        # Accept both proper JSON objects and a JSON string containing an object (some LrC environments double-encode)
        raw_bytes = await request.body()
        try:
            parsed: Any = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else {}
            if isinstance(parsed, str):
                # Handle double-encoded JSON
                parsed = json.loads(parsed)
            body = ClaimPayload.model_validate(parsed)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid payload: {exc}")
        
        q = get_queue()
        cmds = q.claim(worker=body.worker, max_items=body.max)
        if not cmds:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        # Return list of commands (id, type, payload)
        return {"commands": [
            {"id": c.id, "type": c.type, "payload": c.payload} for c in cmds
        ]}

    @app.post("/plugin/commands/{command_id}/result")
    async def post_result(
        command_id: str,
        request: Request,
        _: None = Depends(_require_token),
    ) -> Dict[str, Any]:
        # Accept both proper JSON objects and a JSON string containing an object (some LrC environments double-encode)
        raw_bytes = await request.body()
        try:
            parsed: Any = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else {}
            if isinstance(parsed, str):
                # Handle double-encoded JSON
                parsed = json.loads(parsed)
            body = ResultPayload.model_validate(parsed)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid payload: {exc}")
        
        q = get_queue()
        q.complete(command_id=command_id, ok=body.ok, result=body.result, error=body.error)
        logger.info("command completed", extra={"command_id": command_id, "ok": body.ok})
        return {"status": "ok"}

    return app
