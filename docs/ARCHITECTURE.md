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

### Unified QCodes Meta-Tool

The QCodes functionality is consolidated into a single `qcodes(action=...)` meta-tool with 2 actions.

**Usage:** `qcodes(action="<action_name>", ...params)`

| Action | Parameters | Description |
|--------|------------|-------------|
| `instrument_info` | `name` (required), `with_values` (optional) | Get instrument details; use `name="*"` to list all |
| `get_values` | `queries` (required, JSON) | Read parameter values (single or batch queries) |

**Examples:**
```python
# List all instruments
qcodes(action="instrument_info", name="*")

# Get specific instrument with current values
qcodes(action="instrument_info", name="lockin", with_values=True)

# Single parameter query
qcodes(action="get_values", queries='{"instrument": "lockin", "parameter": "X"}')

# Batch query
qcodes(action="get_values", queries='[{"instrument": "lockin", "parameter": "X"}, {"instrument": "lockin", "parameter": "Y"}]')

# Fresh read (bypass cache)
qcodes(action="get_values", queries='{"instrument": "dac", "parameter": "ch01.voltage", "fresh": true}')
```

### Unified Notebook Meta-Tool

The notebook functionality is consolidated into a single `notebook(action=...)` meta-tool with 13 actions.
This reduces context window overhead by ~2,500 tokens compared to 13 separate tools.

**Usage:** `notebook(action="<action_name>", ...params)`

**Safe Actions (available in all modes):**

| Action | Parameters | Description |
|--------|------------|-------------|
| `list_variables` | `type_filter` (optional) | List notebook variables by type |
| `get_variable_info` | `name` (required) | Detailed variable information |
| `get_editing_cell` | `fresh_ms`, `line_start`, `line_end`, `max_lines` | Current JupyterLab cell content |
| `get_editing_cell_output` | (none) | Get output of most recently executed cell |
| `get_notebook_cells` | `num_cells`, `include_output` | Get recent notebook cells |
| `move_cursor` | `target` (required: "above", "below", "bottom", or number) | Navigate to different cell |
| `server_status` | (none) | Check server mode and status |

**Unsafe Actions (require unsafe mode + consent):**

| Action | Parameters | Consent | Description |
|--------|------------|---------|-------------|
| `update_editing_cell` | `content` (required) | YES | Update current cell content |
| `execute_cell` | (none) | YES | Execute current cell |
| `add_cell` | `cell_type`, `position`, `content` | NO | Add new cell relative to active cell |
| `delete_cell` | (none) | YES | Delete the currently active cell |
| `delete_cells` | `cell_numbers` (required, JSON) | YES | Delete multiple cells by number |
| `apply_patch` | `old_text`, `new_text` (required) | YES | Apply text replacement patch |

**Examples:**
```python
# Safe mode examples
notebook(action="list_variables", type_filter="array")
notebook(action="get_editing_cell", fresh_ms=500, line_start=1, line_end=10)
notebook(action="move_cursor", target="below")
notebook(action="server_status")

# Unsafe mode examples (require consent)
notebook(action="execute_cell")
notebook(action="update_editing_cell", content="print('hello')")
notebook(action="add_cell", cell_type="code", position="below", content="x = 1")
notebook(action="delete_cells", cell_numbers="[1, 2, 5]")
notebook(action="apply_patch", old_text="old", new_text="new")
```

### MeasureIt Integration Tools (requires `%mcp_option measureit`)

- `measureit_get_status()` - Check if any MeasureIt sweep is currently running
- `measureit_wait_for_sweep(variable_name)` - Wait for the given sweep to finish
- `measureit_wait_for_all_sweeps()` - Wait for all currently running sweeps to finish

### Unified Database Meta-Tool (requires `%mcp_option database`)

The database functionality is consolidated into a single `database(action=...)` meta-tool with 4 actions.

**Usage:** `database(action="<action_name>", ...params)`

| Action | Parameters | Description |
|--------|------------|-------------|
| `list_experiments` | `database_path` (optional) | List all experiments in database |
| `get_dataset` | `id` (required), `database_path` (optional) | Get dataset details by run ID |
| `stats` | `database_path` (optional) | Database statistics and health |
| `list_available` | (none) | List all available database files |

**Database Path Resolution** (when `database_path` is not specified):
1. MeasureIt default: `$MeasureItHome/Databases/Example_database.db`
2. QCodes config: `qc.config.core.db_location`
3. Error with suggestions if neither exists

**Examples:**
```python
# List experiments in default database
database(action="list_experiments")

# List experiments in specific database
database(action="list_experiments", database_path="/path/to/experiments.db")

# Get dataset details
database(action="get_dataset", id=5)

# Get database statistics
database(action="stats")

# List all available databases
database(action="list_available")
```

### Unified Dynamic Meta-Tool (unsafe mode only)

The dynamic tool functionality is consolidated into a single `dynamic(action=...)` meta-tool with 6 actions.
This allows runtime creation of custom MCP tools with LLM-powered registration.

**Usage:** `dynamic(action="<action_name>", ...params)`

**Safe Actions (available in all modes):**

| Action | Parameters | Description |
|--------|------------|-------------|
| `list` | `tag`, `capability`, `author` (all optional) | List registered tools with filtering |
| `inspect` | `name` (required) | Get full tool specification including source |
| `stats` | (none) | Registry statistics (total, by author, by capability) |

**Unsafe Actions (require unsafe mode):**

| Action | Parameters | Consent | Description |
|--------|------------|---------|-------------|
| `register` | `name`, `source_code` (required) | YES | Register a new tool |
| `update` | `name`, `version` (required) | YES | Update existing tool |
| `revoke` | `name` (required), `reason` (optional) | NO | Delete tool permanently |

**Tool Registration Parameters:**
- `name` (required): Tool name (snake_case, max 64 chars)
- `source_code` (required): Python function source code
- `version` (optional): Semantic version (default: "1.0.0")
- `description` (optional): Tool description
- `author` (optional): Author identifier (default: "unknown")
- `capabilities` (optional): JSON array of capability labels
- `parameters` (optional): JSON array of parameter specs
- `returns` (optional): JSON object with return type spec
- `examples` (optional): JSON array of usage examples
- `tags` (optional): JSON array of searchable tags

**Examples:**
```python
# List all registered tools
dynamic(action="list")

# List tools by author
dynamic(action="list", author="me")

# Inspect a tool
dynamic(action="inspect", name="my_tool")

# Get registry statistics
dynamic(action="stats")

# Register a new tool (consent required)
dynamic(action="register",
        name="add_nums",
        source_code="def add_nums(a, b): return a + b")

# Update a tool (consent required)
dynamic(action="update",
        name="add_nums",
        version="1.1.0",
        source_code="def add_nums(a, b, c=0): return a + b + c")

# Revoke a tool (no consent required)
dynamic(action="revoke", name="old_tool", reason="No longer needed")
```

**Note:** Dynamic tools persist in `~/.instrmcp/registry/` and are automatically reloaded on server start.

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

### Safe/Unsafe/Dangerous Mode

- `%mcp_safe` - Switch to safe mode (read-only access)
- `%mcp_unsafe` - Switch to unsafe mode (allows cell manipulation and code execution)
- `%mcp_dangerous` - Switch to dangerous mode (all consent dialogs auto-approved)

| Mode | Command | Tools Available | Consent Required |
|------|---------|-----------------|------------------|
| Safe | `%mcp_safe` | Read-only tools | N/A |
| Unsafe | `%mcp_unsafe` | All tools | Yes |
| Dangerous | `%mcp_dangerous` | All tools | No (auto-approved) |

### Unsafe Mode Actions

The following notebook actions are only available when `%mcp_unsafe` or `%mcp_dangerous` is active:

| Action | Consent | Description |
|--------|---------|-------------|
| `notebook(action="execute_cell")` | YES | Execute code in the active cell |
| `notebook(action="update_editing_cell", content="...")` | YES | Replace entire cell content |
| `notebook(action="add_cell", cell_type="code", position="below")` | NO | Add new cell above/below active cell |
| `notebook(action="delete_cell")` | YES | Delete the active cell |
| `notebook(action="delete_cells", cell_numbers="[1,2]")` | YES | Delete multiple cells by index |
| `notebook(action="apply_patch", old_text="...", new_text="...")` | YES | Find/replace text in active cell |

**Consent behavior:**
- **Unsafe mode**: Actions marked "YES" show approval dialog
- **Dangerous mode**: All consents auto-approved (bypass mode)

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

## Server Lifecycle & Troubleshooting

### MCP Server Lifecycle

The MCP server runs as an HTTP server within the Jupyter kernel process using uvicorn:

1. **Start**: Creates uvicorn Server instance with `install_signal_handlers = lambda: None` to prevent interference with ipykernel's ZMQ event loop
2. **Run**: Server runs in an asyncio task via `uvicorn.Server.serve()`
3. **Stop**: Sets `server.should_exit = True` for graceful shutdown, then cancels the task

**Important**: The signal handler override is critical - without it, repeated start/stop cycles corrupt ipykernel's ZMQ sockets.

### Logging System

Logs are stored in `~/.instrmcp/`:

```
~/.instrmcp/
├── logs/
│   ├── mcp.log              # Main server log (rotating, 10MB max)
│   ├── mcp_debug.log        # Debug log (when enabled)
│   └── tool_calls.log       # Tool invocations with timing
├── audit/
│   └── tool_audit.log       # Dynamic tool lifecycle
└── logging.yaml             # Configuration (optional)
```

Logger namespace: all loggers use lowercase `instrmcp.*` (legacy mixed-case names still map here).

**Enable debug logging**: Create/edit `~/.instrmcp/logging.yaml`:
```yaml
debug_enabled: true
```

### Common Issues

#### "Socket operation on non-socket" Error

**Cause**: ZMQ socket corruption from improper uvicorn shutdown.

**Solution**: This was fixed by disabling uvicorn's signal handlers. If you encounter this error:
1. Click the "Reset" button in the toolbar
2. If that fails, restart the kernel

#### Toolbar Shows "Stopped" But Server Won't Start

**Cause**: Stale state after kernel restart.

**Solution**: Click the "Reset" button to reconnect the toolbar comm.

#### Tool Calls Not Appearing in Logs

**Cause**: `tool_logging` disabled or logger not initialized.

**Solution**: Ensure `~/.instrmcp/logging.yaml` has `tool_logging: true` (default) and restart the kernel.
