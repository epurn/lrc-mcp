import json
import pytest

from lrc_mcp import resources as lrc_resources
from lrc_mcp.services.lrc_bridge import get_store


@pytest.fixture(autouse=True)
def clear_heartbeat():
    # Ensure no heartbeat so resources treat Lightroom as not running
    store = get_store()
    try:
        store._last_heartbeat = None
    except Exception:
        pass
    yield


@pytest.mark.asyncio
async def test_status_lightroom_integration_shape_when_not_running():
    out = await lrc_resources.read_resource("lrc://status/lightroom")
    payload = json.loads(out)
    # Validate expected keys exist
    for key in [
        "running",
        "plugin_connected",
        "last_seen_age_s",
        "catalog_path",
        "lightroom_version",
        "plugin_version",
    ]:
        assert key in payload
    # Types for core booleans
    assert isinstance(payload["running"], bool)
    assert isinstance(payload["plugin_connected"], bool)


@pytest.mark.asyncio
async def test_collections_snapshot_integration_when_not_running():
    out = await lrc_resources.read_resource("lrc://catalog/collections")
    payload = json.loads(out)
    # When LR is not running or plugin disconnected, we expect an error marker
    assert isinstance(payload, dict)
    # Either immediate error when LR not running, or pending if prior heartbeat exists without plugin result
    if "error" in payload:
        assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()
    else:
        assert payload.get("status") == "pending"


@pytest.mark.asyncio
async def test_single_collection_integration_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection/some-id")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    if "error" in payload:
        assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()
    else:
        assert payload.get("status") == "pending"


@pytest.mark.asyncio
async def test_single_collection_set_integration_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection_set/some-id")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    if "error" in payload:
        assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()
    else:
        assert payload.get("status") == "pending"


@pytest.mark.asyncio
async def test_collection_by_path_integration_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection/by-path/Some%20Path")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    if "error" in payload:
        assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()
    else:
        assert payload.get("status") == "pending"


@pytest.mark.asyncio
async def test_collection_set_by_path_integration_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection_set/by-path/Set%2FChild")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    if "error" in payload:
        assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()
    else:
        assert payload.get("status") == "pending"
