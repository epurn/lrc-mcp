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
cd src
pip install -e .
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
- `lrc_mcp_health`: Does check the health status of the lrc-mcp server. Returns server status, current time, and version information. Use this to verify the server is running properly. Returns `{ status, serverTime, version }`.
- `lrc_launch_lightroom`: Does launch Lightroom Classic on Windows. Detects and gracefully terminates existing instances before launching. Uses external launcher for job object isolation. Returns process information and launch status. Input: `{ path }`. Returns `{ launched, pid, path }`.
- `lrc_kill_lightroom`: Does gracefully terminate any running Lightroom Classic process. Sends WM_CLOSE message to Lightroom windows, waits up to 15 seconds for graceful shutdown, then force terminates if needed. Returns termination status and process information. Returns `{ killed, previous_pid, duration_ms }`.
- `lrc_lightroom_version`: Does return Lightroom Classic version and enhanced process status information. Checks both plugin heartbeat and actual process presence to determine Lightroom status. Essential for verifying Lightroom connectivity before using other tools. Returns `{ status: "ok"|"waiting"|"not_running", running, lr_version, last_seen }`. **Important:** Always wait for `status: "ok"` before using other Lightroom tools.
- `lrc_add_collection`: Does create a new collection in Lightroom Classic. Requires Lightroom to be running with plugin connected. Parent collection sets must already exist. Returns collection information and creation status. Input: `{ name, parent_path, wait_timeout_sec }`. Returns `{ status, created, collection, command_id, error }`.
- `lrc_add_collection_set`: Does create a new collection set in Lightroom Classic. Requires Lightroom to be running with plugin connected. Parent collection sets must already exist. Returns collection set information and creation status. Input: `{ name, parent_path, wait_timeout_sec }`. Returns `{ status, created, collection_set, command_id, error }`.
- `lrc_remove_collection`: Does remove a collection from Lightroom Classic. Requires Lightroom to be running with plugin connected. Returns removal status and operation information. Input: `{ collection_path, wait_timeout_sec }`. Returns `{ status, removed, command_id, error }`.
- `lrc_edit_collection`: Does edit (rename/move) a collection in Lightroom Classic. Requires Lightroom to be running with plugin connected. Can change collection name and/or move to different parent. Returns updated collection information and operation status. Input: `{ collection_path, new_name, new_parent_path, wait_timeout_sec }`. Returns `{ status, updated, collection, command_id, error }`.
- `check_command_status`: Does check the status of a previously submitted asynchronous command. Returns current status and result information. Input: `{ command_id }`. Returns `{ status: "pending"|"running"|"completed"|"failed", result, error, progress }`.

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

### Recent Changes
- **Project Structure Update**: Moved Python code to `src/` subdirectory for better organization
- **Import Fix**: Resolved import errors by installing package in development mode (`pip install -e .`) from the `src` directory

### Testing
After the plugin loads and the server is running, you should see periodic heartbeat logs in the plugin log and server logs. Test the command queue functionality:

```bash
# Test basic command queuing
python tests/functional/enqueue_echo.py "test message"

# Run comprehensive command queue tests
python tests/functional/test_command_queue.py

# Test collection management commands
python tests/functional/test_collections.py

# Test Lightroom dependency checking
python tests/functional/test_lightroom_dependency.py

# Test Lightroom persistence beyond LLM timeouts (Windows)
python tests/functional/test_lightroom_persistence.py
```

#### Unit Tests
The project now includes comprehensive unit tests that can be run without external dependencies:

#### Plugin Tests
The Lightroom Classic plugin includes an in-situ test suite that can be run directly within Lightroom to validate plugin functionality:

**Running Plugin Tests:**
1. In Lightroom Classic, go to `File` → `Plug-in Extras`
2. Select `MCP: Run Tests` from the menu
3. Check the plugin logs for detailed results at `plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log`

**Test Coverage:**
- Collection lifecycle operations (create, remove)
- Collection set lifecycle operations (create, remove, nested collections)
- Error path handling (invalid inputs, missing parents, non-existent items)
- Automatic cleanup of test artifacts
- Asynchronous execution with proper write access handling

**Test Implementation:**
- Tests run in `LrTasks.startAsyncTask` to avoid blocking the UI thread
- Catalog mutations execute within `catalog:withWriteAccessDo` for safe write operations
- All test results are logged using `logger.info` for evidence capture
- Comprehensive cleanup ensures no test artifacts remain in your catalog

For detailed documentation, see `plugin/lrc-mcp.lrplugin/TESTING.md`.

```bash
# Run unit tests only
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run functional tests
pytest tests/functional -v

# Run all tests
pytest tests -v

# Run tests with coverage report
pytest tests --cov=src/lrc_mcp --cov-report=html --cov-report=term
```

Or use the test runner script:
```bash
# Run unit tests
python tests/run_tests.py unit

# Run integration tests
python tests/run_tests.py integration

# Run functional tests
python tests/run_tests.py functional

# Run all tests
python tests/run_tests.py all

# Run with coverage
python tests/run_tests.py coverage
```

Check the plugin logs at `plugin/lrc-mcp.lrplugin/logs/lrc_mcp.log` to see commands being claimed and completed.

#### Windows Job Object Considerations
When launched via MCP tools from certain hosts (like LLM applications), the lrc-mcp server may run inside a Windows Job object that terminates child processes when the job closes. This can cause Lightroom to crash ~30 seconds after launch.

The `lrc_launch_lightroom` tool addresses this by using `explorer.exe` to launch Lightroom, which runs outside the host job context and ensures persistence beyond tool call completion.

**Operational Procedure:**
- Always wait for `lrc_lightroom_version` to return `status: "ok"` before using other Lightroom tools
- Lightroom typically takes 15-20 seconds to fully start and establish plugin communication
- The persistence test script validates behavior beyond typical LLM tool timeout windows

### Project Structure
```
src/
└── lrc_mcp/
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
tests/                   # Test scripts
plugin/                  # Lightroom Classic plugin
```

### References
- MCP docs: https://modelcontextprotocol.io/docs
- Lightroom SDK samples
