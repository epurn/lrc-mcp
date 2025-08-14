"""Unit tests for lrc_mcp.utils module."""

import json
import pytest

from lrc_mcp.utils import parse_json_body


class TestParseJsonBody:
    """Tests for parse_json_body function."""

    def test_parse_json_object(self):
        """Test parsing a proper JSON object."""
        data = {"key": "value", "number": 42}
        raw_bytes = json.dumps(data).encode("utf-8")
        result = parse_json_body(raw_bytes)
        assert result == data

    def test_parse_json_string(self):
        """Test parsing a JSON string (double-encoded)."""
        inner_data = {"key": "value"}
        json_string = json.dumps(inner_data)
        raw_bytes = json_string.encode("utf-8")
        result = parse_json_body(raw_bytes)
        assert result == inner_data

    def test_parse_empty_bytes(self):
        """Test parsing empty bytes."""
        raw_bytes = b""
        result = parse_json_body(raw_bytes)
        assert result == {}

    def test_invalid_json(self):
        """Test parsing invalid JSON."""
        raw_bytes = b"invalid json"
        with pytest.raises(ValueError, match="invalid payload"):
            parse_json_body(raw_bytes)

    def test_invalid_json_string(self):
        """Test parsing invalid JSON string."""
        json_string = "invalid json string"
        raw_bytes = json_string.encode("utf-8")
        with pytest.raises(ValueError, match="invalid payload"):
            parse_json_body(raw_bytes)
