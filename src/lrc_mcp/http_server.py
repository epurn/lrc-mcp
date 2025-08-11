"""HTTP server entry point for uvicorn deployment."""

from __future__ import annotations

import os
import logging
from dotenv import load_dotenv

from lrc_mcp.infra.http import create_app
from lrc_mcp.uvicorn_config import UVICORN_CONFIG

# Load environment variables
load_dotenv()


def main() -> None:
    """Run the HTTP server independently.
    
    This function is intended for use with uvicorn:
    `uvicorn lrc_mcp.http_server:app --host 127.0.0.1 --port 8765`
    """
    import uvicorn
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    
    app = create_app()
    uvicorn.run(app, **UVICORN_CONFIG)


# For direct uvicorn import
app = create_app()

if __name__ == "__main__":
    main()
