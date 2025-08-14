#!/usr/bin/env python3
"""
Test script for the new lrc_kill_lightroom tool.

This script tests the standalone kill tool functionality.
"""

import json
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from lrc_mcp.adapters.lightroom import kill_lightroom


def test_kill_lightroom():
    """Test the kill_lightroom function directly."""
    print("Testing kill_lightroom function...")
    
    try:
        result = kill_lightroom()
        print(f"✅ kill_lightroom result: {json.dumps(result, indent=2)}")
        
        if result["killed"]:
            print(f"✅ Successfully killed Lightroom process {result['previous_pid']}")
        else:
            print("✅ No Lightroom process was running (this is normal)")
            
        print(f"✅ Operation took {result['duration_ms']} ms")
        return True
        
    except Exception as e:
        print(f"❌ Error testing kill_lightroom: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("Testing lrc_kill_lightroom functionality...")
    print("=" * 50)
    
    success = test_kill_lightroom()
    
    if success:
        print("\n✅ All kill_lightroom tests passed!")
        return 0
    else:
        print("\n❌ kill_lightroom tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
