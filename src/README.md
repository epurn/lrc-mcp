## lrc-mcp

MCP server exposing tools over stdio and a local HTTP bridge for a Lightroom Classic plugin (heartbeat + command queue).

### Requirements
- Python 3.11+
- Dependencies in `requirements.txt`

### Setup
```
python -m venv .venv
. .venv/Scripts/Activate.ps1  # Windows PowerShell
pip install -U pip
pip install -r requirements.txt
```

### Configure environment
Create a `.env` file and adjust values as needed:
```
cp .env.example .env
```
Supported variables:
- `LRC_MCP_HTTP_PORT` (default `8765`)
- `LRC_MCP_PLUGIN_TOKEN` (optional; if set, plugin must send matching token)
- `LRCLASSIC_PATH` (optional override for Lightroom.exe path)

### Run
```
python -m lrc_mcp.main
```

### Run HTTP server with uvicorn (for deployment)
```
uvicorn lrc_mcp.http_server:app --host 127.0.0.1 --port 8765
```

Or with auto-reload for development:
```
uvicorn lrc_mcp.http_server:app --host 127.0.0.1 --port 8765 --reload
```

### Tools
- `lrc_mcp_health`: basic health check for the MCP server. Returns structured output: `{ status, serverTime, version }`.
- `lrc_launch_lightroom`: launch Lightroom Classic (Windows). Optional `path` input; otherwise uses `LRCLASSIC_PATH` or default install path. Returns `{ launched, pid, path }`.
- `lrc_lightroom_version`: returns `{ status: "ok"|"waiting", lr_version, last_seen }` based on plugin heartbeat.
- `lrc_add_collection`: create a new collection in Lightroom. **Requires Lightroom to be running.** Input: `{ name, parent_path, wait_timeout_sec }`. Returns `{ status, created, collection, command_id, error }`.
- `lrc_remove_collection`: remove a collection from Lightroom. **Requires Lightroom to be running.** Input: `{ collection_path, wait_timeout_sec }`. Returns `{ status, removed, command_id, error }`.
- `lrc_edit_collection`: edit (rename/move) a collection in Lightroom. **Requires Lightroom to be running.** Input: `{ collection_path, new_name, new_parent_path, wait_timeout_sec }`. Returns `{ status, updated, collection, command_id, error }`.
- `lrc_collection`: unified collection dispatcher for list/create/edit/delete. **Requires Lightroom to be running.** Input: `{ function: "list"|"create"|"edit"|"delete", args: object, wait_timeout_sec?: number|null }`. Returns `{ status, result, command_id, error, deprecation? }`. Notes:
  - Accepts legacy alias `function: "remove"` which maps to `delete` and sets a deprecation note.
  - `list` supports optional filters `{ set_id?: string, name_contains?: string }` and returns `{ collections: [{ id, name, set_id, smart, photo_count, path }] }`.

### HTTP bridge (Step 4 foundation)
Endpoints for the plugin:
- `POST /plugin/heartbeat` — send heartbeat beacons.
- `POST /plugin/commands/enqueue` — server-side enqueue (used by tools in later steps).
- `POST /plugin/commands/claim` — plugin claims pending commands. Body: `{ "worker": "lrc-plugin", "max": 1 }`. Returns 204 if none.
- `POST /plugin/commands/{id}/result` — plugin posts result for a command.

Notes:
- Header `X-Plugin-Token` is required when `LRC_MCP_PLUGIN_TOKEN` is set; otherwise accepted in dev.
- Bridge binds to `127.0.0.1` only (see main.py uvicorn config).

### Lightroom plugin setup
1) In Lightroom Classic: File → Plug‑in Manager → Add… → select `plugin/lrc-mcp.lrplugin`.
2) The plugin runs background tasks that (a) post heartbeats and (b) poll for commands, supporting minimal `noop` and `echo` commands.
3) Optional: place a raw token string at `%APPDATA%/lrc-mcp/config.json` to authenticate requests when `LRC_MCP_PLUGIN_TOKEN` is set.

### Testing
After the plugin loads and the server is running, you should see periodic heartbeat logs in the plugin log and server logs. Test the command queue functionality:

```bash
# Test basic command queuing
python tests/enqueue_echo.py "test message"

# Run comprehensive command queue tests
python tests/test_command_queue.py

# Test collection management commands
python tests/test_collections.py

# Test Lightroom dependency checking
python tests/test_lightroom_dependency.py
```

Check the plugin logs at `plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log` to see commands being claimed and completed.

### Project Structure
```
lrc_mcp/
├── adapters/         # External system adapters (Lightroom integration)
├── api/              # HTTP API routes and handlers
├── infra/            # Infrastructure setup (FastAPI app)
├── services/         # Business logic services (command queue, heartbeat)
├── schema/           # Pydantic models
├── health.py         # Health check tool
├── lightroom.py      # Lightroom tools (launch, version)
├── server.py         # MCP server setup and tool registration
├── utils.py          # Common utility functions
├── uvicorn_config.py # Uvicorn deployment configuration
├── http_server.py    # HTTP server entry point for uvicorn
└── main.py          # Application entry point
tests/               # Test scripts
plugin/              # Lightroom Classic plugin
```

### References
- MCP docs: https://modelcontextprotocol.io/docs
- Lightroom SDK samples
