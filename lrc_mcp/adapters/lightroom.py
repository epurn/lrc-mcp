"""Adapter utilities for launching Lightroom Classic on Windows.

This module discovers the Lightroom Classic executable and launches it if not
already running. The implementation is Windows-first and conservative.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


DEFAULT_WINDOWS_PATH = r"C:\\Program Files\\Adobe\\Adobe Lightroom Classic\\Lightroom.exe"


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
        return explicit_path
    env_path = os.getenv("LRCLASSIC_PATH")
    if env_path:
        return env_path
    if os.name == "nt" and os.path.exists(DEFAULT_WINDOWS_PATH):
        return DEFAULT_WINDOWS_PATH
    found = shutil.which("Lightroom.exe")
    if found:
        return found
    raise FileNotFoundError("Unable to resolve Lightroom Classic executable path")


def launch_lightroom(explicit_path: Optional[str] = None) -> LaunchResult:
    """Launch Lightroom Classic if possible.

    Returns a `LaunchResult` indicating whether a new process was spawned.
    A best-effort duplicate-run guard is not implemented here to avoid false
    negatives; users can re-use the tool idempotently.
    """
    path = resolve_lightroom_path(explicit_path)

    # Best-effort guard: if Lightroom is already running on Windows, don't spawn a new process
    if os.name == "nt":
        try:
            # Use tasklist to check for Lightroom.exe presence
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Lightroom.exe", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = (result.stdout or "") + (result.stderr or "")
            if "Lightroom.exe" in output:
                return LaunchResult(launched=False, pid=None, path=path)
        except Exception:
            # If the guard fails, we proceed to attempt launch.
            pass

    creationflags = 0
    if os.name == "nt":
        # Create new process group; avoid attaching console window
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )

    proc = subprocess.Popen([path], creationflags=creationflags, close_fds=True)
    return LaunchResult(launched=True, pid=proc.pid, path=path)


