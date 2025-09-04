# Claude Desktop Setup for QCoDeS MCP Servers

This guide shows you how to configure Claude Desktop to work with your QCoDeS instruments using the **STDIO transport** method that Claude Desktop requires for local MCP servers.

## Prerequisites

1. **Install Claude Desktop** (macOS/Windows)
2. **Install Python environment** with QCoDeS
3. **Activate your QCoDeS environment:**
   ```bash
   cd /Users/{your username}/GitHub/instrMCP
   source venv/bin/activate
   ```

## Configuration Steps

### 1. Open Claude Desktop Settings

1. Open Claude Desktop application
2. Navigate to **Settings** → **Developer** tab
3. Click **"Edit Config"** to open the configuration file

### 2. Configure MCP Servers

Add this configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jupyter-qcodes": {
      "command": "/Users/{your username}/GitHub/instrMCP/venv/bin/python",
      "args": [
        "/Users/{your username}/GitHub/instrMCP/servers/jupyter_qcodes/claude_launcher.py"
      ],
      "cwd": "/Users/{your username}/GitHub/instrMCP",
      "env": {
        "PYTHONPATH": "/Users/{your username}/GitHub/instrMCP",
        "JUPYTER_MCP_HOST": "127.0.0.1",
        "JUPYTER_MCP_PORT": "8123"
      }
    }
  }
}
```

**Important:** Update the paths to match your actual installation location.

**Finding your Python path:**

```bash
# Use your virtual environment's Python
ls /Users/{your username}/GitHub/instrMCP/venv/bin/python
```

Use the full path to your virtual environment's Python executable in the "command" field. This ensures all the required dependencies (QCoDeS, FastMCP, etc.) are available.

### 3. Save and Restart

1. **Save** the configuration file
2. **Restart Claude Desktop** completely
3. Look for the **MCP server indicator** in the bottom-right of the conversation input

## How It Works

The launcher script automatically detects your setup and chooses the best mode:

### Mode 1: Jupyter Proxy Mode (When Jupyter is Running)

**When detected:** If you have Jupyter Lab running with the MCP extension loaded
**What it does:** Acts as a proxy between Claude Desktop (STDIO) and your Jupyter server (HTTP)

**Setup:**
1. **Start Jupyter Lab:**
   ```bash
   cd /Users/{your username}/GitHub/instrMCP
   source venv/bin/activate
   jupyter lab
   ```

2. **Load the MCP extension in a notebook cell:**
   ```python
   %load_ext servers.jupyter_qcodes.jupyter_mcp_extension
   ```

3. **Start Claude Desktop** - the launcher will automatically detect and proxy to your Jupyter session

### Mode 2: Standalone Mode (When No Jupyter)

**When activated:** If no Jupyter server is detected on port 8123
**What it does:** Runs a limited MCP server directly without Jupyter integration

**Setup:**
1. **Just start Claude Desktop** - no Jupyter needed
2. The launcher automatically runs in standalone mode
3. Limited functionality with mock data

**Available Tools (Both Modes):**
- `list_instruments()` - List available QCoDeS instruments
- `instrument_info(name)` - Get detailed instrument information  
- `get_parameter_value(inst, param, fresh)` - Read parameter values
- `list_variables()` - List available variables
- `server_status()` - Check server mode and status

**Full Jupyter Mode Additional Tools:**
- `get_parameter_values(batch)` - Batch parameter reads
- `get_variable_info(name)` - Detailed variable information
- `subscribe_parameter(inst, param, interval)` - Monitor parameters
- `suggest_code(description)` - AI code suggestions
- `station_snapshot()` - Complete QCoDeS station snapshot
- `get_cache_stats()` - Parameter cache statistics

## Important Notes

- **Transport Method:** Uses STDIO transport for Claude Desktop compatibility
- **Auto-Detection:** Launcher automatically chooses between proxy and standalone modes  
- **Security:** All operations require explicit user approval
- **Read-Only:** Jupyter integration is read-only by default for safety
- **Rate Limiting:** Built-in protections prevent hardware damage

## Troubleshooting

### Check Logs

- **macOS:** `~/Library/Logs/Claude`
- **Windows:** `%APPDATA%\Claude\logs`

### Common Issues

**MCP Server Not Connecting:**

- Verify configuration file syntax is correct
- Check that Python path in config matches your installation
- Restart Claude Desktop completely
- Ensure Python environment has required dependencies

**Wrong Mode Detected:**

- Check if Jupyter is actually running on port 8123
- Verify Jupyter MCP extension is loaded: `%load_ext servers.jupyter_qcodes.jupyter_mcp_extension`
- Look for server status messages in Claude Desktop logs

**Instruments Not Available:**

- In Jupyter mode: Load your instruments in the Jupyter notebook first
- In standalone mode: Limited functionality is expected - use Jupyter mode for full features
- Verify `config/station.yaml` exists for instrument definitions

**Python Import Errors:**

- Check that PYTHONPATH in config includes the instrMCP directory
- Verify all dependencies are installed in your Python environment
- Ensure QCoDeS and FastMCP are properly installed

### Path Configuration

If you installed instrMCP in a different location, update the paths in the configuration:

```json
{
  "mcpServers": {
    "jupyter-qcodes": {
      "command": "/your/actual/path/to/instrMCP/venv/bin/python",
      "args": ["/your/actual/path/to/instrMCP/servers/jupyter_qcodes/claude_launcher.py"],
      "cwd": "/your/actual/path/to/instrMCP",
      "env": {
        "PYTHONPATH": "/your/actual/path/to/instrMCP"
      }
    }
  }
}
```

## Security Considerations

- **User Approval Required:** All file operations and instrument commands require explicit approval
- **STDIO Transport:** Uses secure local communication (no network ports exposed)
- **Read-Only Mode:** Jupyter integration provides safe, read-only access by default
- **Rate Limiting:** Built-in protections prevent rapid instrument polling that could damage hardware
- **Process Isolation:** Launcher runs in isolated Python environment

Follow the principle of **explicit approval** - carefully review each proposed action before approving.
