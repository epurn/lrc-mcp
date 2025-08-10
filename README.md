## lrc-mcp

MCP server exposing tools over stdio and a local HTTP heartbeat endpoint for a Lightroom Classic plugin.

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
- **`lrc_mcp_health`**: basic health check for the MCP server. Returns structured output:

```json
{
  "status": "ok",
  "serverTime": "<UTC ISO-8601>",
  "version": "0.1.0"
}
```

- **`lrc_launch_lightroom`**: launch Lightroom Classic (Windows). Optional `path` input; otherwise uses `LRCLASSIC_PATH` or default install path. Returns `{ launched, pid, path }`.
- **`lrc_lightroom_version`**: returns `{ status: "ok"|"waiting", lr_version, last_seen }` based on plugin heartbeat.

### Lightroom plugin setup
1) In Lightroom Classic: File → Plug‑in Manager → Add… → select `plugin/lrc_mcp.lrplugin`.
2) The plugin starts a background task and posts heartbeats to `http://127.0.0.1:${LRC_MCP_HTTP_PORT}/plugin/heartbeat`.
3) Optional: place a raw token string at `%APPDATA%/lrc-mcp/config.json` to authenticate heartbeats when `LRC_MCP_PLUGIN_TOKEN` is set.

After the plugin loads and the server is running, invoke `lrc_lightroom_version` to see the reported Lightroom version. If Lightroom is not running, use `lrc_launch_lightroom` first.

### References
- MCP docs: https://modelcontextprotocol.io/docs
 - Lightroom SDK samples: `./resources/LrC_14.3_202504141032-10373aad.release_SDK`


