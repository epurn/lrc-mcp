import json
from datetime import datetime
from pathlib import Path

import pytest

from lrc_mcp.resources import read_resource


def _repo_root() -> Path:
    # tests/integration/test_resources.py -> tests -> repo root
    return Path(__file__).resolve().parents[2]


def _log_path() -> Path:
    return _repo_root() / "plugin" / "lrc-mcp.lrplugin" / "logs" / "lrc_mcp.log"


def _ensure_logs_dir() -> None:
    _log_path().parent.mkdir(parents=True, exist_ok=True)


def _is_iso8601_z(s: str) -> bool:
    try:
        # Expect format like 2024-01-01T00:00:00Z
        datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_plugin_logs_enriched_output():
    _ensure_logs_dir()
    content = "Test log line αβγ\nSecond line\n"
    lp = _log_path()
    lp.write_text(content, encoding="utf-8")

    result = await read_resource("lrc://logs/plugin")
    payload = json.loads(result)

    expected_size = lp.stat().st_size

    assert isinstance(payload, dict)
    assert payload["contentType"] == "text/plain"
    assert payload["size"] == expected_size
    # When the file exists, lastModified should be a Z-terminated ISO8601 string
    assert isinstance(payload.get("lastModified"), str)
    assert payload["lastModified"].endswith("Z")
    assert _is_iso8601_z(payload["lastModified"])

    assert isinstance(payload["data"], str)
    assert payload["data"] == content


@pytest.mark.asyncio
async def test_plugin_logs_missing_and_empty():
    _ensure_logs_dir()
    lp = _log_path()
    if lp.exists():
        lp.unlink()

    # Missing file case
    result_missing = await read_resource("lrc://logs/plugin")
    payload_missing = json.loads(result_missing)

    assert payload_missing["contentType"] == "text/plain"
    assert payload_missing["size"] == 0
    assert "data" in payload_missing
    assert payload_missing["data"] == ""
    # For missing file, lastModified may be null
    assert "lastModified" in payload_missing
    assert payload_missing["lastModified"] is None

    # Empty file case
    lp.write_text("", encoding="utf-8")
    result_empty = await read_resource("lrc://logs/plugin")
    payload_empty = json.loads(result_empty)

    assert payload_empty["contentType"] == "text/plain"
    assert payload_empty["size"] == 0
    assert payload_empty["data"] == ""
    # For existing (even empty) file, lastModified should be ISO8601 Z string
    assert isinstance(payload_empty.get("lastModified"), str)
    assert payload_empty["lastModified"].endswith("Z")
    assert _is_iso8601_z(payload_empty["lastModified"])
