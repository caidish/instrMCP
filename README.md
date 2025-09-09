# InstrMCP: Instrumentation Control MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://github.com/anthropics/mcp)

Professional MCP server suite for physics laboratory instrumentation control, enabling Large Language Models to interact directly with physics instruments and measurement systems through QCodes and JupyterLab.

## Features

- **Full QCodes Integration**: Built-in support for all QCodes instrument drivers
- **JupyterLab Native**: Seamless integration with JupyterLab. 
- **Safe mode**: Read-only mode with optional unsafe execution
- **CLI**: Easy server management with `instrmcp` command
- **MCP**: Standard Model Context Protocol for LLM integration

## Plan
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
- 📦 **instrmcp** Python package with MCP servers
- 🧪 **QCodes** for instrument control
- 🐍 **JupyterLab** for interactive development

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
- `all_instr_health()` - Station-wide instrument status
- `inst_health(name)` - Single instrument snapshot  
- `load_instrument(name)` - Load instrument from configuration
- `station_info()` - General station information
- `get_editing_cell()` - Current JupyterLab cell content
- `execute_editing_cell()` - Execute current cell (unsafe mode only)

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
- **📦 Professional Package**: Standard `pip install instrmcp`
- **🎯 CLI Interface**: New `instrmcp` command suite
- **🔄 Auto-Loading**: Extensions load automatically
- **📊 Built-in QCodes**: Full QCodes ecosystem included
- **🏗️ Modern Architecture**: Clean package structure
- **🛡️ Enhanced Safety**: Improved safe/unsafe mode handling
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

Claude Desktop now only supports stdio, so we have claude_launcher for proxying to HTTP requests.

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

**📡 Communication Flow:**
```
Claude Desktop ←→ STDIO ←→ claude_launcher.py ←→ HTTP ←→ Jupyter MCP Server
```

### Available Tools & Capabilities

#### 🔬 Instrument Control
- `list_instruments()` - Show all available QCodes instruments
- `instrument_info(name)` - Detailed instrument parameters and status
- `get_parameter_value(instrument, parameter)` - Read instrument values
- `station_snapshot()` - Complete laboratory setup overview

#### 📊 Data & Monitoring  
- `get_parameter_values(queries)` - Batch parameter readings
- `subscribe_parameter(instrument, parameter)` - Real-time monitoring
- `get_cache_stats()` - Performance monitoring

#### 💻 Jupyter Integration (Full Mode Only)
- `get_notebook_cells()` - Access recent notebook execution history
- `get_editing_cell()` - Current cell content from JupyterLab
- `update_editing_cell(content)` - Modify active cell programmatically
- `execute_editing_cell()` - Run current cell (unsafe mode required)

#### 🔧 Code Assistance
- `suggest_code(description)` - AI-generated measurement scripts
- `list_variables()` - Jupyter namespace inspection
- `get_variable_info(name)` - Detailed variable analysis

### Usage Examples

**Natural Language Queries:**
```
User: "What instruments are connected to the station?"
Claude: [Calls list_instruments() and provides formatted response]

User: "Set gate voltage to 1.5V and measure the current"
Claude: [Uses instrument tools to safely configure and measure]

User: "Show me the last measurement I ran"
Claude: [Retrieves notebook cells with get_notebook_cells()]

User: "Monitor the temperature every 2 seconds"
Claude: [Sets up parameter subscription]
```

**Advanced Automation:**
- Multi-instrument coordination
- Automated measurement sequences
- Real-time data analysis and plotting
- Experiment logging and documentation

### Configuration Details

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

**⚠️ Important**: Claude Desktop doesn't support environment variable expansion - use absolute paths only.

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

## Links

- [Documentation](https://instrmcp.readthedocs.io)
- [Issues](https://github.com/instrmcp/instrMCP/issues)
- [QCodes](https://qcodes.github.io/Qcodes/)
- [Model Context Protocol](https://github.com/anthropics/mcp)
