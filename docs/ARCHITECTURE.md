# Architecture

This document describes the technical architecture of InstrMCP, including package structure, communication flows, and integration patterns.

## Package Structure

```
instrmcp/
├── servers/           # MCP server implementations
│   ├── jupyter_qcodes/ # Jupyter integration with QCodes instrument access
│   │   ├── mcp_server.py      # FastMCP server implementation (870 lines)
│   │   ├── tools.py           # QCodes read-only tools and Jupyter integration (35KB)
│   │   ├── tools_unsafe.py    # Unsafe mode tools with registrar pattern (130 lines)
│   │   └── cache.py           # Caching and rate limiting for QCodes parameter reads
│   └── qcodes/        # Standalone QCodes station server
├── extensions/        # Jupyter/IPython extensions
│   ├── jupyterlab/    # JupyterLab extension for active cell bridging
│   ├── database/      # Database integration tools and resources
│   └── MeasureIt/     # MeasureIt template resources
├── tools/             # Helper utilities
│   └── stdio_proxy.py # STDIO↔HTTP proxy for Claude Desktop/Codex integration
├── config/            # Configuration management
│   └── data/          # YAML station configuration files
└── cli.py             # Main command-line interface
```

## Core Components

### MCP Servers

**`servers/jupyter_qcodes/`** - Main Jupyter integration server
- `mcp_server.py`: FastMCP server implementation
- `tools.py`: QCodes read-only tools and Jupyter integration
- `tools_unsafe.py`: Unsafe mode tools (cell execution, manipulation)
- `cache.py`: Thread-safe caching and rate limiting

**`servers/qcodes/`** - Standalone QCodes station server
- Independent server for QCodes instrument control
- Can run separately from Jupyter

### Communication Architecture

```
Claude Desktop/Code ←→ STDIO ←→ claude_launcher.py ←→ stdio_proxy.py ←→ HTTP ←→ Jupyter MCP Server
```

The system uses a proxy pattern:
1. External clients (Claude Desktop, Claude Code, Codex) communicate via STDIO
2. Launchers (`claudedesktopsetting/claude_launcher.py`, `codexsetting/codex_launcher.py`) bridge STDIO to HTTP
3. The actual MCP server runs as an HTTP server within Jupyter

### QCodes Integration

- **Lazy Loading**: Instruments loaded on-demand for safety
- **Professional Drivers**: Full QCodes driver ecosystem support
- **Hierarchical Parameters**: Support for nested parameter access (e.g., `ch01.voltage`)
- **Caching System**: `cache.py` prevents excessive instrument reads
- **Rate Limiting**: Protects instruments from command flooding

### Jupyter Integration

- **IPython Event Hooks**: Real-time tracking of cell execution
- **Active Cell Bridge**: JupyterLab extension for current cell access
- **Kernel Variables**: Direct access to notebook namespace
- **Cell Output Capture**: Retrieves output from most recently executed cell

## MCP Tools Available

All tools now use hierarchical naming with `/` separator for better organization.

### QCodes Instrument Tools (`qcodes/*`)

- `qcodes/instrument_info(name, with_values)` - Get instrument details and parameter values
- `qcodes/get_parameter_values(queries)` - Read parameter values (supports both single and batch queries)

### Jupyter Notebook Tools (`notebook/*`)

- `notebook/list_variables(type_filter)` - List notebook variables by type
- `notebook/get_variable_info(name)` - Detailed variable information
- `notebook/get_editing_cell(fresh_ms)` - Current JupyterLab cell content
- `notebook/update_editing_cell(content)` - Update current cell content
- `notebook/get_editing_cell_output()` - Get output of most recently executed cell
- `notebook/get_notebook_cells(num_cells, include_output)` - Get recent notebook cells
- `notebook/server_status()` - Check server mode and status

### Unsafe Notebook Tools (`notebook/*` - unsafe mode only)

- `notebook/execute_cell()` - Execute current cell
- `notebook/add_cell(cell_type, position, content)` - Add new cell relative to active cell
- `notebook/delete_cell()` - Delete the currently active cell
- `notebook/apply_patch(old_text, new_text)` - Apply text replacement patch to active cell

### MeasureIt Integration Tools (`measureit/*` - requires `%mcp_option measureit`)

- `measureit/get_status()` - Check if any MeasureIt sweep is currently running
- `measureit/wait_for_sweep(variable_name)` - Wait for the given sweep to finish
- `measureit/wait_for_all_sweeps()` - Wait for all currently running sweeps to finish

### Database Integration Tools (`database/*` - requires `%mcp_option database`)

- `database/list_experiments(database_path)` - List all experiments in the specified QCodes database
- `database/get_dataset_info(id, database_path)` - Get detailed information about a specific dataset
- `database/get_database_stats(database_path)` - Get database statistics and health information

**Note**: All database tools accept an optional `database_path` parameter. If not provided, they default to `$MeasureItHome/Databases/Example_database.db` when MeasureIt is available, otherwise use QCodes configuration.

## MCP Resources Available

### QCodes Resources

- `available_instruments` - JSON list of available QCodes instruments with hierarchical parameter structure
- `station_state` - Current QCodes station snapshot without parameter values

### Jupyter Resources

- `notebook_cells` - All notebook cell contents

### MeasureIt Resources (Optional - requires `%mcp_option measureit`)

- `measureit_sweep0d_template` - Sweep0D code examples and patterns for time-based monitoring
- `measureit_sweep1d_template` - Sweep1D code examples and patterns for single parameter sweeps
- `measureit_sweep2d_template` - Sweep2D code examples and patterns for 2D parameter mapping
- `measureit_simulsweep_template` - SimulSweep code examples for simultaneous parameter sweeping
- `measureit_sweepqueue_template` - SweepQueue code examples for sequential measurement workflows
- `measureit_common_patterns` - Common MeasureIt patterns and best practices
- `measureit_code_examples` - Complete collection of ALL MeasureIt patterns in structured format

### Database Resources (Optional - requires `%mcp_option database`)

- `database_config` - Current QCodes database configuration, path, and connection status
- `recent_measurements` - Metadata for recent measurements across all experiments

## Optional Features and Magic Commands

The server supports optional features that can be enabled/disabled via magic commands:

### Safe/Unsafe Mode

- `%mcp_safe` - Switch to safe mode (read-only access)
- `%mcp_unsafe` - Switch to unsafe mode (allows cell manipulation and code execution)

### Unsafe Mode Tools

Only available when `%mcp_unsafe` is active:

- `notebook/execute_cell()` - Execute code in the active cell
- `notebook/add_cell(cell_type, position, content)` - Add new cells to the notebook
  - `cell_type`: "code", "markdown", or "raw" (default: "code")
  - `position`: "above" or "below" active cell (default: "below")
  - `content`: Initial cell content (default: empty)
- `notebook/delete_cell()` - Delete the active cell (clears content if last cell)
- `notebook/apply_patch(old_text, new_text)` - Replace text in active cell
  - More efficient than `notebook_update_editing_cell` for small changes
  - Replaces first occurrence of `old_text` with `new_text`

### Optional Features

- `%mcp_option measureit` - Enable MeasureIt template resources
- `%mcp_option -measureit` - Disable MeasureIt template resources
- `%mcp_option database` - Enable database integration tools and resources
- `%mcp_option -database` - Disable database integration tools and resources
- `%mcp_option` - Show current option status

### Server Control

- `%mcp_start` - Start the MCP server
- `%mcp_stop` - Stop the MCP server
- `%mcp_restart` - Restart server (required after mode/option changes)
- `%mcp_status` - Show server status and available commands

**Note:** Server restart is required after changing modes or options for changes to take effect.

## Configuration

### Station Configuration

Station configuration uses standard YAML format:

```yaml
# instrmcp/config/data/default_station.yaml
instruments:
  mock_dac:
    driver: qcodes.instrument_drivers.mock.MockDAC
    name: mock_dac_1
    enable: true
```

### Environment Variables

- `instrMCP_PATH`: Must be set to the instrMCP installation directory
- `JUPYTER_MCP_HOST`: MCP server host (default: 127.0.0.1)
- `JUPYTER_MCP_PORT`: MCP server port (default: 8123)

### Configuration Files

- System config: `instrmcp/config/data/`
- User config: `~/.instrmcp/config.yaml` (optional)
- Auto-detection via: `instrmcp config`

## Integration Patterns

### Claude Desktop Integration

```json
{
  "mcpServers": {
    "instrmcp-jupyter": {
      "command": "/path/to/your/python3",
      "args": ["/path/to/your/instrMCP/claudedesktopsetting/claude_launcher.py"],
      "env": {
        "PYTHONPATH": "/path/to/your/instrMCP",
        "instrMCP_PATH": "/path/to/your/instrMCP",
        "JUPYTER_MCP_HOST": "127.0.0.1",
        "JUPYTER_MCP_PORT": "8123"
      }
    }
  }
}
```

### Claude Code Integration

```bash
claude mcp add instrMCP --env instrMCP_PATH=$instrMCP_PATH \
  --env PYTHONPATH=$instrMCP_PATH \
  -- $instrMCP_PATH/venv/bin/python \
  $instrMCP_PATH/claudedesktopsetting/claude_launcher.py
```

### Codex CLI Integration

- Command: `python`
- Args: `["/path/to/your/instrMCP/codexsetting/codex_launcher.py"]`
- Env:
  - `JUPYTER_MCP_HOST=127.0.0.1`
  - `JUPYTER_MCP_PORT=8123`

## Communication Flows

### STDIO-based Clients (Claude Desktop, Claude Code, Codex)

```
Client ←→ STDIO ←→ Launcher ←→ stdio_proxy.py ←→ HTTP ←→ Jupyter MCP Server
```

1. Client sends MCP request over STDIO
2. Launcher receives request and forwards to stdio_proxy
3. stdio_proxy converts STDIO to HTTP request
4. HTTP server in Jupyter processes request
5. Response flows back through the same chain

### Direct HTTP Clients

```
Client ←→ HTTP ←→ Jupyter MCP Server
```

Direct connection to the HTTP server running in Jupyter.
