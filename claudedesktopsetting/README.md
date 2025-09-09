# Claude Desktop Configuration

This directory contains Claude Desktop launcher and configuration files for InstrMCP.

## Files

- `claude_launcher.py`: STDIO transport launcher for Claude Desktop
- `claude_desktop_config.json`: Sample configuration template  
- `setup_claude.sh`: Automated setup script
- `README.md`: This documentation

## Quick Setup

**Automated (Recommended):**
```bash
cd /path/to/instrMCP
./claudedesktopsetting/setup_claude.sh
```

**Manual Setup:**
```bash
# 1. Copy template
cp claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json

# 2. Edit copied file - replace placeholders:
#    /path/to/your/python3 → /usr/bin/python3 (or your path)
#    /path/to/your/instrMCP → /Users/you/instrMCP (or your path)

# 3. Restart Claude Desktop
```

## Configuration Template Explained

```json
{
  "mcpServers": {
    "instrmcp-jupyter": {
      "command": "/path/to/your/python3",         // Full Python path (required)
      "args": ["/path/to/your/instrMCP/..."],     // Full script path (required)  
      "env": {                                    // Environment variables
        "PYTHONPATH": "/path/to/your/instrMCP",   // For Python imports
        "instrMCP_PATH": "/path/to/your/instrMCP", // For station config
        "JUPYTER_MCP_HOST": "127.0.0.1",
        "JUPYTER_MCP_PORT": "8123"
      }
    }
  }
}
```

**⚠️ Important Notes:**
- Claude Desktop requires **absolute paths** - no environment variable expansion
- Use full path to Python executable to avoid `spawn python ENOENT` errors
- The `env` section works for runtime environment variables

## How It Works

**Architecture:**
```
Claude Desktop ←→ STDIO ←→ claude_launcher.py ←→ (instrmcp.tools.stdio_proxy) ←→ HTTP ←→ Jupyter MCP Server
```

**Mode Detection:**
- **Full Mode**: When Jupyter + MCP server running → complete functionality
- **Standalone Mode**: When Jupyter not running → mock data access

**Features:**
- Automatic fallback between modes
- Clean STDIO communication for Claude Desktop
- Shared STDIO↔HTTP proxy (no duplication) to existing Jupyter servers
- Error handling and logging

## Troubleshooting

**Setup script fails:**
- Check you're in instrMCP root directory
- Verify Python is in PATH: `which python3`

**Claude Desktop shows no tools:**
- Restart Claude Desktop completely (not just reload)
- Check config file exists with absolute paths
- Verify Python path is accessible

**"spawn python ENOENT":**
- Use full Python path in config `command` field
- Test: `/full/path/to/python3 --version`

**Launcher import errors:**
- Ensure InstrMCP installed: `pip install -e .`
- Check PYTHONPATH in config

**Check your setup:**
```bash
# Verify config file
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Test Python path
/your/python/path --version

# Test launcher directly
/your/python/path /path/to/claude_launcher.py
```
