"""Unit tests for lrc_mcp.adapters.lightroom module."""

import pytest
import os
from unittest.mock import patch, MagicMock, mock_open

from lrc_mcp.adapters.lightroom import (
    _query_tasklist_lightroom,
    _parse_first_pid_from_tasklist,
    _is_lightroom_running,
    _launch_via_external_launcher,
    resolve_lightroom_path,
    launch_lightroom,
    LaunchResult,
)


class TestLightroomAdapter:
    """Tests for lightroom adapter functions."""

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.subprocess.run')
    def test_query_tasklist_lightroom_windows(self, mock_subprocess):
        """Test _query_tasklist_lightroom on Windows."""
        mock_result = MagicMock()
        mock_result.stdout = "Lightroom.exe 1234 Console 123456 Running"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        result = _query_tasklist_lightroom()
        assert "Lightroom.exe" in result
        mock_subprocess.assert_called_once()

    @patch('lrc_mcp.adapters.lightroom.os.name', 'posix')
    def test_query_tasklist_lightroom_non_windows(self):
        """Test _query_tasklist_lightroom on non-Windows."""
        result = _query_tasklist_lightroom()
        assert result == ""

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.subprocess.run')
    def test_query_tasklist_lightroom_exception(self, mock_subprocess):
        """Test _query_tasklist_lightroom when subprocess fails."""
        mock_subprocess.side_effect = Exception("Subprocess failed")
        
        result = _query_tasklist_lightroom()
        assert result == ""

    def test_parse_first_pid_from_tasklist_valid(self):
        """Test _parse_first_pid_from_tasklist with valid output."""
        output = "Lightroom.exe 1234 Console 123456 Running"
        pid = _parse_first_pid_from_tasklist(output)
        assert pid == 1234

    def test_parse_first_pid_from_tasklist_multiple_lines(self):
        """Test _parse_first_pid_from_tasklist with multiple lines."""
        output = "Background Task 5678\nLightroom.exe 1234 Console 123456 Running\nAnother Process 9999"
        pid = _parse_first_pid_from_tasklist(output)
        assert pid == 1234

    def test_parse_first_pid_from_tasklist_invalid_format(self):
        """Test _parse_first_pid_from_tasklist with invalid format."""
        output = "Lightroom.exe not_a_number Console"
        pid = _parse_first_pid_from_tasklist(output)
        assert pid is None

    def test_parse_first_pid_from_tasklist_no_lightroom(self):
        """Test _parse_first_pid_from_tasklist when Lightroom is not found."""
        output = "OtherProcess.exe 1234 Console"
        pid = _parse_first_pid_from_tasklist(output)
        assert pid is None

    @patch('lrc_mcp.adapters.lightroom._query_tasklist_lightroom')
    def test_is_lightroom_running_found(self, mock_query):
        """Test _is_lightroom_running when Lightroom is found."""
        mock_query.return_value = "Lightroom.exe 1234 Console"
        is_running, pid = _is_lightroom_running()
        assert is_running is True
        assert pid == 1234

    @patch('lrc_mcp.adapters.lightroom._query_tasklist_lightroom')
    def test_is_lightroom_running_not_found(self, mock_query):
        """Test _is_lightroom_running when Lightroom is not found."""
        mock_query.return_value = "OtherProcess.exe 1234 Console"
        is_running, pid = _is_lightroom_running()
        assert is_running is False
        assert pid is None

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    @patch('lrc_mcp.adapters.lightroom.os.path.isfile')
    @patch('lrc_mcp.adapters.lightroom.os.path.dirname')
    @patch('lrc_mcp.adapters.lightroom.subprocess.Popen')
    def test_launch_via_external_launcher_success(self, mock_popen, mock_dirname, mock_isfile, mock_exists):
        """Test _launch_via_external_launcher success case."""
        # Mock file existence checks: launcher exists and is file, lightroom exe exists and is file
        mock_exists.side_effect = lambda path: "launch_lightroom_external.py" in path or "/path/to/lightroom.exe" in path
        mock_isfile.side_effect = lambda path: "launch_lightroom_external.py" in path or "/path/to/lightroom.exe" in path
        mock_dirname.return_value = "/project/root"
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        _launch_via_external_launcher("/path/to/lightroom.exe")
        
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "launch_lightroom_external.py" in args[1]
        assert "/path/to/lightroom.exe" in args

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    def test_launch_via_external_launcher_launcher_not_found(self, mock_exists):
        """Test _launch_via_external_launcher when launcher is not found."""
        mock_exists.side_effect = [False, True]  # launcher not found, but lightroom exe exists
        
        with pytest.raises(FileNotFoundError, match="External launcher not found"):
            _launch_via_external_launcher("/path/to/lightroom.exe")

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    def test_launch_via_external_launcher_lightroom_not_found(self, mock_exists):
        """Test _launch_via_external_launcher when Lightroom exe is not found."""
        mock_exists.side_effect = [True, False]  # launcher found, but lightroom exe not found
        
        with pytest.raises(FileNotFoundError, match="Lightroom executable not found"):
            _launch_via_external_launcher("/path/to/lightroom.exe")

    @patch('lrc_mcp.adapters.lightroom.os.getenv')
    def test_resolve_lightroom_path_explicit(self, mock_getenv):
        """Test resolve_lightroom_path with explicit path."""
        explicit_path = "/custom/path/to/Lightroom.exe"
        result = resolve_lightroom_path(explicit_path)
        assert result == explicit_path

    @patch('lrc_mcp.adapters.lightroom.os.getenv')
    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    def test_resolve_lightroom_path_env_var(self, mock_getenv):
        """Test resolve_lightroom_path with environment variable."""
        mock_getenv.return_value = "/env/path/to/Lightroom.exe"
        result = resolve_lightroom_path(None)
        assert result == "/env/path/to/Lightroom.exe"
        mock_getenv.assert_called_once_with("LRCLASSIC_PATH")

    @patch('lrc_mcp.adapters.lightroom.os.getenv')
    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    def test_resolve_lightroom_path_default_windows(self, mock_exists, mock_getenv):
        """Test resolve_lightroom_path with default Windows path."""
        mock_getenv.return_value = None
        mock_exists.return_value = True
        from lrc_mcp.adapters.lightroom import DEFAULT_WINDOWS_PATH
        result = resolve_lightroom_path(None)
        assert result == DEFAULT_WINDOWS_PATH

    @patch('lrc_mcp.adapters.lightroom.os.getenv')
    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    @patch('lrc_mcp.adapters.lightroom.shutil.which')
    def test_resolve_lightroom_path_shutil_which(self, mock_which, mock_exists, mock_getenv):
        """Test resolve_lightroom_path with shutil.which fallback."""
        mock_getenv.return_value = None
        mock_exists.return_value = False
        mock_which.return_value = "/found/via/which/Lightroom.exe"
        result = resolve_lightroom_path(None)
        assert result == "/found/via/which/Lightroom.exe"

    @patch('lrc_mcp.adapters.lightroom.os.getenv')
    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    @patch('lrc_mcp.adapters.lightroom.shutil.which')
    def test_resolve_lightroom_path_not_found(self, mock_which, mock_exists, mock_getenv):
        """Test resolve_lightroom_path when no path is found."""
        mock_getenv.return_value = None
        mock_exists.return_value = False
        mock_which.return_value = None
        with pytest.raises(FileNotFoundError, match="Unable to resolve Lightroom Classic executable path"):
            resolve_lightroom_path(None)

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.resolve_lightroom_path')
    @patch('lrc_mcp.adapters.lightroom._is_lightroom_running')
    @patch('lrc_mcp.adapters.lightroom._launch_via_external_launcher')
    @patch('lrc_mcp.adapters.lightroom.time.sleep')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    @patch('lrc_mcp.adapters.lightroom.os.path.isfile')
    def test_launch_lightroom_already_running(self, mock_isfile, mock_exists, mock_sleep, mock_launch, mock_is_running, mock_resolve):
        """Test launch_lightroom when Lightroom is already running."""
        mock_resolve.return_value = "/path/to/lightroom.exe"
        mock_exists.return_value = True  # Lightroom path exists
        mock_isfile.return_value = True  # Lightroom path is a file
        mock_is_running.return_value = (True, 1234)
        
        result = launch_lightroom()
        assert isinstance(result, LaunchResult)
        assert result.launched is False
        assert result.pid == 1234
        assert result.path == "/path/to/lightroom.exe"
        mock_launch.assert_not_called()

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.resolve_lightroom_path')
    @patch('lrc_mcp.adapters.lightroom._is_lightroom_running')
    @patch('lrc_mcp.adapters.lightroom._launch_via_external_launcher')
    @patch('lrc_mcp.adapters.lightroom.time.sleep')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    @patch('lrc_mcp.adapters.lightroom.os.path.isfile')
    def test_launch_lightroom_success(self, mock_isfile, mock_exists, mock_sleep, mock_launch, mock_is_running, mock_resolve):
        """Test launch_lightroom success case."""
        mock_resolve.return_value = "/path/to/lightroom.exe"
        mock_exists.return_value = True  # Lightroom path exists
        mock_isfile.return_value = True  # Lightroom path is a file
        mock_is_running.side_effect = [(False, None), (True, 5678)]  # not running, then running
        mock_launch.return_value = None
        
        result = launch_lightroom()
        assert isinstance(result, LaunchResult)
        assert result.launched is True
        assert result.pid == 5678
        assert result.path == "/path/to/lightroom.exe"

    @patch('lrc_mcp.adapters.lightroom.os.name', 'nt')
    @patch('lrc_mcp.adapters.lightroom.resolve_lightroom_path')
    @patch('lrc_mcp.adapters.lightroom.os.path.exists')
    def test_launch_lightroom_path_not_found(self, mock_exists, mock_resolve):
        """Test launch_lightroom when Lightroom path doesn't exist."""
        mock_resolve.return_value = "/path/does/not/exist/Lightroom.exe"
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError):
            launch_lightroom()

    def test_launch_result_creation(self):
        """Test LaunchResult dataclass creation."""
        result = LaunchResult(launched=True, pid=1234, path="/path/to/lightroom.exe")
        assert result.launched is True
        assert result.pid == 1234
        assert result.path == "/path/to/lightroom.exe"
