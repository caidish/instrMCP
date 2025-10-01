# InstrMCP: Instrumentation Control MCP Server

[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](https://github.com/caidish/instrMCP/releases)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://github.com/anthropics/mcp)
[![Documentation Status](https://readthedocs.org/projects/instrmcp/badge/?version=latest)](https://instrmcp.readthedocs.io/en/latest/?badge=latest)
[![Tests](https://github.com/caijiaqi/instrMCP/actions/workflows/tests.yml/badge.svg)](https://github.com/caijiaqi/instrMCP/actions/workflows/tests.yml)
[![Lint](https://github.com/caijiaqi/instrMCP/actions/workflows/lint.yml/badge.svg)](https://github.com/caijiaqi/instrMCP/actions/workflows/lint.yml)

 MCP server suite for quantum device physics laboratory's instrumentation control, enabling Large Language Models to interact directly with physics instruments and measurement systems through QCodes and JupyterLab.

## V1.0.0 Features

- **Full QCodes Integration**: Built-in support for all QCodes instrument drivers
- **Database Integration**: Read-only access to QCodes databases with intelligent code generation
- **MeasureIt Templates**: Comprehensive measurement pattern library and code generation
- **JupyterLab Native**: Seamless integration with JupyterLab.
- **Safe mode**: Read-only mode with optional unsafe execution
- **CLI**: Easy server management with `instrmcp` command
- **MCP**: Standard Model Context Protocol for LLM integration
- The MCP has been tested to work with Claude Desktop, Claude Code, and Codex CLI.

https://github.com/user-attachments/assets/1d4d6e42-138c-4f49-90ef-803eb6c01488


## V2.0.0 Plan
- Support RedPitaya. 
- Support Raspberry Pi for outdated instruments. 
- Integrating lab wiki knowledge base for safety rails
- More LLM integration examples.

##  Quick Start

### Installation

```bash
# Install from source (current method)
git clone https://github.com/caijiaqi/instrMCP.git
cd instrMCP
pip install -e .

# Set required environment variable
export instrMCP_PATH="$(pwd)"
echo 'export instrMCP_PATH="'$(pwd)'"' >> ~/.zshrc
source ~/.zshrc
```

**That's it!** QCodes, JupyterLab, and all dependencies are automatically installed.

**What gets installed:**
- **instrmcp** Python package with MCP servers
- **QCodes** for instrument control
- **JupyterLab** for interactive development

### Extension MeasureIt

To install MeasureIt, visit https://github.com/nanophys/MeasureIt and follow the installation instructions. 

### Usage

#### Loading InstrMCP in Jupyter

**📋 Manual Loading:** Load the extension when needed using the magic command below.

```bash
# Start JupyterLab
jupyter lab
```

In a Jupyter notebook cell, load the InstrMCP extension:

```python
# Load InstrMCP extension
%load_ext instrmcp.extensions

# Now use the magic commands:
%mcp_start                          # Start MCP server
%mcp_status                         # Check server status
%mcp_unsafe                         # Enable unsafe mode (code execution)
%mcp_safe                           # Return to safe mode

# Optional features (restart required after changes)
%mcp_option add measureit database  # Enable MeasureIt templates and database integration
%mcp_option remove measureit        # Disable MeasureIt templates
%mcp_option list                    # Show enabled optional features
%mcp_restart                        # Restart server to apply changes
%mcp_close                          # Stop server
```

#### CLI Server Management

```bash
# Start standalone servers
instrmcp jupyter --port 3000                # Jupyter MCP server
instrmcp jupyter --port 3000 --unsafe       # With unsafe mode
instrmcp qcodes --port 3001                 # QCodes station server

# Configuration and info
instrmcp config    # Show configuration paths
instrmcp version   # Show version
instrmcp --help    # Show all commands
```

#### Configuration (Optional)

Configuration is automatic! The system auto-detects installation paths. For custom setups:

```bash
# View current configuration
instrmcp config

# Custom config file (optional)
mkdir -p ~/.instrmcp
echo "custom_setting: value" > ~/.instrmcp/config.yaml

# Environment variable setup (required for QCodes station.yaml)
export instrMCP_PATH="/path/to/your/instrMCP"
# Add to shell config for persistence:
echo 'export instrMCP_PATH="/path/to/your/instrMCP"' >> ~/.zshrc
source ~/.zshrc
```

## Architecture

### Package Structure
```
instrmcp/
├── servers/           # MCP server implementations
│   ├── jupyter_qcodes/ # Jupyter integration  
│   └── qcodes/        # QCodes station server
├── extensions/        # Jupyter/IPython extensions
├── tools/            # Helper utilities
├── config/           # Configuration management
└── cli.py            # Command-line interface
```

### QCodes Integration
- **Lazy Loading**: Instruments loaded on-demand for safety
- **Professional Drivers**: Full QCodes driver ecosystem support

### Available MCP Tools

**QCodes Instrument Tools:**
- `instrument_info(name, with_values)` - Get instrument details and parameter values
- `get_parameter_values(queries)` - Read parameter values (supports both single and batch queries)

**Jupyter Integration Tools:**
- `list_variables(type_filter)` - List notebook variables by type
- `get_variable_info(name)` - Detailed variable information
- `get_editing_cell_output()` - Get output of the most recently executed cell (detects running cells)
- `get_notebook_cells(num_cells, include_output)` - Get recent notebook cells
- `get_editing_cell(fresh_ms)` - Current JupyterLab cell content
- `update_editing_cell(content)` - Update current cell content
- `execute_editing_cell()` - Execute current cell (unsafe mode only)
- `server_status()` - Check server mode and status

**Database Integration Tools** *(Optional - requires `%mcp_option add database`):*
- `list_experiments()` - List all experiments in the current QCodes database
- `query_datasets(filters...)` - Query datasets with optional filters (experiment, sample, date range, run ID)
- `get_dataset_info(identifiers...)` - Get detailed information about a specific dataset
- `get_database_stats()` - Get database statistics and health information
- `suggest_database_setup(params...)` - Generate database initialization code
- `suggest_measurement_from_history(reference...)` - Generate measurement code based on historical data patterns

### Resources

**QCodes Resources:**
- `available_instruments` - JSON list of available QCodes instruments with hierarchical parameter structure
- `station_state` - Current QCodes station snapshot without parameter values

**Jupyter Resources:**
- `notebook_cells` - All notebook cell contents

**MeasureIt Resources** *(Optional - requires `%mcp_option add measureit`):*
- `measureit_sweep0d_template` - Sweep0D code examples for time-based monitoring
- `measureit_sweep1d_template` - Sweep1D code examples for single parameter sweeps
- `measureit_sweep2d_template` - Sweep2D code examples for 2D parameter mapping
- `measureit_simulsweep_template` - SimulSweep code examples for simultaneous parameter sweeping
- `measureit_sweepqueue_template` - SweepQueue code examples for sequential measurement workflows
- `measureit_common_patterns` - Common MeasureIt patterns and best practices
- `measureit_code_examples` - Complete collection of ALL MeasureIt patterns in structured format

**Database Resources** *(Optional - requires `%mcp_option add database`):*
- `database_config` - Current QCodes database configuration, path, and connection status
- `recent_measurements` - Metadata for recent measurements across all experiments
- `measurement_templates` - Common measurement patterns and templates extracted from historical data

## Configuration Example

Station configuration uses standard YAML format:

```yaml
# instrmcp/config/data/default_station.yaml
instruments:
  mock_dac:
    driver: qcodes.instrument_drivers.mock.MockDAC
    name: mock_dac_1
    enable: true
```

## Troubleshooting

### Installation Issues

**Error: "Module not found" or import errors**
- Ensure you installed with: `pip install instrmcp`
- Check installation: `instrmcp version`
- Verify in Python: `import instrmcp; print("OK")`

**Error: "JupyterLab extension not found"**
- Restart JupyterLab after installation
- Check extensions: `jupyter labextension list`
- Should show: `mcp-active-cell-bridge v0.1.0 enabled OK`
- If issues persist, clean and rebuild: `jupyter lab clean --all && jupyter lab build`

### Magic Commands Not Working

**Error: "Magic command not found"**
- Run setup: `instrmcp-setup` (sets up Jupyter auto-loading)
- Restart Jupyter kernel after setup
- Manual load (if needed): `%load_ext instrmcp.extensions`
- Check status: `%mcp_status`

### Configuration Issues

**Error: "Configuration file not found"**
- Configuration is automatic - no setup required
- Check paths: `instrmcp config`
- Custom config location: `~/.instrmcp/config.yaml`

**Error: "Instrument not found"**
- Check available instruments: Use MCP tool `available_instr`
- Verify YAML config in: `instrmcp/config/data/default_station.yaml`
- Enable instruments: Set `enable: true` in configuration

### Clean Installation (Fresh Start)

If you need to completely uninstall and reinstall InstrMCP (e.g., to test as a new user):

```bash
# 1. Uninstall instrmcp
pip uninstall instrmcp -y

# 2. Clean JupyterLab build cache
jupyter lab clean --all

# 3. Verify extension is removed
jupyter labextension list | grep mcp

# 4. (Optional) Create fresh conda environment
conda deactivate
conda env remove -n instrMCPdev
conda create -n instrMCPdev python=3.11 -y
conda activate instrMCPdev

# 5. Install JupyterLab and dependencies
pip install jupyterlab ipython qcodes

# 6. Reinstall instrmcp
cd /path/to/instrMCP
pip install -e .

# 7. Run setup
instrmcp-setup

# 8. Verify installation
jupyter labextension list | grep mcp-active-cell-bridge
# Should show: mcp-active-cell-bridge v0.1.0 enabled OK
```

## Development

```bash
# Install development dependencies
pip install instrmcp[dev]

# Code formatting
black instrmcp/ tests/

# Type checking  
mypy instrmcp/

# Install from source
git clone https://github.com/instrmcp/instrMCP.git
cd instrMCP
pip install -e .
```

## Optional Dependencies

```bash
# Install specific features
pip install instrmcp[redpitaya]    # RedPitaya FPGA support
pip install instrmcp[full]         # Everything (recommended)

# Development tools
pip install instrmcp[dev]          # Testing, formatting, type checking
pip install instrmcp[docs]         # Documentation building
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## Claude Desktop Integration

InstrMCP provides seamless integration with Claude Desktop, enabling AI-assisted laboratory instrumentation control through natural language. 

Claude Desktop communicates over STDIO. The launcher `claudedesktopsetting/claude_launcher.py` proxies STDIO↔HTTP using the shared proxy in `instrmcp.tools.stdio_proxy` to reach your HTTP MCP server.

### Quick Setup (2 Steps)

1. **Run Automated Setup**:
```bash
cd /path/to/your/instrMCP
./claudedesktopsetting/setup_claude.sh
```

2. **Restart Claude Desktop** completely and test with: *"What MCP tools are available?"*

**Manual Setup Alternative:**
```bash
# 1. Copy and edit configuration
cp claudedesktopsetting/claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json

# 2. Edit the copied file - replace placeholders with actual paths:
#    /path/to/your/python3 → $(which python3)
#    /path/to/your/instrMCP → $(pwd)
```

### How Claude Desktop Integration Works

**Manual Configuration** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
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
 Claude Desktop doesn't support environment variable expansion - use absolute paths only.

### Troubleshooting

**"spawn python ENOENT" error:**
- Use full Python path: `which python3` 
- Update `command` field in config with absolute path

**Claude Desktop shows no MCP tools:**
- Check Claude config file exists and has absolute paths
- Restart Claude Desktop completely (don't just reload)
- Verify Python executable is accessible

**"Standalone mode" message:**
- Start Jupyter: `jupyter lab`
- Load extension: `%load_ext instrmcp.extensions`
- Start MCP server: `%mcp_start`

**Import errors in launcher:**
- Ensure InstrMCP installed: `pip install -e .`
- Check PYTHONPATH in config points to instrMCP directory

**Setup script help:**
- Re-run: `./claudedesktopsetting/setup_claude.sh`
- Check generated config: `cat ~/Library/Application\ Support/Claude/claude_desktop_config.json`

See [`claudedesktopsetting/README.md`](claudedesktopsetting/README.md) for detailed setup instructions.

## Claude Code Integration

Claude Code supports local MCP servers via STDIO. Use the provided launcher to connect instrMCP to Claude Code for AI-assisted laboratory instrumentation control directly from the command line.

### Quick Setup

**Add instrMCP as MCP Server:**
```bash
# With virtual environment Python (recommended)
claude mcp add instrMCP --env instrMCP_PATH=$instrMCP_PATH \
  --env PYTHONPATH=$instrMCP_PATH \
  -- $instrMCP_PATH/venv/bin/python \
  $instrMCP_PATH/claudedesktopsetting/claude_launcher.py

# Or with system Python
claude mcp add instrMCP --env instrMCP_PATH=$instrMCP_PATH \
  --env PYTHONPATH=$instrMCP_PATH \
  -- python $instrMCP_PATH/claudedesktopsetting/claude_launcher.py
```

**Verify Connection:**
```bash
# Check MCP servers
/mcp

# Restart if needed
claude mcp restart instrMCP
```

### Communication Flow
```
Claude Code ←→ STDIO ←→ claude_launcher.py ←→ (instrmcp.tools.stdio_proxy) ←→ HTTP ←→ Jupyter MCP Server
```

### Usage
Once connected, you can interact with your instruments through natural language:
```
User: "List all available instruments"
Claude: [Uses mcp__instrMCP__list_instruments()]

User: "Check the health status of the mock DAC"
Claude: [Uses mcp__instrMCP__instrument_info("mock_dac")]

User: "Show me my recent Jupyter notebook cells"
Claude: [Uses mcp__instrMCP__get_notebook_cells()]
```

### Prerequisites
- Ensure `instrMCP_PATH` environment variable is set in your shell
- Have a Jupyter server running with the instrMCP extension loaded
- MCP server should be started in Jupyter with `%mcp_start`

## Codex CLI Integration

Codex expects MCP servers over STDIO. Use the Codex launcher to proxy STDIO calls to your HTTP MCP server.

**Command**
- command: `python`
- args: `["/path/to/your/instrMCP/codexsetting/codex_launcher.py"]`
- env:
  - `JUPYTER_MCP_HOST=127.0.0.1`
  - `JUPYTER_MCP_PORT=8123`

**Flow**
```
Codex CLI ←→ STDIO ←→ codex_launcher.py ←→ (instrmcp.tools.stdio_proxy) ←→ HTTP ←→ Jupyter MCP Server
```

After configuring, start Codex and ask to list MCP tools. You should see tools from the HTTP server (proxied through the launcher).

## Links

- [Documentation](https://instrmcp.readthedocs.io)
- [Issues](https://github.com/instrmcp/instrMCP/issues)
- [QCodes](https://qcodes.github.io/Qcodes/)
- [Model Context Protocol](https://github.com/anthropics/mcp)
