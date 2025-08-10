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

### References
- MCP docs: https://modelcontextprotocol.io/docs
 - Lightroom SDK samples: `./resources/LrC_14.3_202504141032-10373aad.release_SDK`


