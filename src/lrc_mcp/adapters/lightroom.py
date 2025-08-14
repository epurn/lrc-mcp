"""Adapter utilities for launching Lightroom Classic on Windows.

This module discovers the Lightroom Classic executable and launches it using
an external launcher that handles job object isolation for maximum compatibility."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple


DEFAULT_WINDOWS_PATH = r"C:\Program Files\Adobe\Adobe Lightroom Classic\Lightroom.exe"
logger = logging.getLogger(__name__)


def _query_tasklist_lightroom() -> str:
    """Return raw tasklist output filtered to Lightroom.exe (Windows-only)."""
    if os.name != "nt":
        return ""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Lightroom.exe", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (result.stdout or "") + (result.stderr or "")
    except Exception as exc:
        logger.warning(f"tasklist query failed: {exc}")
        return ""


def _parse_first_pid_from_tasklist(output: str) -> Optional[int]:
    """Parse the first PID for Lightroom.exe from tasklist output."""
    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    for line in lines:
        if "Lightroom.exe" in line:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except Exception:
                    continue
    return None


def _is_lightroom_running() -> Tuple[bool, Optional[int]]:
    """Check if Lightroom.exe appears to be running via tasklist."""
    out = _query_tasklist_lightroom()
    if "Lightroom.exe" in out:
        return True, _parse_first_pid_from_tasklist(out)
    return False, None


def is_lightroom_process_running() -> bool:
    """Check if Lightroom process is currently running.
    
    Returns:
        True if Lightroom process is running, False otherwise
    """
    try:
        running, _ = _is_lightroom_running()
        return running
    except Exception:
        # If we can't determine, assume not running
        return False


def _kill_lightroom_gracefully(pid: int, timeout: int = 15) -> bool:
    """Gracefully kill Lightroom process with timeout.
    
    Args:
        pid: Process ID to kill
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if process was killed, False if timeout reached
    """
    if os.name != "nt":
        return False
    
    logger.info(f"Attempting to gracefully kill Lightroom (PID: {pid})")
    start_time = time.time()
    
    try:
        # Try graceful close first (WM_CLOSE)
        import ctypes
        from ctypes import wintypes
        
        # Get handle to the process
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        
        # Open process
        process_handle = kernel32.OpenProcess(0x00100000, False, pid)  # PROCESS_QUERY_INFORMATION
        if process_handle:
            try:
                # Enumerate windows and send WM_CLOSE to Lightroom windows
                def enum_windows_proc(hwnd, lParam):
                    # Get process ID for window
                    window_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                    if window_pid.value == pid:
                        # Send WM_CLOSE (0x0010)
                        user32.PostMessageW(hwnd, 0x0010, 0, 0)
                        logger.info(f"Sent WM_CLOSE to window {hwnd}")
                    return True
                
                # Enumerate all windows
                enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows(enum_proc(enum_windows_proc), 0)
            finally:
                kernel32.CloseHandle(process_handle)
        
        # Wait for process to exit
        while time.time() - start_time < timeout:
            running, current_pid = _is_lightroom_running()
            if not running or current_pid != pid:
                logger.info(f"Lightroom process {pid} terminated gracefully")
                return True
            time.sleep(1)
        
        # If still running, force kill
        logger.warning(f"Lightroom process {pid} did not respond to graceful close, forcing termination")
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        
        # Wait a bit more for force kill to take effect
        time.sleep(2)
        running, current_pid = _is_lightroom_running()
        if not running or current_pid != pid:
            logger.info(f"Lightroom process {pid} force terminated")
            return True
            
    except Exception as e:
        logger.error(f"Error during graceful kill attempt: {e}")
    
    # Final check
    running, current_pid = _is_lightroom_running()
    if not running or current_pid != pid:
        return True
        
    logger.error(f"Failed to kill Lightroom process {pid} within {timeout} seconds")
    return False


def _launch_via_external_launcher(path: str) -> None:
    """
    Launch Lightroom using the external launcher script that handles
    job object isolation and multiple launch strategies.
    """
    if os.name != "nt":
        return
    
    logger.info(f"Launching Lightroom via external launcher: {path}")
    
    # Find the external launcher script
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    launcher_path = os.path.join(project_root, "launch_lightroom_external.py")
    
    # Validate paths
    if not os.path.exists(launcher_path):
        logger.error(f"External launcher not found: {launcher_path}")
        raise FileNotFoundError(f"External launcher not found: {launcher_path}")
        
    if not os.path.exists(path) or not os.path.isfile(path):
        logger.error(f"Lightroom executable not found: {path}")
        raise FileNotFoundError(f"Lightroom executable not found: {path}")
    
    # Launch the external launcher
    cmd = [sys.executable, launcher_path, path]
    logger.info(f"Executing external launcher: {cmd}")
    
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            shell=False,
        )
        logger.info("External launcher started successfully")
    except Exception as exc:
        logger.error(f"Failed to start external launcher: {exc}", exc_info=True)
        raise


@dataclass(frozen=True)
class LaunchResult:
    launched: bool
    pid: Optional[int]
    path: str


def resolve_lightroom_path(explicit_path: Optional[str] = None) -> str:
    """Resolve Lightroom executable path.

    Precedence:
    1. Provided explicit path
    2. Environment variable `LRCLASSIC_PATH`
    3. Default Windows install path
    4. `shutil.which('Lightroom.exe')`
    """
    if explicit_path:
        logger.info(f"Using explicit path: {explicit_path}")
        return explicit_path
    env_path = os.getenv("LRCLASSIC_PATH")
    if env_path:
        logger.info(f"Using LRCLASSIC_PATH environment variable: {env_path}")
        return env_path
    if os.name == "nt" and os.path.exists(DEFAULT_WINDOWS_PATH):
        logger.info(f"Using default Windows path: {DEFAULT_WINDOWS_PATH}")
        return DEFAULT_WINDOWS_PATH
    found = shutil.which("Lightroom.exe")
    if found:
        logger.info(f"Found Lightroom.exe via shutil.which: {found}")
        return found
    raise FileNotFoundError("Unable to resolve Lightroom Classic executable path")


def kill_lightroom() -> dict:
    """Gracefully kill any running Lightroom Classic process.
    
    Returns:
        Dict with kill result information:
        - killed: bool - whether a process was killed
        - previous_pid: Optional[int] - PID of killed process, None if none was running
        - duration_ms: int - time taken in milliseconds
    """
    if os.name != "nt":
        return {"killed": False, "previous_pid": None, "duration_ms": 0}
    
    start_time = time.time()
    
    try:
        running, pid = _is_lightroom_running()
        if not running or pid is None:
            duration_ms = int((time.time() - start_time) * 1000)
            return {"killed": False, "previous_pid": None, "duration_ms": duration_ms}
        
        logger.info(f"Killing Lightroom process (PID: {pid})")
        success = _kill_lightroom_gracefully(pid, timeout=15)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if success:
            logger.info(f"Successfully killed Lightroom process {pid}")
            return {"killed": True, "previous_pid": pid, "duration_ms": duration_ms}
        else:
            logger.error(f"Failed to kill Lightroom process {pid}")
            raise RuntimeError(f"Failed to terminate Lightroom process {pid} within timeout")
            
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Error killing Lightroom: {e}")
        raise


def launch_lightroom(explicit_path: Optional[str] = None) -> LaunchResult:
    """Launch Lightroom Classic using external launcher for maximum compatibility.

    Returns a `LaunchResult` indicating whether a new process was spawned.
    Uses an external launcher script that handles job object isolation.
    If Lightroom is already running, it will be gracefully terminated before launching.
    """
    try:
        path = resolve_lightroom_path(explicit_path)
        logger.info(f"Resolved Lightroom path: {path}")
        
        # Validate that the executable exists
        if not os.path.exists(path):
            raise FileNotFoundError(f"Lightroom executable not found at: {path}")
        
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Lightroom path is not a file: {path}")

        # Check if Lightroom is already running and kill it if so
        existing_pid = None
        if os.name == "nt":
            try:
                running, pid = _is_lightroom_running()
                if running and pid is not None:
                    logger.info(f"Lightroom is already running (PID: {pid}), terminating before relaunch")
                    existing_pid = pid
                    # Kill the existing process gracefully
                    if not _kill_lightroom_gracefully(pid, timeout=15):
                        raise RuntimeError(f"Failed to terminate existing Lightroom process {pid} within 15 seconds")
                    # Wait a moment for process to fully terminate
                    time.sleep(2)
            except Exception as e:
                logger.warning(f"Failed to check/kill existing Lightroom process: {e}")
                # If the check fails, proceed with launch attempt but warn

        # Launch Lightroom via external launcher
        logger.info(f"Launching Lightroom via external launcher: {path}")
        try:
            _launch_via_external_launcher(path)
            logger.info("External launcher completed")
            
            # Give it a moment to start
            time.sleep(5)
            
            # Verify it's running and get the new PID
            running, new_pid = _is_lightroom_running()
            if running:
                logger.info(f"Lightroom is running after launch (PID: {new_pid})")
                # Check if this is a restart (different PID) or fresh launch
                launched = existing_pid is None or (new_pid is not None and new_pid != existing_pid)
                return LaunchResult(launched=launched, pid=new_pid, path=path)
            else:
                logger.warning("Lightroom may not have started yet (this can be normal)")
                return LaunchResult(launched=True, pid=None, path=path)
        except Exception as e:
            logger.error(f"Failed to launch Lightroom: {e}")
            raise
        
    except Exception as e:
        logger.error(f"Failed to launch Lightroom: {e}", exc_info=True)
        raise
