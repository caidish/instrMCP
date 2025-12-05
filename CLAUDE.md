# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Environment Setup:**

```bash
# Always use conda environment instrMCPdev for testing
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev
```

**Package Management:**

```bash
pip install -e .              # Install for development
pip install -e .[dev]         # With dev dependencies
python -m build               # Build package
instrmcp version              # Test installation
```

**Code Quality (CI Requirements - see `.github/workflows/lint.yml`):**

```bash
black --check instrmcp/ tests/                    # Format check (must pass)
flake8 instrmcp/ tests/ --select=E9,F63,F7,F82    # Critical errors only (must pass)
flake8 instrmcp/ tests/ --max-line-length=127     # Style warnings (non-blocking)
mypy instrmcp/ --ignore-missing-imports           # Type check (non-blocking)
```

**Testing:**

```bash
pytest                                              # All tests
pytest -v                                           # Verbose
pytest --cov=instrmcp --cov-report=html             # With coverage
pytest tests/unit/test_cache.py                     # Single file
pytest -k "test_cache_initialization"               # Single test by name
pytest tests/unit/test_cache.py::TestReadCache::test_cache_initialization  # Specific test
```

**Server Management:**

```bash
instrmcp jupyter --port 3000              # Start Jupyter MCP server
instrmcp jupyter --port 3000 --unsafe     # With code execution
instrmcp qcodes --port 3001               # QCodes station server
instrmcp config                           # Show configuration
```

## Architecture Overview

### Communication Flow

```text
Claude Desktop/Code ←→ STDIO ←→ claude_launcher.py ←→ stdio_proxy.py ←→ HTTP ←→ Jupyter MCP Server
```

### Key Directories

- `instrmcp/servers/jupyter_qcodes/` - Main MCP server with QCodes + Jupyter integration
- `instrmcp/servers/jupyter_qcodes/registrars/` - Tool registrars (qcodes, notebook, database, measureit)
- `instrmcp/tools/stdio_proxy.py` - STDIO↔HTTP proxy for Claude Desktop/Codex
- `instrmcp/extensions/` - Jupyter extensions, MeasureIt templates, database resources
- `instrmcp/cli.py` - Command-line interface

### Key Files for Tool Changes

When adding/removing MCP tools, update ALL of these:

1. `instrmcp/servers/jupyter_qcodes/registrars/` - Add tool implementation
2. `instrmcp/tools/stdio_proxy.py` - Add/remove tool proxy
3. `docs/ARCHITECTURE.md` - Update tool documentation
4. `README.md` - Update feature documentation

### Safe vs Unsafe vs Dangerous Mode

- **Safe Mode**: Read-only access to instruments and notebooks (default)
- **Unsafe Mode**: Allows code execution (`--unsafe` flag or `%mcp_unsafe` magic)
- **Dangerous Mode**: Unsafe mode with all consent dialogs auto-approved (`%mcp_dangerous` magic)

Unsafe mode tools require user consent via dialog for: `notebook(action="update_editing_cell")`, `notebook(action="execute_cell")`, `notebook(action="delete_cell")`, `notebook(action="delete_cells")`, `notebook(action="apply_patch")`, `dynamic_register_tool`, `dynamic_update_tool`. In dangerous mode, all consents are automatically approved.

### JupyterLab Extension

Located in `instrmcp/extensions/jupyterlab/`. After modifying TypeScript:

```bash
cd instrmcp/extensions/jupyterlab && jlpm run build
pip install -e . --force-reinstall --no-deps
# Restart JupyterLab completely
```

## MCP Tools Reference

- **Core Tools:** `mcp_list_resources`, `mcp_get_resource`
- **QCodes:** `qcodes_instrument_info`, `qcodes_get_parameter_values`
- **Notebook (unified):** `notebook(action=...)` - Single meta-tool with 13 actions:
  - Safe actions: `list_variables`, `get_variable_info`, `get_editing_cell`, `get_editing_cell_output`, `get_notebook_cells`, `move_cursor`, `server_status`
  - Unsafe actions (require consent): `update_editing_cell`, `execute_cell`, `add_cell`, `delete_cell`, `delete_cells`, `apply_patch`
- **MeasureIt (opt-in):** `measureit_get_status`, `measureit_wait_for_sweep`, `measureit_wait_for_all_sweeps`
- **Database (opt-in):** `database_list_experiments`, `database_get_dataset_info`, `database_get_database_stats`
- **Dynamic Tools:** `dynamic_register_tool`, `dynamic_update_tool`, `dynamic_revoke_tool`, `dynamic_list_tools`, `dynamic_inspect_tool`, `dynamic_registry_stats`

See `docs/ARCHITECTURE.md` for detailed tool parameters and resources.

## Magic Commands (Jupyter)

```python
%load_ext instrmcp.extensions   # Load extension
%mcp_start                      # Start server
%mcp_stop                       # Stop server
%mcp_restart                    # Restart (required after mode/option changes)
%mcp_status                     # Show status
%mcp_safe                       # Switch to safe mode
%mcp_unsafe                     # Switch to unsafe mode
%mcp_dangerous                  # Switch to dangerous mode (auto-approve all consents)
%mcp_option measureit           # Enable MeasureIt
%mcp_option database            # Enable database tools
%mcp_option -measureit          # Disable MeasureIt
```

## Checklist When Modifying Tools

- [ ] Update tool implementation in `registrars/`
- [ ] Update `stdio_proxy.py` with tool proxy
- [ ] Update `docs/ARCHITECTURE.md`
- [ ] Update `README.md` if user-facing
- [ ] Run `black instrmcp/ tests/` before committing
- [ ] Run `pytest` to verify tests pass
- [ ] Run `flake8 instrmcp/ tests/ --select=E9,F63,F7,F82` (must pass for CI)

