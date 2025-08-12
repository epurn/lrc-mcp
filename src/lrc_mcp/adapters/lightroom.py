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


def launch_lightroom(explicit_path: Optional[str] = None) -> LaunchResult:
    """Launch Lightroom Classic using external launcher for maximum compatibility.

    Returns a `LaunchResult` indicating whether a new process was spawned.
    Uses an external launcher script that handles job object isolation.
    """
    try:
        path = resolve_lightroom_path(explicit_path)
        logger.info(f"Resolved Lightroom path: {path}")
        
        # Validate that the executable exists
        if not os.path.exists(path):
            raise FileNotFoundError(f"Lightroom executable not found at: {path}")
        
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Lightroom path is not a file: {path}")

        # Check if Lightroom is already running
        if os.name == "nt":
            try:
                running, existing_pid = _is_lightroom_running()
                if running:
                    logger.info(f"Lightroom is already running (PID: {existing_pid}), not launching new instance")
                    return LaunchResult(launched=False, pid=existing_pid, path=path)
            except Exception as e:
                logger.warning(f"Failed to check if Lightroom is running: {e}")
                # If the check fails, proceed with launch attempt

        # Launch Lightroom via external launcher
        logger.info(f"Launching Lightroom via external launcher: {path}")
        try:
            _launch_via_external_launcher(path)
            logger.info("External launcher completed")
            
            # Give it a moment to start
            time.sleep(5)
            
            # Verify it's running
            running, pid = _is_lightroom_running()
            if running:
                logger.info(f"Lightroom is running after launch (PID: {pid})")
                return LaunchResult(launched=True, pid=pid, path=path)
            else:
                logger.warning("Lightroom may not have started yet (this can be normal)")
                return LaunchResult(launched=True, pid=None, path=path)
        except Exception as e:
            logger.error(f"Failed to launch Lightroom: {e}")
            raise
        
    except Exception as e:
        logger.error(f"Failed to launch Lightroom: {e}", exc_info=True)
        raise
