"""Unit tests for lrc_mcp.adapters.collections module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from lrc_mcp.adapters.collections import (
    _is_lightroom_running,
    _check_lightroom_dependency,
    get_collection_tool,
    get_collection_set_tool,
    handle_collection_tool,
    handle_collection_set_tool,
)
from lrc_mcp.services.lrc_bridge import Heartbeat


class TestCollectionsAdapter:
    """Tests for collections adapter functions."""

    @patch('lrc_mcp.adapters.collections.get_store')
    def test_is_lightroom_running_no_heartbeat(self, mock_get_store):
        """Test _is_lightroom_running when no heartbeat exists."""
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = None
        mock_get_store.return_value = mock_store
        
        result = _is_lightroom_running()
        assert result is False

    @patch('lrc_mcp.adapters.collections.get_store')
    def test_is_lightroom_running_old_heartbeat(self, mock_get_store):
        """Test _is_lightroom_running when heartbeat is too old."""
        from datetime import datetime, timezone, timedelta
        old_time = datetime.now(timezone.utc) - timedelta(seconds=60)  # 60 seconds ago
        
        mock_heartbeat = Heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            received_at=old_time,
            sent_at=None
        )
        
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = mock_heartbeat
        mock_get_store.return_value = mock_store
        
        result = _is_lightroom_running()
        assert result is False

    @patch('lrc_mcp.adapters.collections.get_store')
    def test_is_lightroom_running_recent_heartbeat(self, mock_get_store):
        """Test _is_lightroom_running when heartbeat is recent."""
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=10)  # 10 seconds ago
        
        mock_heartbeat = Heartbeat(
            plugin_version="1.0.0",
            lr_version="13.2",
            catalog_path="/path/to/catalog",
            received_at=recent_time,
            sent_at=None
        )
        
        mock_store = MagicMock()
        mock_store.get_last_heartbeat.return_value = mock_heartbeat
        mock_get_store.return_value = mock_store
        
        result = _is_lightroom_running()
        assert result is True

    @patch('lrc_mcp.adapters.collections._is_lightroom_running')
    def test_check_lightroom_dependency_not_running(self, mock_is_running):
        """Test _check_lightroom_dependency when Lightroom is not running."""
        mock_is_running.return_value = False
        
        result = _check_lightroom_dependency()
        assert result is not None
        assert result["status"] == "error"
        assert "Lightroom Classic is not running" in result["error"]
        assert result["command_id"] is None

    @patch('lrc_mcp.adapters.collections._is_lightroom_running')
    def test_check_lightroom_dependency_running(self, mock_is_running):
        """Test _check_lightroom_dependency when Lightroom is running."""
        mock_is_running.return_value = True
        
        result = _check_lightroom_dependency()
        assert result is None


    def test_get_collection_tool(self):
        """Test getting the unified collection tool definition."""
        tool = get_collection_tool()
        assert tool.name == "lrc_collection"
        assert tool.description is not None
        assert tool.description.strip().startswith("Does ")
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "function" in tool.inputSchema["properties"]
        assert "args" in tool.inputSchema["properties"]
        assert "status" in tool.outputSchema["properties"]
        assert "result" in tool.outputSchema["properties"]

    def test_get_collection_set_tool(self):
        """Test getting the unified collection set tool definition."""
        tool = get_collection_set_tool()
        assert tool.name == "lrc_collection_set"
        assert tool.description is not None
        assert tool.description.strip().startswith("Does ")
        assert tool.inputSchema is not None
        assert tool.outputSchema is not None
        assert "function" in tool.inputSchema["properties"]
        assert "args" in tool.inputSchema["properties"]
        assert "status" in tool.outputSchema["properties"]
        assert "result" in tool.outputSchema["properties"]

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_alias_remove(self, mock_get_queue, mock_check):
        """Test handle_collection_tool with deprecated 'remove' alias mapping to delete by id."""
        mock_check.return_value = None  # No dependency error

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-1"
        mock_queue.wait_for_result.return_value = MagicMock(ok=True, result={"removed": True})
        mock_get_queue.return_value = mock_queue

        args = {"function": "remove", "args": {"id": "123"}}
        result = handle_collection_tool(args)

        assert result["status"] == "ok"
        assert result["command_id"] == "cmd-1"
        assert "deprecation" in result and result["deprecation"] is not None
        mock_queue.enqueue.assert_called_once()
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection.remove"
        assert enq_kwargs["payload"]["id"] == "123"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_list_success(self, mock_get_queue, mock_check):
        """Test handle_collection_tool list function with filters using unified args."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-2"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"collections": [{"id": "1", "name": "Foo", "set_id": None, "smart": False, "photo_count": 0, "path": "Foo"}]}
        )
        mock_get_queue.return_value = mock_queue

        # Test legacy args (set_id)
        args = {"function": "list", "args": {"set_id": "abc", "name_contains": "Foo"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        mock_queue.enqueue.assert_called_once()
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection.list"
        assert enq_kwargs["payload"]["set_id"] == "abc"
        assert enq_kwargs["payload"]["name_contains"] == "Foo"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_list_with_parent_id(self, mock_get_queue, mock_check):
        """Test handle_collection_tool list function with parent_id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-2b"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"collections": [{"id": "1", "name": "Foo", "set_id": "abc", "smart": False, "photo_count": 0, "path": "Sets/Foo"}]}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (parent_id)
        args = {"function": "list", "args": {"parent_id": "abc", "name_contains": "Foo"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["set_id"] == "abc"  # Mapped from parent_id

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_create_success(self, mock_get_queue, mock_check):
        """Test handle_collection_tool create function with unified args."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-3"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"created": True, "collection": {"id": "9", "name": "New", "path": "New"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (parent_path)
        args = {"function": "create", "args": {"name": "New", "parent_path": "Sets/A"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        assert result["result"]["created"] is True
        mock_queue.enqueue.assert_called_once()
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection.create"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_create_with_parent_id(self, mock_get_queue, mock_check):
        """Test handle_collection_tool create function with parent_id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-3b"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"created": True, "collection": {"id": "10", "name": "New2", "path": "Sets/New2"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (parent_id)
        args = {"function": "create", "args": {"name": "New2", "parent_id": "set-123"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["parent_id"] == "set-123"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_edit_success(self, mock_get_queue, mock_check):
        """Test handle_collection_tool edit function with unified args."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-4"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"updated": True, "collection": {"id": "9", "name": "Renamed", "path": "Renamed"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test legacy args (collection_path)
        args = {"function": "edit", "args": {"collection_path": "Old", "new_name": "Renamed"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        assert result["result"]["updated"] is True
        mock_queue.enqueue.assert_called_once()
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection.edit"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_edit_with_id(self, mock_get_queue, mock_check):
        """Test handle_collection_tool edit function with id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-4b"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"updated": True, "collection": {"id": "9", "name": "Renamed2", "path": "Renamed2"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (id takes precedence)
        args = {"function": "edit", "args": {"id": "coll-123", "collection_path": "Old", "new_name": "Renamed2"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["id"] == "coll-123"  # id takes precedence

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_edit_with_new_parent_id(self, mock_get_queue, mock_check):
        """Test handle_collection_tool edit function with new_parent_id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-4c"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"updated": True, "collection": {"id": "9", "name": "Moved", "path": "NewSet/Moved"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (new_parent_id)
        args = {"function": "edit", "args": {"id": "coll-123", "new_parent_id": "set-456"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["new_parent_id"] == "set-456"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    def test_handle_collection_tool_delete_requires_id_or_path(self, mock_check):
        """Test handle_collection_tool delete requires id or path."""
        mock_check.return_value = None  # No dependency error
        
        # No dependency check needed; validation fails before queue usage
        result = handle_collection_tool({"function": "delete", "args": {}})
        assert result["status"] == "error"
        assert "Either 'id' or 'path' is required for delete" in result["error"]

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_delete_with_id(self, mock_get_queue, mock_check):
        """Test handle_collection_tool delete function with id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-5"
        mock_queue.wait_for_result.return_value = MagicMock(ok=True, result={"removed": True})
        mock_get_queue.return_value = mock_queue

        args = {"function": "delete", "args": {"id": "coll-123"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection.remove"
        assert enq_kwargs["payload"]["id"] == "coll-123"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_tool_delete_with_path(self, mock_get_queue, mock_check):
        """Test handle_collection_tool delete function with path."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-5b"
        mock_queue.wait_for_result.return_value = MagicMock(ok=True, result={"removed": True})
        mock_get_queue.return_value = mock_queue

        args = {"function": "delete", "args": {"path": "Sets/ToDelete"}}
        result = handle_collection_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["path"] == "Sets/ToDelete"  # Path gets resolved by plugin

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_list_success(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool list function with unified args."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-6"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"collection_sets": [{"id": "1", "name": "Sets", "path": "Sets"}]}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args
        args = {"function": "list", "args": {"parent_path": "Root", "name_contains": "Sets"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection_set.list"
        assert enq_kwargs["payload"]["parent_path"] == "Root"
        assert enq_kwargs["payload"]["name_contains"] == "Sets"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_list_with_parent_id(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool list function with parent_id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-6b"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"collection_sets": [{"id": "2", "name": "Child", "path": "Parent/Child"}]}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (parent_id)
        args = {"function": "list", "args": {"parent_id": "parent-123", "name_contains": "Child"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["parent_id"] == "parent-123"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_create_success(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool create function with unified args."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-7"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"created": True, "collection_set": {"id": "3", "name": "NewSet", "path": "NewSet"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args
        args = {"function": "create", "args": {"name": "NewSet", "parent_path": "Parent"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection_set.create"
        assert enq_kwargs["payload"]["name"] == "NewSet"
        assert enq_kwargs["payload"]["parent_path"] == "Parent"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_create_with_parent_id(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool create function with parent_id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-7b"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"created": True, "collection_set": {"id": "4", "name": "NewSet2", "path": "Parent/NewSet2"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (parent_id)
        args = {"function": "create", "args": {"name": "NewSet2", "parent_id": "parent-123"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["parent_id"] == "parent-123"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_edit_success(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool edit function with unified args."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-8"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"updated": True, "collection_set": {"id": "5", "name": "RenamedSet", "path": "RenamedSet"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test legacy args (collection_set_path)
        args = {"function": "edit", "args": {"collection_set_path": "OldSet", "new_name": "RenamedSet"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection_set.edit"
        assert enq_kwargs["payload"]["path"] == "OldSet"  # Mapped from collection_set_path

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_edit_with_id(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool edit function with id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-8b"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"updated": True, "collection_set": {"id": "6", "name": "RenamedSet2", "path": "Sets/RenamedSet2"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (id takes precedence)
        args = {"function": "edit", "args": {"id": "set-123", "collection_set_path": "OldSet", "new_name": "RenamedSet2"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["id"] == "set-123"  # id takes precedence

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_edit_with_new_parent_id(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool edit function with new_parent_id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-8c"
        mock_queue.wait_for_result.return_value = MagicMock(
            ok=True,
            result={"updated": True, "collection_set": {"id": "7", "name": "MovedSet", "path": "NewParent/MovedSet"}}
        )
        mock_get_queue.return_value = mock_queue

        # Test unified args (new_parent_id)
        args = {"function": "edit", "args": {"id": "set-123", "new_parent_id": "newparent-456"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["new_parent_id"] == "newparent-456"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    def test_handle_collection_set_tool_delete_requires_id_or_path(self, mock_check):
        """Test handle_collection_set_tool delete requires id or path."""
        mock_check.return_value = None  # No dependency error
        
        # No dependency check needed; validation fails before queue usage
        result = handle_collection_set_tool({"function": "delete", "args": {}})
        assert result["status"] == "error"
        assert "Either 'id' or 'path' is required for delete" in result["error"]

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_delete_with_id(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool delete function with id."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-9"
        mock_queue.wait_for_result.return_value = MagicMock(ok=True, result={"removed": True})
        mock_get_queue.return_value = mock_queue

        args = {"function": "delete", "args": {"id": "set-123"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["type"] == "collection_set.remove"
        assert enq_kwargs["payload"]["id"] == "set-123"

    @patch('lrc_mcp.adapters.collections._check_lightroom_dependency')
    @patch('lrc_mcp.adapters.collections.get_queue')
    def test_handle_collection_set_tool_delete_with_path(self, mock_get_queue, mock_check):
        """Test handle_collection_set_tool delete function with path."""
        mock_check.return_value = None

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = "cmd-9b"
        mock_queue.wait_for_result.return_value = MagicMock(ok=True, result={"removed": True})
        mock_get_queue.return_value = mock_queue

        args = {"function": "delete", "args": {"path": "Sets/ToDelete"}}
        result = handle_collection_set_tool(args)
        assert result["status"] == "ok"
        enq_kwargs = mock_queue.enqueue.call_args.kwargs
        assert enq_kwargs["payload"]["path"] == "Sets/ToDelete"
