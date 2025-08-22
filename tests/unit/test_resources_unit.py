import json
import pytest

from lrc_mcp import resources as lrc_resources


def _as_set(items):
    return set(items)


def _resource_uris(resources):
    return {str(r.uri) for r in resources}


def _resource_template_uris(templates):
    # ResourceTemplate uses uriTemplate in our code
    return {t.uriTemplate for t in templates}


def test_list_resources_contains_expected_uris():
    res = lrc_resources.list_resources()
    assert isinstance(res, list)
    uris = _resource_uris(res)
    expected = {
        "lrc://logs/plugin",
        "lrc://status/lightroom",
        "lrc://catalog/collections",
    }
    # Must contain at least the three core resources
    assert expected.issubset(uris)


def test_list_resource_templates_contains_expected_templates():
    tpls = lrc_resources.list_resource_templates()
    assert isinstance(tpls, list)
    uris = _resource_template_uris(tpls)
    expected = {
        "lrc://collection/{id}",
        "lrc://collection_set/{id}",
        "lrc://collection/by-path/{path}",
        "lrc://collection_set/by-path/{path}",
    }
    assert expected.issubset(uris)


@pytest.mark.asyncio
async def test_read_resource_unsupported_returns_message():
    uri = "lrc://unknown/thing"
    out = await lrc_resources.read_resource(uri)
    assert isinstance(out, str)
    assert out == f"Unsupported resource: {uri}"


@pytest.mark.asyncio
async def test_status_lightroom_json_shape_when_not_running():
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
async def test_collections_snapshot_when_not_running():
    out = await lrc_resources.read_resource("lrc://catalog/collections")
    payload = json.loads(out)
    # When LR is not running or plugin disconnected, we expect an error marker
    assert isinstance(payload, dict)
    assert "error" in payload
    assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()


@pytest.mark.asyncio
async def test_single_collection_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection/some-id")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    assert "error" in payload
    assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()


@pytest.mark.asyncio
async def test_single_collection_set_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection_set/some-id")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    assert "error" in payload
    assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()


@pytest.mark.asyncio
async def test_collection_by_path_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection/by-path/Some%20Path")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    assert "error" in payload
    assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()


@pytest.mark.asyncio
async def test_collection_set_by_path_when_not_running():
    out = await lrc_resources.read_resource("lrc://collection_set/by-path/Set%2FChild")
    payload = json.loads(out)
    assert isinstance(payload, dict)
    assert "error" in payload
    assert "not running" in payload["error"].lower() or "not connected" in payload["error"].lower()
