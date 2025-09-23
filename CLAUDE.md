# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

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
- `instrmcp/servers/jupyter_qcodes/mcp_server.py`: FastMCP server implementation
- `instrmcp/servers/jupyter_qcodes/tools.py`: QCodes read-only tools and Jupyter integration
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

**QCodes Instrument Tools:**
- `instrument_info(name, with_values)` - Get instrument details and parameter values
- `get_parameter_values(queries)` - Read parameter values (supports both single and batch queries)

**Jupyter Integration Tools:**
- `list_variables(type_filter)` - List notebook variables by type
- `get_variable_info(name)` - Detailed variable information
- `get_editing_cell_output()` - Get output of most recently executed cell
- `get_notebook_cells(num_cells, include_output)` - Get recent notebook cells
- `get_editing_cell(fresh_ms)` - Current JupyterLab cell content
- `update_editing_cell(content)` - Update current cell content
- `execute_editing_cell()` - Execute current cell (unsafe mode only)
- `server_status()` - Check server mode and status

### MCP Resources Available

**QCodes Resources:**
- `available_instruments` - JSON list of available QCodes instruments with hierarchical parameter structure
- `station_state` - Current QCodes station snapshot without parameter values

**Jupyter Resources:**
- `notebook_cells` - All notebook cell contents

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

- Use `pytest` for running tests
- Test files are in `qdevbench/tests/`
- Mock instruments available for testing without hardware
- Coverage reports generated with `pytest --cov=instrmcp`

### JupyterLab Extension

The package includes a JupyterLab extension for active cell bridging:
- Located in `instrmcp/extensions/jupyterlab/`
- Automatically installed with the main package
- Enables real-time cell content access for MCP tools

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
- Remember to update stdio_proxy.py whenever we change the tools for mcp server.
- check requirements.txt when new python file is created.
- don't forget to update pyproject.toml
- whenever delete or create a tool in mcp_server.py, update the hook in instrmcp.tools.stdio_proxy
- when removing features, update readme.md