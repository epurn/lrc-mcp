"""Uvicorn configuration for the lrc-mcp server."""

import os
import logging

# Uvicorn configuration
UVICORN_CONFIG = {
    "host": "127.0.0.1",
    "port": int(os.getenv("LRC_MCP_HTTP_PORT", "8765")),
    "log_config": {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": False,
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            # Reduce access logs and send them to stderr as well (we also disable via access_log=False)
            "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        },
    },
    "access_log": False,
    "log_level": "info",
}

# Default configuration for development
DEV_CONFIG = {
    "host": "127.0.0.1",
    "port": int(os.getenv("LRC_MCP_HTTP_PORT", "8765")),
    "reload": True,
    "log_level": "debug",
}
