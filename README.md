## lrc-mcp

Minimal MCP server skeleton exposing a single tool `lrc_mcp_health` over stdio.

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

### Healthcheck
- **`lrc_mcp_health`**: basic health check for the MCP server. Returns structured output:

```json
{
  "status": "ok",
  "serverTime": "<UTC ISO-8601>",
  "version": "0.1.0"
}
```

### References
- MCP docs: https://modelcontextprotocol.io/docs


