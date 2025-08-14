#!/usr/bin/env python3
"""
Test script to verify Lightroom Classic persistence beyond typical LLM tool timeouts.

This script:
1. Kills any running Lightroom.exe processes
2. Launches Lightroom via the MCP tool
3. Waits and polls for process persistence and plugin heartbeat
4. Logs timing and status information

Usage:
    python tests/test_lightroom_persistence.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from typing import Any, Dict, Optional

# Configuration
PORT = int(os.getenv("LRC_MCP_HTTP_PORT", "8765"))
TOKEN = os.getenv("LRC_MCP_PLUGIN_TOKEN")
BASE = f"http://127.0.0.1:{PORT}"
LIGHTROOM_EXE = "Lightroom.exe"


def kill_lightroom_processes() -> bool:
    """Kill all running Lightroom.exe processes (Windows-only).
    
    Returns:
        True if successful, False if failed
    """
    if os.name != "nt":
        print("This test is Windows-only (taskkill)")
        return False
    
    try:
        print("Killing any running Lightroom processes...")
        result = subprocess.run(
            ["taskkill", "/F", "/IM", LIGHTROOM_EXE, "/T"],
            capture_output=True,
            text=True,
            check=False
        )
        output = (result.stdout or "") + (result.stderr or "")
        print(f"Taskkill output: {output}")
        # taskkill returns 128 when no processes found, which is ok
        if result.returncode in (0, 128):
            print("Successfully killed Lightroom processes (or none were running)")
            return True
        else:
            print(f"Taskkill failed with return code {result.returncode}")
            return False
    except Exception as e:
        print(f"Failed to kill Lightroom processes: {e}")
        return False


def launch_lightroom_via_mcp() -> Optional[Dict[str, Any]]:
    """Launch Lightroom via the MCP tool endpoint.
    
    Returns:
        Launch result dictionary or None if failed
    """
    print("Launching Lightroom via MCP tool...")
    payload = {
        "method": "tools/call",
        "params": {
            "name": "lrc_launch_lightroom",
            "arguments": {}
        }
    }
    
    url = f"{BASE}/mcp"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={
            "Content-Type": "application/json",
            "X-Plugin-Token": TOKEN or ""
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                print("Empty response from MCP tool call")
                return None
            try:
                result = json.loads(body)
                print(f"Launch tool result: {json.dumps(result, indent=2)}")
                return result.get("result", {})
            except Exception as e:
                print(f"Failed to parse MCP tool response: {e}")
                print(f"Raw response: {body}")
                return None
    except Exception as e:
        print(f"Failed to call MCP launch tool: {e}")
        return None


def check_lightroom_process() -> tuple[bool, Optional[int]]:
    """Check if Lightroom.exe is running via tasklist.
    
    Returns:
        Tuple of (is_running, pid)
    """
    if os.name != "nt":
        return False, None
    
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {LIGHTROOM_EXE}", "/NH"],
            capture_output=True,
            text=True,
            check=False
        )
        output = (result.stdout or "") + (result.stderr or "")
        
        if LIGHTROOM_EXE in output:
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
            for line in lines:
                if LIGHTROOM_EXE in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            return True, pid
                        except (ValueError, IndexError):
                            continue
        return False, None
    except Exception as e:
        print(f"Failed to check Lightroom process: {e}")
        return False, None


def check_plugin_heartbeat() -> Optional[Dict[str, Any]]:
    """Check if the plugin is sending heartbeats.
    
    Returns:
        Heartbeat data dictionary or None if no heartbeat
    """
    try:
        url = f"{BASE}/plugin/heartbeat"
        req = urllib.request.Request(url)
        if TOKEN:
            req.add_header("X-Plugin-Token", TOKEN)
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            if body:
                try:
                    return json.loads(body)
                except Exception:
                    return {"raw": body}
        return None
    except Exception as e:
        print(f"Failed to check plugin heartbeat: {e}")
        return None


def main() -> int:
    """Main test entry point.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("=== Lightroom Persistence Test ===")
    print(f"Target server: {BASE}")
    print()
    
    # Step 1: Kill existing Lightroom processes
    if not kill_lightroom_processes():
        print("❌ Failed to kill Lightroom processes")
        return 1
    
    print()
    time.sleep(2)
    
    # Step 2: Launch Lightroom via MCP tool
    launch_result = launch_lightroom_via_mcp()
    if not launch_result:
        print("❌ Failed to launch Lightroom via MCP tool")
        return 1
    
    launched = launch_result.get("launched", False)
    initial_pid = launch_result.get("pid")
    
    if not launched:
        print("⚠️  Lightroom was already running or launch was skipped")
    
    print(f"Initial launch result - Launched: {launched}, PID: {initial_pid}")
    print()
    
    # Step 3: Wait and monitor for persistence and heartbeat
    print("Monitoring Lightroom persistence and heartbeat for 90 seconds...")
    print("(This tests beyond typical LLM tool timeout windows)")
    print()
    
    start_time = time.time()
    heartbeat_first_seen = None
    heartbeat_count = 0
    process_check_interval = 5  # Check process every 5 seconds
    heartbeat_check_interval = 10  # Check heartbeat every 10 seconds
    next_process_check = start_time + process_check_interval
    next_heartbeat_check = start_time + heartbeat_check_interval
    
    # Monitor for 90 seconds
    while time.time() - start_time < 90:
        current_time = time.time()
        
        # Check process persistence
        if current_time >= next_process_check:
            is_running, current_pid = check_lightroom_process()
            status = "✅ RUNNING" if is_running else "❌ NOT RUNNING"
            print(f"[{int(current_time - start_time):2d}s] Process: {status} (PID: {current_pid})")
            
            if not is_running and launched:
                print("❌ Lightroom process terminated unexpectedly!")
                return 1
            
            next_process_check = current_time + process_check_interval
        
        # Check plugin heartbeat
        if current_time >= next_heartbeat_check:
            heartbeat = check_plugin_heartbeat()
            if heartbeat:
                if not heartbeat_first_seen:
                    heartbeat_first_seen = current_time
                    time_to_first_heartbeat = current_time - start_time
                    print(f"[{int(current_time - start_time):2d}s] 📡 First heartbeat received! (took {time_to_first_heartbeat:.1f}s)")
                heartbeat_count += 1
                status = heartbeat.get("status", "unknown")
                lr_version = heartbeat.get("lr_version", "unknown")
                print(f"[{int(current_time - start_time):2d}s] Heartbeat: {status} (LR: {lr_version})")
            else:
                print(f"[{int(current_time - start_time):2d}s] Heartbeat: ❌ No response")
            
            next_heartbeat_check = current_time + heartbeat_check_interval
        
        time.sleep(1)
    
    # Final status
    print()
    print("=== Test Results ===")
    is_running_final, final_pid = check_lightroom_process()
    heartbeat_final = check_plugin_heartbeat()
    
    print(f"Final process status: {'✅ RUNNING' if is_running_final else '❌ NOT RUNNING'} (PID: {final_pid})")
    if heartbeat_first_seen:
        total_heartbeat_time = time.time() - heartbeat_first_seen
        print(f"Final heartbeat status: ✅ ACTIVE (first seen at {int(heartbeat_first_seen - start_time)}s, {heartbeat_count} heartbeats)")
        print(f"Total heartbeat duration: {int(total_heartbeat_time)}s")
    else:
        print("Final heartbeat status: ❌ NO HEARTBEAT")
    
    if is_running_final and heartbeat_first_seen:
        print()
        print("🎉 SUCCESS: Lightroom persisted and plugin is communicating!")
        return 0
    else:
        print()
        print("💥 FAILURE: Lightroom did not persist or plugin is not communicating")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
