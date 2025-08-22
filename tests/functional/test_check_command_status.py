import uuid

import pytest

from lrc_mcp.adapters.lightroom import (
    get_check_command_status_tool,
    handle_check_command_status_tool,
)
from lrc_mcp.services.lrc_bridge import get_queue


def test_tool_definition_exists():
    tool = get_check_command_status_tool()
    assert tool.name == "check_command_status"
    assert tool.inputSchema is not None
    assert tool.outputSchema is not None


def test_status_pending_for_unknown_command():
    unknown_id = str(uuid.uuid4())
    out = handle_check_command_status_tool({"command_id": unknown_id})
    assert isinstance(out, dict)
    assert out["status"] == "pending"
    assert out["result"] is None
    assert out["error"] is None


def test_status_completed_success():
    queue = get_queue()
    # Enqueue any command to get an id we can complete
    cmd_id = queue.enqueue(type="echo", payload={"hello": "world"})
    # Complete with success
    queue.complete(command_id=cmd_id, ok=True, result={"ok": True, "data": 123})
    out = handle_check_command_status_tool({"command_id": cmd_id})
    assert out["status"] == "completed"
    assert out["error"] is None
    assert out["result"] == {"ok": True, "data": 123}


def test_status_failed_error():
    queue = get_queue()
    cmd_id = queue.enqueue(type="noop", payload={})
    # Complete with failure
    queue.complete(command_id=cmd_id, ok=False, error="Something went wrong")
    out = handle_check_command_status_tool({"command_id": cmd_id})
    assert out["status"] == "failed"
    assert out["result"] is None
    assert out["error"] == "Something went wrong"
