# InstrMCP: Instrumentation Control MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://github.com/anthropics/mcp)

Professional MCP server suite for physics laboratory instrumentation control, enabling Large Language Models to interact directly with physics instruments and measurement systems through QCodes and JupyterLab.

## ✨ Features

- **🔬 Full QCodes Integration**: Built-in support for all QCodes instrument drivers
- **📊 JupyterLab Native**: Seamless integration with JupyterLab notebooks
- **🛡️ Safe by Default**: Read-only mode with optional unsafe execution
- **⚡ Zero Configuration**: Automatic setup with no environment variables required
- **🎯 Professional CLI**: Easy server management with `instrmcp` command
- **🔗 MCP Protocol**: Standard Model Context Protocol for LLM integration

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI (recommended - when available)
pip install instrmcp && instrmcp-setup

# Install from source (current method)
git clone https://github.com/caijiaqi/instrMCP.git
cd instrMCP
pip install -e . && instrmcp-setup
```

**That's it!** QCodes, JupyterLab, and all dependencies are automatically installed.

**What gets installed & configured:**
- 📦 **instrmcp** Python package with MCP servers
- 🧪 **JupyterLab extension** (mcp-active-cell-bridge) for active cell capture (via `instrmcp-setup`)
- 🐍 **IPython extension** with magic commands (manual loading)
- ⚙️ **CLI tools** (`instrmcp`, `instrmcp-setup` commands)

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
%mcp_start        # Start MCP server
%mcp_status       # Check server status  
%mcp_unsafe       # Enable unsafe mode (code execution)
%mcp_safe         # Return to safe mode
%mcp_restart      # Restart server
%mcp_close        # Stop server
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
```

## 🔧 Advanced Features

### Active Cell Capture

InstrMCP automatically captures your currently editing JupyterLab cell content for LLM analysis:

```python
# In your notebook, the LLM can access:
get_editing_cell()                    # Current cell content (any age)
get_editing_cell(fresh_ms=1000)       # Content no older than 1 second
get_notebook_cells()                  # All notebook cells  
update_editing_cell("new code")       # Update current cell
```

The extension uses intelligent debouncing (2-second delay) to avoid excessive updates while typing.

### Extension Management

```bash
# Check extension status
jupyter labextension list

# Should show: mcp-active-cell-bridge v0.1.0 enabled OK
```

Both extensions are automatically installed and configured - no manual setup required!

## 🏗️ Architecture

### Modern Package Structure
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
- **Station-Based Design**: YAML configuration in `instrmcp/config/data/`
- **Lazy Loading**: Instruments loaded on-demand for safety
- **Professional Drivers**: Full QCodes driver ecosystem support
- **Health Monitoring**: Real-time instrument status via snapshots

### Available MCP Tools
- `all_instr_health()` - Station-wide instrument status
- `inst_health(name)` - Single instrument snapshot  
- `load_instrument(name)` - Load instrument from configuration
- `station_info()` - General station information
- `get_editing_cell()` - Current JupyterLab cell content
- `execute_editing_cell()` - Execute current cell (unsafe mode)

### Resources
- `available_instr` - JSON list of configured instruments
- `notebook_cells` - All notebook cell contents

## 📝 Configuration Example

Station configuration uses standard YAML format:

```yaml
# instrmcp/config/data/default_station.yaml
instruments:
  mock_dac:
    driver: qcodes.instrument_drivers.mock.MockDAC
    name: mock_dac_1
    enable: true
    
  keithley_2400:
    driver: qcodes.instrument_drivers.Keithley.keithley_2400.Keithley2400
    name: k2400
    address: GPIB0::24::INSTR
    enable: false  # Disabled for safety
    
  general_test_device:
    driver: instrmcp.servers.general_test_instrument.GeneralTestInstrument
    name: test_device
    config_file: instrmcp://config/data/test_device.json
    enable: true
```

## 🤖 Usage with LLMs

```
User: "Show me the health status of all instruments"
LLM → all_instr_health()

User: "Load the mock DAC and check its status"  
LLM → load_instrument("mock_dac")
LLM → inst_health("mock_dac")

User: "What code am I currently writing?"
LLM → get_editing_cell()

User: "Execute the current cell"
LLM → execute_editing_cell()  # (requires unsafe mode)
```

## 🛡️ Safety Features

- **🔒 Safe by Default**: Read-only mode prevents accidental instrument commands
- **⚡ Unsafe Mode**: Explicit opt-in for code execution capabilities
- **🎛️ Configuration Control**: Instruments disabled by default in YAML
- **✅ Validation**: Parameter bounds checking and error handling  
- **📦 Isolated Package**: Clean installation without conflicts
- **🔍 Auto-Discovery**: Automatic path detection eliminates configuration errors

## 🔧 Troubleshooting

### Installation Issues

**Error: "Module not found" or import errors**
- Ensure you installed with: `pip install instrmcp`
- Check installation: `instrmcp version`
- Verify in Python: `import instrmcp; print("OK")`

**Error: "JupyterLab extension not found"**
- Restart JupyterLab after installation
- Check extensions: `jupyter labextension list`
- Should show: `mcp-active-cell-bridge v0.1.0 enabled OK`

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

## 👨‍💻 Development

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

## 📦 Optional Dependencies

```bash
# Install specific features
pip install instrmcp[redpitaya]    # RedPitaya FPGA support
pip install instrmcp[full]         # Everything (recommended)

# Development tools
pip install instrmcp[dev]          # Testing, formatting, type checking
pip install instrmcp[docs]         # Documentation building
```

## 🚀 What's New in v0.3.0

- **✨ Zero Configuration**: No environment variables required
- **📦 Professional Package**: Standard `pip install instrmcp`
- **🎯 CLI Interface**: New `instrmcp` command suite
- **🔄 Auto-Loading**: Extensions load automatically
- **📊 Built-in QCodes**: Full QCodes ecosystem included
- **🏗️ Modern Architecture**: Clean package structure
- **🛡️ Enhanced Safety**: Improved safe/unsafe mode handling

## Context7 Integration

InstrMCP includes optional Context7 integration for QCodes documentation lookup:

```bash
# Configure Context7 API key
export CONTEXT7_API_KEY="your_key_here"
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## Links

- [Documentation](https://instrmcp.readthedocs.io)
- [Issues](https://github.com/instrmcp/instrMCP/issues)
- [QCodes](https://qcodes.github.io/Qcodes/)
- [Model Context Protocol](https://github.com/anthropics/mcp)
