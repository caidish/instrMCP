# Gemini CLI Setup for InstrMCP

This folder contains the Gemini CLI configuration template for InstrMCP.

Gemini CLI uses the same STDIO launcher as Claude Desktop, proxying MCP requests to the Jupyter HTTP server.

## Quick Setup

1. Copy the template to your Gemini config directory:

```bash
mkdir -p ~/.gemini
cp agentsetting/geminisetting/settings.json ~/.gemini/settings.json
```

2. Edit `~/.gemini/settings.json` — replace placeholders with actual paths:
   - `/path/to/your/python` → your Python path (e.g., `which python`)
   - `/path/to/your/instrMCP` → your instrMCP directory (e.g., `~/GitHub/instrMCP`)

3. Start your Jupyter MCP server:

```bash
jupyter lab
# In a notebook cell:
# %load_ext instrmcp.extensions
# %mcp_start
```

4. Run Gemini CLI — it will connect via STDIO to the launcher.

## Configuration

```json
{
  "mcpServers": {
    "instrMCP": {
      "command": "/path/to/your/python",
      "args": ["/path/to/your/instrMCP/agentsetting/claudedesktopsetting/claude_launcher.py"],
      "env": {
        "instrMCP_PATH": "/path/to/your/instrMCP",
        "PYTHONPATH": "/path/to/your/instrMCP"
      },
      "trust": true
    }
  }
}
```

**Fields:**
- `command`: Full path to Python executable
- `args`: Path to the STDIO launcher script
- `env`: Environment variables for the launcher
- `trust`: Allow the MCP server to run without prompting

## How It Works

```
Gemini CLI ←→ STDIO ←→ claude_launcher.py ←→ stdio_proxy ←→ HTTP ←→ Jupyter MCP Server
```

The launcher reuses the shared STDIO-HTTP proxy in `instrmcp.utils.stdio_proxy`.

## Troubleshooting

**Gemini shows no tools:**
- Ensure Jupyter is running with the MCP extension loaded and started
- Check that `~/.gemini/settings.json` has correct absolute paths

**"spawn python ENOENT":**
- Use full path to Python executable in the `command` field
- Test: `/full/path/to/python --version`

**Launcher import errors:**
- Ensure instrMCP is installed: `pip install -e .`
- Check PYTHONPATH in the env section
