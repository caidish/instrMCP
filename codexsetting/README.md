Codex CLI Setup for InstrMCP (STDIO proxy)

This folder contains a Codex-focused STDIO launcher that proxies to your HTTP MCP server at `http://127.0.0.1:8123/mcp`.
The launcher uses the shared proxy implementation in `instrmcp.utils.stdio_proxy`.

Usage
- Ensure your HTTP MCP server (instr_mcp) is running and reachable at the host/port you set (defaults: `127.0.0.1:8123`).
- Install this project into the Python env Codex will use: `pip install -e .` from the repo root.
- Configure Codex to launch an MCP server over STDIO using this command:
  - command: `python`
  - args: `["/path/to/instrMCP/codexsetting/codex_launcher.py"]`
  - env (recommended):
    - `JUPYTER_MCP_HOST=127.0.0.1`
    - `JUPYTER_MCP_PORT=8123`

Using the TOML config
- A ready-to-use MCP config is provided at `codexsetting/codex.mcp.toml`.
- Options to use it (adapt to your Codex version):
  - Merge: copy the `[mcp.servers.instr_mcp]` section into your main Codex config file.
  - Direct: if supported, point Codex to this file, e.g. `codex --mcp-config /path/to/instrMCP/codexsetting/codex.mcp.toml`.
- Paths: If your Codex does not expand `${...}`, replace with absolute paths in the TOML as noted in comments.
- Env: Ensure the Python used by Codex has this repo installed (`pip install -e .`).

Example (conceptual) config entry
- id: `instr_mcp`
- command: `python`
- args: `["${instrMCP_PATH}/codexsetting/codex_launcher.py"]`
- env:
  - `PYTHONPATH=${instrMCP_PATH}`
  - `instrMCP_PATH=${instrMCP_PATH}`
  - `JUPYTER_MCP_HOST=127.0.0.1`
  - `JUPYTER_MCP_PORT=8123`

Notes
- This launcher speaks STDIO to Codex and proxies MCP JSON-RPC calls to your HTTP MCP server, handling `initialize`, `notifications/initialized`, and `tools/*` calls.
- You can change the host/port via env vars without changing the command.
- If you want to tailor the client identity strings further (e.g., in the HTTP `initialize` handshake), we can inline the proxy instead of importing, but this version keeps maintenance minimal and separates Codex from the Claude Desktop setup.

Verify
- Start Codex and list tools (or ask: "What MCP tools are available?").
- You should see tools proxied from your HTTP server (e.g., `list_instruments`, `instrument_info`, ...).
