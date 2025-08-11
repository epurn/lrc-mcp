"""Pydantic schemas for plugin HTTP API payloads."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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
