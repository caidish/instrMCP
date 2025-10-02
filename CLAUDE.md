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

All tools use underscore naming convention for better compatibility.

**QCodes Instrument Tools:**
- `qcodes_instrument_info(name, with_values)` - Get instrument details and parameter values
- `qcodes_get_parameter_values(queries)` - Read parameter values (supports both single and batch queries)

**Jupyter Notebook Tools:**
- `notebook_list_variables(type_filter)` - List notebook variables by type
- `notebook_get_variable_info(name)` - Detailed variable information
- `notebook_get_editing_cell(fresh_ms, line_start, line_end)` - Current JupyterLab cell content
  - `fresh_ms`: Maximum age in ms (default: 1000)
  - `line_start`: Starting line number, 1-indexed (default: 1)
  - `line_end`: Ending line number, 1-indexed inclusive (default: 100)
  - Returns truncated content if cell has more than 100 lines to save context window
  - Returns empty string (not error) if selected line range is beyond cell content
- `notebook_update_editing_cell(content)` - Update current cell content
- `notebook_get_editing_cell_output()` - Get output of most recently executed cell
- `notebook_get_notebook_cells(num_cells, include_output)` - Get recent notebook cells
- `notebook_server_status()` - Check server mode and status
- `notebook_move_cursor(target)` - Move cursor to specified cell (use "next", "previous", "first", "last", or cell number)

**Unsafe Notebook Tools (unsafe mode only):**
- `notebook_execute_cell()` - Execute current cell (requires user consent via dialog)
- `notebook_add_cell(cell_type, position, content)` - Add new cell relative to active cell
- `notebook_delete_cell()` - Delete the currently active cell (requires user consent via dialog)
- `notebook_delete_cells(cell_numbers)` - Delete multiple cells by number (requires user consent via dialog)
- `notebook_apply_patch(old_text, new_text)` - Apply text replacement patch to active cell (requires user consent with visual diff preview)

**MeasureIt Integration Tools (requires `%mcp_option measureit`):**
- `measureit_get_status()` - Check if any MeasureIt sweep is currently running, returns sweep status and configuration

**Database Integration Tools (requires `%mcp_option database`):**
- `database_list_experiments(database_path)` - List all experiments in the specified QCodes database
- `database_get_dataset_info(id, database_path)` - Get detailed information about a specific dataset
- `database_get_database_stats(database_path)` - Get database statistics and health information

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

### Dynamic Tool Creation (v2.0.0 - Unsafe Mode Only)

**Meta-Tools for Runtime Tool Creation:**
- `dynamic_register_tool(name, source_code, ...)` - Register new dynamic tool
- `dynamic_update_tool(name, version, ...)` - Update existing tool
- `dynamic_revoke_tool(name, reason)` - Delete tool from registry
- `dynamic_list_tools(tag, capability, author)` - List registered tools with optional filtering
- `dynamic_inspect_tool(name)` - Get full tool specification
- `dynamic_registry_stats()` - Get registry statistics (total tools, by capability, by author, etc.)

**Capability Labels (Freeform - v2.0.0):**
Capabilities are **documentation labels only** - NOT enforced security boundaries. Use any descriptive string:
- **Suggested format**: `cap:library.action` (e.g., `cap:numpy.array`, `cap:qcodes.read`, `cap:custom.analysis`)
- **But any format is allowed** - flexibility for LLMs to describe tool dependencies
- **Uses**: Discovery (filtering/search), transparency (shown in consent UI), documentation
- **Not enforced**: No validation of capability names, no runtime checking
- **Examples of valid capabilities**:
  - `cap:numpy.array` - Uses NumPy arrays
  - `cap:qcodes.read` - Reads QCodes instrument parameters
  - `cap:scipy.optimize` - Uses SciPy optimization
  - `cap:custom.my_analysis` - Custom analysis capability
  - `data-processing` - Simple label (no cap: prefix required)
  - `instrument-control` - Any descriptive string works
- **Future (v3.0.0)**: Capability enforcement with taxonomy and security boundaries planned

**Tool Registration Example:**
```python
dynamic_register_tool(
    name="analyze_data",
    source_code="import numpy as np\n\ndef analyze_data(arr):\n    return np.mean(arr)",
    capabilities=["cap:numpy.stats", "data-processing"],  # Freeform labels
    parameters=[{"name": "arr", "type": "array", "description": "Data array", "required": true}],
    version="1.0.0",
    description="Calculate mean of data array",
    author="my_llm"
)
```

**Storage & Persistence:**
- Tools saved to `~/.instrmcp/registry/{tool_name}.json`
- Automatically reloaded on server restart
- Audit trail in `~/.instrmcp/audit/tool_audit.log`

### Optional Features and Magic Commands

The server supports optional features that can be enabled/disabled via magic commands:

**Safe/Unsafe Mode:**
- `%mcp_safe` - Switch to safe mode (read-only access)
- `%mcp_unsafe` - Switch to unsafe mode (allows cell manipulation and code execution)

**Unsafe Mode Tools (Only available when `%mcp_unsafe` is active):**
- `notebook_execute_cell()` - Execute code in the active cell
- `notebook_add_cell(cell_type, position, content)` - Add new cells to the notebook
  - `cell_type`: "code", "markdown", or "raw" (default: "code")
  - `position`: "above" or "below" active cell (default: "below")
  - `content`: Initial cell content (default: empty)
- `notebook_delete_cell()` - Delete the active cell (clears content if last cell)
- `notebook_delete_cells(cell_numbers)` - Delete multiple cells by number (comma-separated string)
- `notebook_apply_patch(old_text, new_text)` - Replace text in active cell
  - More efficient than `notebook_update_editing_cell` for small changes
  - Replaces first occurrence of `old_text` with `new_text`

**Optional Features:**
- `%mcp_option measureit` - Enable MeasureIt template resources
- `%mcp_option -measureit` - Disable MeasureIt template resources
- `%mcp_option database` - Enable database integration tools and resources
- `%mcp_option -database` - Disable database integration tools and resources
- `%mcp_option auto_correct_json` - Enable automatic JSON error correction via LLM sampling (Phase 4 feature)
- `%mcp_option -auto_correct_json` - Disable automatic JSON correction (default)
- `%mcp_option` - Show current option status

**Auto-Correction Feature (Experimental - Phase 4):**
When `auto_correct_json` is enabled, the server uses MCP sampling to automatically fix malformed JSON in tool registration:
- Applies to: `capabilities`, `parameters`, `returns`, `examples`, `tags` fields
- Uses client's LLM to correct syntax errors (missing quotes, wrong brackets, etc.)
- Returns transparent results showing original and corrected JSON
- Max 1 correction attempt per registration
- All corrections logged to audit trail
- **Timeout**: 60 seconds (server-level default) - if LLM sampling takes longer, returns original error
- **Safety**: Only fixes structural JSON errors, never modifies logic or values
- **Default**: Disabled (explicit errors preferred for transparency)

**Consent System (Phase 2):**
The server requires user consent for sensitive operations:
- **Consent workflow**: User must approve operations via consent dialog (when frontend is available)
- **Always allow**: Users can grant permanent permission to specific authors (for dynamic tools only)
- **Storage**: Permissions stored in `~/.instrmcp/consents/always_allow.json`
- **Bypass mode**: Set `INSTRMCP_CONSENT_BYPASS=1` environment variable to auto-approve all operations (for testing)
- **Timeout**: Infinite for unsafe notebook operations, 5 minutes for dynamic tool operations
- **Operations requiring consent**:
  - **Unsafe Notebook Operations**:
    - `notebook_execute_cell` - Shows code to be executed with cell info
    - `notebook_delete_cell` - Shows cell content and metadata before deletion
    - `notebook_delete_cells` - Shows count of cells to be deleted
    - `notebook_apply_patch` - Shows visual diff (red deletions, green additions) with context lines
  - **Dynamic Tool Operations**:
    - `dynamic_register_tool` - Register new dynamic tool
    - `dynamic_update_tool` - Update existing dynamic tool
- **Operations NOT requiring consent**:
  - `dynamic_revoke_tool` - Revoke/delete tool (always allowed)
  - Dynamic tool execution - Once registered with consent, tools can execute freely
  - Read-only operations (all safe mode tools)
  - `notebook_add_cell` - Adding cells is considered safe
  - `notebook_update_editing_cell` - Direct content updates (LLM has full control)

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
- **Comprehensive test suite**: 380+ tests covering all major components
- **Test structure**: `tests/` directory with unit tests, integration tests (planned), and fixtures
- **Run tests**: `pytest` (all tests) or `pytest --cov=instrmcp --cov-report=html` (with coverage)
- **Test organization**:
  - Unit tests in `tests/unit/` - isolated component tests
  - Integration tests in `tests/integration/` - end-to-end workflows (planned)
  - Fixtures in `tests/fixtures/` - mock instruments, IPython, notebooks, databases
- **Mock-based testing**: All tests use mocks (no physical hardware required)
- **Coverage target**: 80%+ for core modules
- **See `tests/README.md`** for detailed testing guide and best practices

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
- **Always use conda environment instrMCPdev for testing** by `source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev`
- Jupyter cell tracking happens via IPython event hooks for real-time access
- Remember to update stdio_proxy.py whenever we change the tools for mcp server.
- check requirements.txt when new python file is created.
- update pyproject.toml
- whenever delete or create a tool in mcp_server.py, update the hook in instrmcp.tools.stdio_proxy
- when removing features, update readme.md
- Format code when wrapping up: black instrmcp/ tests/. Check linter.