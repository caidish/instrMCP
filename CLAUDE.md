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

**Testing:** (Only perform it when explicitly asked)
```bash
# Unit tests (fast, no hardware required - all mocked)
pytest tests/unit/                                  # All unit tests
pytest -v                                           # Verbose
pytest --cov=instrmcp --cov-report=html             # With coverage
pytest tests/unit/test_cache.py                     # Single file
pytest -k "test_cache_initialization"               # Single test by name
pytest tests/unit/test_cache.py::TestReadCache::test_cache_initialization  # Specific test

# E2E tests (requires Playwright and browser automation)
pytest tests/e2e/ -v                                # All E2E tests
pytest tests/e2e/test_01_server_lifecycle.py -v     # Specific E2E test file
pytest tests/e2e/ -v -m p0                          # Priority 0 (critical) tests only

# Playwright tests (metadata consistency checks)
pytest tests/playwright/ -v                         # Playwright-based tests
python tests/playwright/test_metadata_consistency.py --mode snapshot  # Update metadata snapshot
```
Important notes:
- Some tests may stall indefinitely, set a reasonable timeout if needed
- E2E tests launch real JupyterLab servers and use browser automation
- CI excludes E2E and Playwright tests (they run separately or locally)
- Supported Python versions: 3.11, 3.12, 3.13


**CLI Utilities:**
```bash
instrmcp config                           # Show configuration
instrmcp version                          # Show version
```

**Version Management:**
```bash
python tools/version.py              # Show all version locations
python tools/version.py --check      # CI check (exit 1 if mismatch)
python tools/version.py --sync       # Sync all to canonical version
python tools/version.py --bump patch # Bump patch (2.1.0 → 2.1.1)
python tools/version.py --bump minor # Bump minor (2.1.0 → 2.2.0)
python tools/version.py --bump major # Bump major (2.1.0 → 3.0.0)
python tools/version.py --set 2.2.0  # Set specific version
```

**E2E Test Prerequisites:**
```bash
# Install Playwright browsers (one-time setup for E2E tests)
playwright install chromium
```

## Architecture Overview

### Communication Flow
```
Claude Desktop/Code ←→ STDIO ←→ claude_launcher.py ←→ stdio_proxy.py ←→ HTTP ←→ Jupyter MCP Server
                              (agentsetting/claudedesktopsetting/)  (utils/)        (servers/jupyter_qcodes/)

Codex CLI          ←→ STDIO ←→ codex_launcher.py ←→ stdio_proxy.py ←→ HTTP ←→ Jupyter MCP Server
                              (agentsetting/codexsetting/)

Gemini CLI         ←→ STDIO ←→ claude_launcher.py ←→ stdio_proxy.py ←→ HTTP ←→ Jupyter MCP Server
                              (agentsetting/geminisetting/)
```

### Key Directories
- `instrmcp/servers/jupyter_qcodes/` - Main MCP server with QCodes + Jupyter integration
- `instrmcp/servers/jupyter_qcodes/core/` - Always-available tools (qcodes, notebook, resources)
- `instrmcp/servers/jupyter_qcodes/options/` - Optional features (measureit, database, dynamic_tool)
- `instrmcp/utils/stdio_proxy.py` - STDIO↔HTTP proxy for Claude Desktop/Codex
- `instrmcp/extensions/jupyterlab/` - JupyterLab frontend extension
- `instrmcp/cli.py` - Command-line interface
- `tools/version.py` - Unified version management script

### Key Files for Tool Changes
When adding/removing MCP tools, update ALL of these:
1. `instrmcp/servers/jupyter_qcodes/core/` - Core tool implementation
2. `instrmcp/servers/jupyter_qcodes/options/` - Optional feature tools
3. `instrmcp/config/metadata_baseline.yaml` - Add tool/resource descriptions
4. `instrmcp/utils/stdio_proxy.py` - Add/remove tool proxy
5. `docs/ARCHITECTURE.md` - Update tool documentation
6. `README.md` - Update feature documentation

### Metadata Configuration
Tool and resource descriptions are stored in YAML, not hardcoded in Python:
- **Baseline**: `instrmcp/config/metadata_baseline.yaml` (single source of truth)
- **User overrides**: `~/.instrmcp/metadata.yaml` (optional customizations)
- **Config loader**: `instrmcp/utils/metadata_config.py`
- **STDIO client**: `instrmcp/utils/stdio_proxy.py` - `StdioMCPClient` for validation

When adding a new tool, add its description to `metadata_baseline.yaml`:
```yaml
tools:
  my_new_tool:
    title: "My Tool"
    description: |
      Tool description here.
      Args:
          param1: Description of param1
```

**CLI commands**: `instrmcp metadata init|edit|list|show|path|validate|tokens`

**Validation** (`instrmcp metadata validate`) tests the full STDIO proxy path:
```
CLI → STDIO → stdio_proxy → HTTP → MCP Server (8123)
```

### Safe vs Unsafe vs Dangerous Mode
- **Safe Mode**: Read-only access to instruments and notebooks (default)
- **Unsafe Mode**: Allows code execution (`--unsafe` flag or `%mcp_unsafe` magic)
- **Dangerous Mode**: Unsafe mode with all consent dialogs auto-approved (`%mcp_dangerous` magic)

Unsafe mode tools require user consent via dialog for: `notebook_execute_active_cell`, `notebook_delete_cell`, `notebook_apply_patch`. In dangerous mode, all consents are automatically approved.

**Dynamic Tools** (opt-in, requires dangerous mode): Enable with `%mcp_option dynamictool` while in dangerous mode. Tools: `dynamic_register_tool`, `dynamic_update_tool`, `dynamic_revoke_tool`, `dynamic_list_tools`, `dynamic_inspect_tool`, `dynamic_registry_stats`. These tools allow runtime creation and execution of arbitrary code.

### JupyterLab Extension
Located in `instrmcp/extensions/jupyterlab/`. After modifying TypeScript:
```bash
cd instrmcp/extensions/jupyterlab && jlpm run build
pip install -e . --force-reinstall --no-deps
instrmcp-setup  # Link extension to Jupyter data directory
# Restart JupyterLab completely
```

## MCP Tools Reference

All tools use underscore naming (e.g., `qcodes_instrument_info`, `notebook_read_active_cell`).

**Core Tools:** `mcp_list_resources`, `mcp_get_resource`
**QCodes:** `qcodes_instrument_info`, `qcodes_get_parameter_values`
**Notebook:** `notebook_list_variables`, `notebook_read_variable`, `notebook_read_active_cell`, `notebook_read_active_cell_output`, `notebook_read_content`, `notebook_server_status`, `notebook_move_cursor`
**Unsafe Notebook:** `notebook_execute_active_cell`, `notebook_add_cell`, `notebook_delete_cell`, `notebook_apply_patch`
**MeasureIt (opt-in):** `measureit_get_status`, `measureit_wait_for_sweep`, `measureit_kill_sweep`
**Database (opt-in):** `database_list_experiments`, `database_get_dataset_info`, `database_get_database_stats`
**Dynamic Tools (opt-in via `dynamictool`, requires dangerous mode):** `dynamic_register_tool`, `dynamic_update_tool`, `dynamic_revoke_tool`, `dynamic_list_tools`, `dynamic_inspect_tool`, `dynamic_registry_stats`

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
%mcp_option dynamictool         # Enable dynamic tools (requires dangerous mode)
%mcp_option -measureit          # Disable MeasureIt
```

## Checklist When Modifying Tools

- [ ] Update tool implementation in `core/` or `options/`
- [ ] Add tool description to `instrmcp/config/metadata_baseline.yaml`
- [ ] Update `utils/stdio_proxy.py` with tool proxy
- [ ] Update `docs/ARCHITECTURE.md`
- [ ] Update `README.md` if user-facing
- [ ] Run `black instrmcp/ tests/` before committing
- [ ] Run `flake8 instrmcp/ tests/ --select=E9,F63,F7,F82 --extend-ignore=F824` (must pass for CI)
- [ ] Update `tests/unit/test_stdio_proxy.py` with new tool tests (expected_tool list)
- [ ] Update metadata snapshot: `python tests/playwright/test_metadata_consistency.py --mode snapshot`
- [ ] Verify metadata: `instrmcp metadata validate` (tests STDIO → HTTP → MCP Server path)

## Version Management

The project uses a unified version management script at `tools/version.py`. The canonical source of truth is `instrmcp/__init__.py`.

**Version locations managed (7 files):**

- `pyproject.toml` - Package metadata
- `instrmcp/__init__.py` - Main package (canonical source)
- `instrmcp/servers/__init__.py` - Servers subpackage
- `instrmcp/servers/jupyter_qcodes/__init__.py` - Jupyter QCodes server
- `instrmcp/extensions/jupyterlab/mcp_active_cell_bridge/__init__.py` - JupyterLab Python extension
- `instrmcp/extensions/jupyterlab/package.json` - JupyterLab Node.js extension
- `docs/source/conf.py` - Sphinx documentation

**Before releasing:** Always run `python tools/version.py --check` to verify all versions are in sync.

## CI/CD

**Workflows:**

- `.github/workflows/tests.yml` - Unit tests on Ubuntu, macOS, Windows with Python 3.11, 3.12, 3.13
- `.github/workflows/lint.yml` - Black formatting, Flake8 linting, MyPy type checking

**Key CI notes:**

- Unit tests exclude E2E and Playwright tests: `pytest tests/ --ignore=tests/e2e --ignore=tests/playwright`
- Critical lint errors must pass: `flake8 --select=E9,F63,F7,F82 --extend-ignore=F824`
- MyPy type checking continues on error (non-blocking)
- Coverage reports generated on Ubuntu 3.11 and uploaded to Codecov
