# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Environment Setup:**
```bash
# Always use conda environment instrMCPdev for testing
conda activate instrMCPdev
```

**Package Management:**
```bash
# Install for development
pip install -e .

# Install with development dependencies
pip install -e .[dev]

# Build package
python -m build

# Test installation
instrmcp version
```

**Code Quality:**
```bash
# Format code
black instrmcp/ tests/

# Type checking
mypy instrmcp/

# Linting
flake8 instrmcp/

# Run tests
pytest
pytest -v  # verbose output
pytest --cov=instrmcp  # with coverage
```

**Server Management:**
```bash
# Start Jupyter MCP server
instrmcp jupyter --port 3000
instrmcp jupyter --port 3000 --unsafe  # with code execution

# Start QCodes station server
instrmcp qcodes --port 3001

# Show configuration
instrmcp config
```

## Architecture Overview

### Core Components

**MCP Servers (`instrmcp/servers/`):**
- `jupyter_qcodes/`: Main Jupyter integration server with QCodes instrument access
- `qcodes/`: Standalone QCodes station server

**Key Files:**
- `instrmcp/servers/jupyter_qcodes/mcp_server.py`: FastMCP server implementation (870 lines)
- `instrmcp/servers/jupyter_qcodes/tools.py`: QCodes read-only tools and Jupyter integration (35KB)
- `instrmcp/servers/jupyter_qcodes/tools_unsafe.py`: Unsafe mode tools with registrar pattern (130 lines)
- `instrmcp/tools/stdio_proxy.py`: STDIO↔HTTP proxy for Claude Desktop/Codex integration
- `instrmcp/cli.py`: Main command-line interface

### Communication Architecture

```
Claude Desktop/Code ←→ STDIO ←→ claude_launcher.py ←→ stdio_proxy.py ←→ HTTP ←→ Jupyter MCP Server
```

The system uses a proxy pattern where:
1. External clients (Claude Desktop, Claude Code, Codex) communicate via STDIO
2. Launchers (`claudedesktopsetting/claude_launcher.py`, `codexsetting/codex_launcher.py`) bridge STDIO to HTTP
3. The actual MCP server runs as an HTTP server within Jupyter

### MCP Tools Available

All tools now use hierarchical naming with `/` separator for better organization.

**QCodes Instrument Tools (`qcodes/*`):**
- `qcodes/instrument_info(name, with_values)` - Get instrument details and parameter values
- `qcodes/get_parameter_values(queries)` - Read parameter values (supports both single and batch queries)

**Jupyter Notebook Tools (`notebook/*`):**
- `notebook/list_variables(type_filter)` - List notebook variables by type
- `notebook/get_variable_info(name)` - Detailed variable information
- `notebook/get_editing_cell(fresh_ms)` - Current JupyterLab cell content
- `notebook/update_editing_cell(content)` - Update current cell content
- `notebook/get_editing_cell_output()` - Get output of most recently executed cell
- `notebook/get_notebook_cells(num_cells, include_output)` - Get recent notebook cells
- `notebook/server_status()` - Check server mode and status

**Unsafe Notebook Tools (`notebook/*` - unsafe mode only):**
- `notebook/execute_cell()` - Execute current cell
- `notebook/add_cell(cell_type, position, content)` - Add new cell relative to active cell
- `notebook/delete_cell()` - Delete the currently active cell
- `notebook/apply_patch(old_text, new_text)` - Apply text replacement patch to active cell

**MeasureIt Integration Tools (`measureit/*` - requires `%mcp_option measureit`):**
- `measureit/get_status()` - Check if any MeasureIt sweep is currently running, returns sweep status and configuration

**Database Integration Tools (`database/*` - requires `%mcp_option database`):**
- `database/list_experiments(database_path)` - List all experiments in the specified QCodes database
- `database/get_dataset_info(id, database_path)` - Get detailed information about a specific dataset
- `database/get_database_stats(database_path)` - Get database statistics and health information

**Note**: All database tools accept an optional `database_path` parameter. If not provided, they default to `$MeasureItHome/Databases/Example_database.db` when MeasureIt is available, otherwise use QCodes configuration.

### MCP Resources Available

**QCodes Resources:**
- `available_instruments` - JSON list of available QCodes instruments with hierarchical parameter structure
- `station_state` - Current QCodes station snapshot without parameter values

**Jupyter Resources:**
- `notebook_cells` - All notebook cell contents

**MeasureIt Resources (Optional - requires `%mcp_option measureit`):**
- `measureit_sweep0d_template` - Sweep0D code examples and patterns for time-based monitoring
- `measureit_sweep1d_template` - Sweep1D code examples and patterns for single parameter sweeps
- `measureit_sweep2d_template` - Sweep2D code examples and patterns for 2D parameter mapping
- `measureit_simulsweep_template` - SimulSweep code examples for simultaneous parameter sweeping
- `measureit_sweepqueue_template` - SweepQueue code examples for sequential measurement workflows
- `measureit_common_patterns` - Common MeasureIt patterns and best practices
- `measureit_code_examples` - Complete collection of ALL MeasureIt patterns in structured format

**Database Resources (Optional - requires `%mcp_option database`):**
- `database_config` - Current QCodes database configuration, path, and connection status
- `recent_measurements` - Metadata for recent measurements across all experiments

### Optional Features and Magic Commands

The server supports optional features that can be enabled/disabled via magic commands:

**Safe/Unsafe Mode:**
- `%mcp_safe` - Switch to safe mode (read-only access)
- `%mcp_unsafe` - Switch to unsafe mode (allows cell manipulation and code execution)

**Unsafe Mode Tools (Only available when `%mcp_unsafe` is active):**
- `notebook/execute_cell()` - Execute code in the active cell
- `notebook/add_cell(cell_type, position, content)` - Add new cells to the notebook
  - `cell_type`: "code", "markdown", or "raw" (default: "code")
  - `position`: "above" or "below" active cell (default: "below")
  - `content`: Initial cell content (default: empty)
- `notebook/delete_cell()` - Delete the active cell (clears content if last cell)
- `notebook/apply_patch(old_text, new_text)` - Replace text in active cell
  - More efficient than `notebook_update_editing_cell` for small changes
  - Replaces first occurrence of `old_text` with `new_text`

**Optional Features:**
- `%mcp_option measureit` - Enable MeasureIt template resources
- `%mcp_option -measureit` - Disable MeasureIt template resources
- `%mcp_option database` - Enable database integration tools and resources
- `%mcp_option -database` - Disable database integration tools and resources
- `%mcp_option` - Show current option status

**Server Control:**
- `%mcp_start` - Start the MCP server
- `%mcp_stop` - Stop the MCP server
- `%mcp_restart` - Restart server (required after mode/option changes)
- `%mcp_status` - Show server status and available commands

**Note:** Server restart is required after changing modes or options for changes to take effect.

## Development Workflow

### Critical Dependencies

When making changes to MCP tools:
1. **Update `stdio_proxy.py`**: Add/remove tool proxies in `instrmcp/tools/stdio_proxy.py`
2. **Check `requirements.txt`**: Ensure new Python dependencies are listed
3. **Update `pyproject.toml`**: Add dependencies and entry points as needed
4. **Update README.md**: Document new features or removed functionality

### Safe vs Unsafe Mode

The server operates in two modes:
- **Safe Mode**: Read-only access to instruments and notebooks
- **Unsafe Mode**: Allows code execution in Jupyter cells

This is controlled via the `safe_mode` parameter in server initialization and the `--unsafe` CLI flag.

### Testing

- **Always use conda environment instrMCPdev for testing**
- Use `pytest` for running tests
- Test files are in `qdevbench/tests/`
- Mock instruments available for testing without hardware
- Coverage reports generated with `pytest --cov=instrmcp`

### JupyterLab Extension

The package includes a JupyterLab extension for active cell bridging:
- Located in `instrmcp/extensions/jupyterlab/`
- **Build workflow:** `cd instrmcp/extensions/jupyterlab && jlpm run build`
  - The build automatically copies files to `mcp_active_cell_bridge/labextension/`
  - This ensures `pip install -e .` will find the latest built files
- Automatically installed with the main package
- Enables real-time cell content access for MCP tools

**Important for development:** After modifying TypeScript files, you must:
1. Run `jlpm run build` in the extension directory
2. The postbuild script automatically copies files to the correct location
3. Reinstall: `pip install -e . --force-reinstall --no-deps`
4. Restart JupyterLab completely

### Configuration

- Station configuration: YAML files in `instrmcp/config/data/`
- Environment variable: `instrMCP_PATH` must be set for proper operation
- Auto-detection of installation paths via `instrmcp config`

## Important Notes

- Always test MCP tool changes with both safe and unsafe modes
- The caching system (`cache.py`) prevents excessive instrument reads
- Rate limiting protects instruments from command flooding
- The system supports hierarchical parameter access (e.g., `ch01.voltage`)
- Jupyter cell tracking happens via IPython event hooks for real-time access
- **Always use conda environment instrMCPdev for testing**
- Remember to update stdio_proxy.py whenever we change the tools for mcp server.
- check requirements.txt when new python file is created.
- don't forget to update pyproject.toml
- whenever delete or create a tool in mcp_server.py, update the hook in instrmcp.tools.stdio_proxy
- when removing features, update readme.md