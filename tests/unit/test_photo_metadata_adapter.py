"""Unit tests for lrc_mcp.adapters.photo_metadata module (E9-S1)."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from lrc_mcp.adapters.photo_metadata import (
    get_photo_metadata_tool,
    handle_photo_metadata_tool,
)


class TestPhotoMetadataAdapter:
    """Tests for photo metadata adapter functions (read-only)."""

    def test_get_photo_metadata_tool_definition(self):
        """Tool definition should be deterministic and verb-led."""
        tool = get_photo_metadata_tool()
        assert tool.name == "lrc_photo_metadata"
        assert tool.description is not None and tool.description.strip().startswith("Does ")
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "function" in tool.inputSchema["properties"]
        assert "args" in tool.inputSchema["properties"]
        assert "status" in tool.outputSchema["properties"]
        assert "result" in tool.outputSchema["properties"]

    def test_handle_tool_requires_arguments(self):
        """Call must include arguments object."""
        result = handle_photo_metadata_tool(None)
        assert result["status"] == "error"
        assert "No arguments" in result["error"]

    def test_handle_tool_invalid_function(self):
        """Function must be get or bulk_get."""
        result = handle_photo_metadata_tool({"function": "unknown", "args": {}})
        assert result["status"] == "error"
        assert "Invalid function" in result["error"]

    def test_get_requires_photo_identifier(self):
        """photo.local_id or photo.file_path is required for get."""
        # Missing photo
        result = handle_photo_metadata_tool({"function": "get", "args": {}})
        assert result["status"] == "error"
        assert "photo must be an object" in result["error"]

        # Missing identifiers
        result2 = handle_photo_metadata_tool({"function": "get", "args": {"photo": {}}})
        assert result2["status"] == "error"
        assert "photo.local_id or photo.file_path is required" in result2["error"]

    def test_get_rejects_unknown_fields(self):
        """Unknown fields should be rejected strictly."""
        result = handle_photo_metadata_tool(
            {
                "function": "get",
                "args": {"photo": {"local_id": "1"}, "fields": ["title", "bogus_field"]},
            }
        )
        assert result["status"] == "error"
        assert "Unknown field(s)" in result["error"]

    def test_bulk_get_requires_photos(self):
        """bulk_get requires non-empty photos array and identifiers per item."""
        # Missing photos
        result = handle_photo_metadata_tool({"function": "bulk_get", "args": {}})
        assert result["status"] == "error"
        assert "photos must be a non-empty array" in result["error"]

        # Invalid item
        result2 = handle_photo_metadata_tool(
            {"function": "bulk_get", "args": {"photos": [{}]}}
        )
        assert result2["status"] == "error"
        assert "photos[0].local_id or photos[0].file_path is required" in result2["error"]

    @patch("lrc_mcp.adapters.photo_metadata._check_lightroom_dependency")
    def test_dependency_error_is_returned(self, mock_dep):
        """Dependency check failure should surface error."""
        mock_dep.return_value = {
            "status": "error",
            "error": "Lightroom Classic is not running or plugin is not connected.",
        }
        result = handle_photo_metadata_tool(
            {"function": "get", "args": {"photo": {"local_id": "123"}, "fields": ["title"]}}
        )
        assert result["status"] == "error"
        assert "Lightroom Classic is not running" in result["error"]

    @patch("lrc_mcp.adapters.photo_metadata.get_queue")
    @patch("lrc_mcp.adapters.photo_metadata._check_lightroom_dependency")
    def test_get_enqueues_and_waits(self, mock_dep, mock_get_queue):
        """get should enqueue photo_metadata.get and wait for result by default."""
        mock_dep.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-a"
        # Simulate plugin returning a normalized result shape
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={
                "photo": {"local_id": "1", "file_path": None},
                "result": {"title": "Hello"},
                "error": None,
            },
        )
        mock_get_queue.return_value = mock_queue

        args = {"function": "get", "args": {"photo": {"local_id": "1"}, "fields": ["title"]}}
        result = handle_photo_metadata_tool(args)

        assert result["status"] == "ok"
        assert result["command_id"] == "cmd-a"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "photo_metadata.get"
        assert enq_kwargs["payload"]["photo"]["local_id"] == "1"
        assert enq_kwargs["payload"]["fields"] == ["title"]

    @patch("lrc_mcp.adapters.photo_metadata.get_queue")
    @patch("lrc_mcp.adapters.photo_metadata._check_lightroom_dependency")
    def test_bulk_get_enqueues_and_waits(self, mock_dep, mock_get_queue):
        """bulk_get should enqueue photo_metadata.bulk_get and wait for result."""
        mock_dep.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-b"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={
                "items": [
                    {
                        "photo": {"local_id": "1", "file_path": None},
                        "result": {"rating": 5},
                        "error": None,
                    },
                    {
                        "photo": {"local_id": None, "file_path": "/a.jpg"},
                        "result": None,
                        "error": {"code": "PHOTO_NOT_FOUND", "message": "Photo not found"},
                    },
                ],
                "errors_aggregated": [{"index": 2, "code": "PHOTO_NOT_FOUND", "message": "Photo not found"}],
                "stats": {"requested": 2, "succeeded": 1, "failed": 1, "duration_ms": 10},
            },
        )
        mock_get_queue.return_value = mock_queue

        args = {
            "function": "bulk_get",
            "args": {
                "photos": [{"local_id": "1"}, {"file_path": "/a.jpg"}],
                "fields": ["rating"],
            },
        }
        result = handle_photo_metadata_tool(args)

        assert result["status"] == "ok"
        assert result["command_id"] == "cmd-b"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "photo_metadata.bulk_get"
        assert enq_kwargs["payload"]["photos"][0]["local_id"] == "1"
        assert enq_kwargs["payload"]["photos"][1]["file_path"] == "/a.jpg"
        assert enq_kwargs["payload"]["fields"] == ["rating"]
