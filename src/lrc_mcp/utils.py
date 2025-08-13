"""Common utility functions for the lrc-mcp project."""

from __future__ import annotations

import json
from typing import Any


def parse_json_body(raw_bytes: bytes) -> Any:
    """Parse JSON body, handling both proper JSON objects and JSON strings.
    
    Args:
        raw_bytes: Raw bytes from HTTP request body
        
    Returns:
        Parsed JSON object
        
    Raises:
        ValueError: If JSON parsing fails
    """
    try:
        parsed: Any = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else {}
        if isinstance(parsed, str):
            # Handle double-encoded JSON
            parsed = json.loads(parsed)
        return parsed
    except Exception as exc:
        raise ValueError(f"invalid payload: {exc}")
