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
Create a `.env` file from the example and adjust values as needed:
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

### Tools
- `lrc_mcp_health`: basic health check for the MCP server. Returns structured output: `{ status, serverTime, version }`.
- `lrc_launch_lightroom`: launch Lightroom Classic (Windows). Optional `path` input; otherwise uses `LRCLASSIC_PATH` or default install path. Returns `{ launched, pid, path }`.
- `lrc_lightroom_version`: returns `{ status: "ok"|"waiting", lr_version, last_seen }` based on plugin heartbeat.

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
1) In Lightroom Classic: File → Plug‑in Manager → Add… → select `plugin/lrc_mcp.lrplugin`.
2) The plugin runs background tasks that (a) post heartbeats and (b) poll for commands, supporting minimal `noop` and `echo` commands.
3) Optional: place a raw token string at `%APPDATA%/lrc-mcp/config.json` to authenticate requests when `LRC_MCP_PLUGIN_TOKEN` is set.

After the plugin loads and the server is running, you should see periodic heartbeat logs in the plugin log and server logs. For Step 4, you can enqueue a test `noop` or `echo` command using a temporary script or the soon-to-be-added MCP tools in later steps.
### References
- MCP docs: https://modelcontextprotocol.io/docs
 - Lightroom SDK samples: `./resources/LrC_14.3_202504141032-10373aad.release_SDK`




