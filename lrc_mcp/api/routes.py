"""Plugin HTTP API routes for the LrC bridge.

Endpoints:
- POST /plugin/heartbeat          (Step 3)
- POST /plugin/commands/enqueue   (Step 4)
- POST /plugin/commands/claim     (Step 4)
- POST /plugin/commands/{id}/result (Step 4)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from ..models import (
    HeartbeatPayload,
    EnqueuePayload,
    ClaimPayload,
    ResultPayload,
)
from ..services.lrc_bridge import get_store, get_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugin", tags=["plugin"])


def _get_expected_token() -> Optional[str]:
    import os
    return os.getenv("LRC_MCP_PLUGIN_TOKEN") or None


async def _require_token(x_plugin_token: Optional[str] = Header(default=None)) -> None:
    expected = _get_expected_token()
    if expected is None:
        # Dev mode: accept without token
        return
    if not x_plugin_token or x_plugin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid plugin token")


def _parse_json_body(raw_bytes: bytes) -> Any:
    """Parse JSON body, handling both proper JSON objects and JSON strings."""
    from ..utils import parse_json_body
    try:
        return parse_json_body(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/heartbeat")
async def plugin_heartbeat(
    request: Request,
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Handle plugin heartbeat beacons."""
    raw_bytes = await request.body()
    parsed = _parse_json_body(raw_bytes)
    payload = HeartbeatPayload.model_validate(parsed)

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


@router.post("/commands/enqueue")
async def enqueue_command(
    request: Request,
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Enqueue a command from the server side."""
    raw_bytes = await request.body()
    parsed = _parse_json_body(raw_bytes)
    body = EnqueuePayload.model_validate(parsed)
    
    q = get_queue()
    cmd_id = q.enqueue(type=body.type, payload=body.payload, idempotency_key=body.idempotency_key)
    logger.info("command queued", extra={"command_id": cmd_id, "type": body.type})
    return {"status": "queued", "command_id": cmd_id}


@router.post("/commands/claim")
async def claim_commands(
    request: Request,
    _: None = Depends(_require_token),
) -> Any:
    """Allow plugin to claim pending commands."""
    raw_bytes = await request.body()
    parsed = _parse_json_body(raw_bytes)
    body = ClaimPayload.model_validate(parsed)
    
    q = get_queue()
    cmds = q.claim(worker=body.worker, max_items=body.max)
    if not cmds:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    # Return list of commands (id, type, payload)
    return {"commands": [
        {"id": c.id, "type": c.type, "payload": c.payload} for c in cmds
    ]}


@router.post("/commands/{command_id}/result")
async def post_result(
    command_id: str,
    request: Request,
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Receive command results from the plugin."""
    raw_bytes = await request.body()
    parsed = _parse_json_body(raw_bytes)
    body = ResultPayload.model_validate(parsed)
    
    q = get_queue()
    q.complete(command_id=command_id, ok=body.ok, result=body.result, error=body.error)
    logger.info("command completed", extra={"command_id": command_id, "ok": body.ok})
    return {"status": "ok"}
