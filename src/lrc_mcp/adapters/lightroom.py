"""Adapter utilities for launching Lightroom Classic on Windows.

This module discovers the Lightroom Classic executable and launches it if not
already running. The implementation is Windows-first and conservative.
"""

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

# Windows job/process diagnostics and helpers
def _is_current_process_in_job() -> Optional[bool]:
    """
    Best-effort check whether the current process is running inside a Job object (Windows-only).

    Returns:
        True if in a job, False if not, None if undetectable or non-Windows.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        IsProcessInJob = kernel32.IsProcessInJob
        IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        IsProcessInJob.restype = wintypes.BOOL

        bool_in_job = wintypes.BOOL()
        current_process = ctypes.c_void_p(-1)  # GetCurrentProcess() pseudo-handle
        if not IsProcessInJob(current_process, None, ctypes.byref(bool_in_job)):
            return None
        return bool(bool_in_job.value)
    except Exception:
        return None


def _log_job_status() -> None:
    """Log whether the current process appears to be inside a job."""
    status = _is_current_process_in_job()
    if status is None:
        logger.info("job status: undetectable or non-Windows")
    else:
        logger.info(f"job status: in_job={status}")


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


def _launch_via_explorer(path: str) -> None:
    """
    Attempt to launch Lightroom by delegating to explorer.exe so the shell
    (outside the MCP host job) performs the execution. PID is not reliable.
    """
    if os.name != "nt":
        return
    try:
        logger.warning("falling back to explorer.exe launch")
        subprocess.Popen(
            ["explorer.exe", path],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            shell=False,
        )
    except Exception as exc:
        logger.error(f"explorer.exe fallback failed: {exc}")


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


def launch_lightroom(explicit_path: Optional[str] = None) -> LaunchResult:
    """Launch Lightroom Classic if possible.

    Returns a `LaunchResult` indicating whether a new process was spawned.
    A best-effort duplicate-run guard is not implemented here to avoid false
    negatives; users can re-use the tool idempotently.
    """
    try:
        path = resolve_lightroom_path(explicit_path)
        logger.info(f"Resolved Lightroom path: {path}")
        _log_job_status()
        
        # Validate that the executable exists
        if not os.path.exists(path):
            raise FileNotFoundError(f"Lightroom executable not found at: {path}")
        
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Lightroom path is not a file: {path}")

        # Best-effort guard: if Lightroom is already running on Windows, don't spawn a new process
        if os.name == "nt":
            try:
                # Use tasklist to check for Lightroom.exe presence
                logger.info("Checking if Lightroom is already running...")
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq Lightroom.exe", "/NH"],
                    capture_output=True,
                    text=True,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                output = (result.stdout or "") + (result.stderr or "")
                logger.info(f"Tasklist output: {output}")
                if "Lightroom.exe" in output:
                    logger.info("Lightroom is already running, not launching new instance")
                    return LaunchResult(launched=False, pid=None, path=path)
            except Exception as e:
                logger.warning(f"Failed to check if Lightroom is running: {e}")
                # If the guard fails, we proceed to attempt launch.

        # Launch Lightroom via explorer.exe to ensure persistence beyond job termination
        logger.info(f"Launching Lightroom via explorer.exe: {path}")
        try:
            _launch_via_explorer(path)
            logger.info("Launched Lightroom via explorer.exe (PID not available)")
            # Give it a moment to start
            time.sleep(5)
            # Verify it's running
            running, pid = _is_lightroom_running()
            if running:
                logger.info(f"Lightroom is running after explorer launch (PID: {pid})")
                return LaunchResult(launched=True, pid=pid, path=path)
            else:
                logger.warning("Lightroom may not have started after explorer launch")
                return LaunchResult(launched=True, pid=None, path=path)
        except Exception as e:
            logger.error(f"Failed to launch Lightroom via explorer.exe: {e}")
            raise
        
    except Exception as e:
        logger.error(f"Failed to launch Lightroom: {e}", exc_info=True)
        raise
