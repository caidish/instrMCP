# Claude Desktop Setup for QCoDeS MCP Servers

This guide shows you how to configure Claude Desktop to work with your QCoDeS instruments.

## Two Usage Options

### Option 1: Standalone QCoDeS Server (Recommended for dedicated instrument control)

This runs a standalone MCP server with QCoDeS instruments loaded from your configuration.

**Claude Desktop Configuration:**
Add this to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qcodes-standalone": {
      "command": "python",
      "args": ["-m", "servers.qcodes.server", "--host", "127.0.0.1", "--port", "8000"],
      "cwd": "/Users/caijiaqi/GitHub/instrMCP",
      "env": {
        "PYTHONPATH": "/Users/caijiaqi/GitHub/instrMCP",
        "STATION_YAML": "/Users/caijiaqi/GitHub/instrMCP/config/station.yaml"
      }
    }
  }
}
```

**Usage:**
1. Make sure your QCoDeS environment is activated
2. Start Claude Desktop
3. The server auto-loads all instruments from `config/station.yaml`
4. Claude has full access to instrument control

**Available Tools:**
- `all_instr_health()` - Get health status of all instruments
- `inst_health(name)` - Get specific instrument status  
- `load_instrument(name)` - Load an instrument
- `close_instrument(name)` - Close an instrument connection
- `reconnect_instrument(name)` - Reconnect an instrument
- `station_info()` - Get station information

---

### Option 2: Jupyter Integration (Recommended for interactive analysis)

This runs an MCP server inside your Jupyter session with read-only access to your workspace.

**Setup Steps:**

1. **Start Jupyter Lab/Notebook:**
   ```bash
   cd /Users/caijiaqi/GitHub/instrMCP
   source venv/bin/activate
   jupyter lab
   ```

2. **In your Jupyter notebook, load the extension:**
   ```python
   %load_ext servers.jupyter_qcodes.jupyter_mcp_extension
   ```

3. **The MCP server starts automatically on `http://127.0.0.1:8123`**

4. **Connect Claude Desktop to the running server:**
   - Use the web interface or API to connect to `127.0.0.1:8123`
   - Or add a client configuration (see below)

**Available Tools:**
- `list_instruments()` - List all QCoDeS instruments
- `instrument_info(name)` - Get instrument details
- `get_parameter_value(inst, param, fresh)` - Read parameter values
- `get_parameter_values(batch)` - Batch parameter reads
- `list_variables()` - List Jupyter namespace variables
- `get_variable_info(name)` - Variable information
- `subscribe_parameter(inst, param, interval)` - Monitor parameters
- `suggest_code(description)` - AI code suggestions
- `station_snapshot()` - Full station snapshot
- `server_status()` - Server information

---

## Claude Desktop Config File Locations

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

---

## Example Complete Configuration

Here's a complete `claude_desktop_config.json` with both options:

```json
{
  "mcpServers": {
    "qcodes-standalone": {
      "command": "python",
      "args": ["-m", "servers.qcodes.server"],
      "cwd": "/Users/caijiaqi/GitHub/instrMCP",
      "env": {
        "PYTHONPATH": "/Users/caijiaqi/GitHub/instrMCP"
      }
    }
  }
}
```

**Note:** The Jupyter integration doesn't need a Claude Desktop config entry because it runs inside your Jupyter session. You connect to it directly via the web interface or API.

---

## Troubleshooting

### Standalone Server Issues:
- **Server won't start:** Check that your Python environment has QCoDeS installed
- **Instruments not loading:** Verify your `config/station.yaml` file
- **Permission errors:** Make sure the working directory is accessible

### Jupyter Integration Issues:
- **Extension won't load:** Check that the extension is in your Python path
- **Server not starting:** Look for error messages in Jupyter console
- **Can't connect:** Verify the server is running on port 8123

### General Issues:
- **Path problems:** Update the `cwd` and `PYTHONPATH` to match your installation
- **Port conflicts:** Change the port numbers if they're already in use
- **Import errors:** Make sure all dependencies are installed in your environment

---

## Security Notes

- Both servers bind to `127.0.0.1` (localhost only) for security
- The Jupyter integration is read-only by default
- The standalone server has full instrument control capabilities
- Use access tokens and authentication for production environments