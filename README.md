# InstrMCP: Instrumentation Control MCP Server

[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](https://github.com/caidish/instrMCP/releases)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://github.com/anthropics/mcp)
[![Documentation Status](https://readthedocs.org/projects/instrmcp/badge/?version=latest)](https://instrmcp.readthedocs.io/en/latest/?badge=latest)
[![Tests](https://github.com/caidish/instrMCP/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/caidish/instrMCP/actions/workflows/tests.yml)
[![Lint](https://github.com/caidish/instrMCP/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/caidish/instrMCP/actions/workflows/lint.yml)

MCP server suite for quantum device physics laboratory's instrumentation control, enabling Large Language Models to interact directly with physics instruments and measurement systems through QCodes and JupyterLab.

https://github.com/user-attachments/assets/1d4d6e42-138c-4f49-90ef-803eb6c01488

## Features

- **Full QCodes Integration**: Built-in support for all QCodes instrument drivers
- **Database Integration**: Read-only access to QCodes databases with intelligent code generation
- **MeasureIt Templates**: Comprehensive measurement pattern library and code generation
- **JupyterLab Native**: Seamless integration with JupyterLab
- **Safe mode**: Read-only mode with optional unsafe execution
- **CLI**: Easy server management with `instrmcp` command
- **MCP**: Standard Model Context Protocol for LLM integration
- The MCP has been tested to work with Claude Desktop, Claude Code, and Codex CLI

## Quick Start

### Installation

```bash
# Install from source
git clone https://github.com/caidish/instrMCP.git
cd instrMCP
pip install -e .

# Set required environment variable
# For macOS/Linux:
export instrMCP_PATH="$(pwd)"
echo 'export instrMCP_PATH="'$(pwd)'"' >> ~/.zshrc  # or ~/.bashrc
source ~/.zshrc

# For Windows (PowerShell):
$env:instrMCP_PATH = (Get-Location).Path
[System.Environment]::SetEnvironmentVariable('instrMCP_PATH', (Get-Location).Path, 'User') 
```

**That's it!** QCodes, JupyterLab, and all dependencies are automatically installed.

### Extension: MeasureIt

To install MeasureIt, visit https://github.com/nanophys/MeasureIt and follow the installation instructions.

### Usage

#### Loading InstrMCP in Jupyter

```bash
# Start JupyterLab
jupyter lab
```

In a Jupyter notebook cell:

```python
# Load InstrMCP extension
%load_ext instrmcp.extensions

# Start MCP server
%mcp_start

# Check status
%mcp_status

# Enable unsafe mode (code execution)
%mcp_unsafe

# Enable optional features (restart required)
%mcp_option add measureit database
%mcp_restart
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

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture, package structure, MCP tools and resources
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Development Guide](docs/DEVELOPMENT.md)** - Development setup, testing, code quality, contributing

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

Configuration is automatic! The system auto-detects installation paths. For custom setups:

```bash
# View current configuration
instrmcp config

# Custom config file (optional)
mkdir -p ~/.instrmcp
echo "custom_setting: value" > ~/.instrmcp/config.yaml
```

## Claude Desktop Integration

InstrMCP provides seamless integration with Claude Desktop for AI-assisted laboratory instrumentation control.

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

See [`claudedesktopsetting/README.md`](claudedesktopsetting/README.md) for detailed setup instructions and troubleshooting.

## Claude Code Integration

Claude Code supports local MCP servers via STDIO. Use the provided launcher to connect:

```bash
# Add instrMCP as MCP Server
claude mcp add instrMCP --env instrMCP_PATH=$instrMCP_PATH \
  --env PYTHONPATH=$instrMCP_PATH \
  -- $instrMCP_PATH/venv/bin/python \
  $instrMCP_PATH/claudedesktopsetting/claude_launcher.py

# Verify connection
/mcp
```

**Prerequisites:**
- Ensure `instrMCP_PATH` environment variable is set
- Have a Jupyter server running with the instrMCP extension loaded
- MCP server started in Jupyter with `%mcp_start`

## Codex CLI Integration

Codex expects MCP servers over STDIO. Use the Codex launcher to proxy STDIO calls to your HTTP MCP server.

**Configuration:**
- command: `python`
- args: `["/path/to/your/instrMCP/codexsetting/codex_launcher.py"]`
- env:
  - `JUPYTER_MCP_HOST=127.0.0.1`
  - `JUPYTER_MCP_PORT=8123`

## V2.0.0 Plan

- Support RedPitaya
- Support Raspberry Pi for outdated instruments
- Integrating lab wiki knowledge base for safety rails
- More LLM integration examples

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

We welcome contributions! See our [Development Guide](docs/DEVELOPMENT.md) for details on:
- Setting up development environment
- Running tests
- Code quality standards
- Contribution guidelines

## Links

- [Documentation](https://instrmcp.readthedocs.io)
- [Issues](https://github.com/caidish/instrMCP/issues)
- [QCodes](https://qcodes.github.io/Qcodes/)
- [Model Context Protocol](https://github.com/anthropics/mcp)
