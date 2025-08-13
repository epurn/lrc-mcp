"""pytest configuration file."""

import sys
from pathlib import Path

# Add src directory to Python path so we can import lrc_mcp modules
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))
