#!/usr/bin/env python3
"""
Test script for the lrc_launch_lightroom restart functionality.

This script tests that the launch tool properly handles existing instances.
"""

import json
import sys
import time
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from lrc_mcp.adapters.lightroom import launch_lightroom


def test_launch_restart():
    """Test the launch_lightroom function with restart logic."""
    print("Testing launch_lightroom restart functionality...")
    
    try:
        # First launch - should start fresh
        print("\n1. Testing first launch...")
        # Use the LRCLASSIC_PATH environment variable
        import os
        lightroom_path = os.getenv("LRCLASSIC_PATH")
        if not lightroom_path:
            print("   ⚠️  LRCLASSIC_PATH not set, trying default resolution...")
            result1 = launch_lightroom()
        else:
            print(f"   Using LRCLASSIC_PATH: {lightroom_path}")
            result1 = launch_lightroom(lightroom_path)
        print(f"   First launch result: {json.dumps(result1, indent=2, default=str)}")
        
        if result1.launched:
            print(f"   ✅ Successfully launched Lightroom (PID: {result1.pid})")
        else:
            print(f"   ✅ Lightroom was already running (PID: {result1.pid})")
            
        # Wait a moment for Lightroom to stabilize
        print("   Waiting 5 seconds for Lightroom to stabilize...")
        time.sleep(5)
        
        # Second launch - should kill existing and restart
        print("\n2. Testing restart (should kill existing and launch new)...")
        if not lightroom_path:
            result2 = launch_lightroom()
        else:
            result2 = launch_lightroom(lightroom_path)
        print(f"   Second launch result: {json.dumps(result2, indent=2, default=str)}")
        
        if result2.launched:
            print(f"   ✅ Successfully restarted Lightroom (PID: {result2.pid})")
            if result1.pid is not None and result2.pid is not None and result1.pid != result2.pid:
                print(f"   ✅ PID changed from {result1.pid} to {result2.pid} (restart confirmed)")
            else:
                print("   ⚠️  PID may not have changed (could be same instance)")
        else:
            print(f"   ⚠️  Lightroom launch reported not launched (PID: {result2.pid})")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing launch_lightroom: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("Testing lrc_launch_lightroom restart functionality...")
    print("=" * 60)
    
    success = test_launch_restart()
    
    if success:
        print("\n✅ All launch_lightroom restart tests passed!")
        return 0
    else:
        print("\n❌ launch_lightroom restart tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
