# InstrMCP: Instrumentation Control MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://github.com/anthropics/mcp)

MCP server suite for physics laboratory instrumentation control, enabling Large Language Models to interact directly with physics instruments and measurement systems.

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/instrmcp/instrMCP.git
cd instrMCP

# Install dependencies
pip install -e .

# For QCodes support
pip install -e ".[qcodes]"
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### Run QCodes MCP Server

```bash
# Start server
python -m servers.qcodes.server --port 8000

# Or using entry point
qcodes-mcp-server --port 8000
```

### JupyterLab Extension Setup

For the `get_editing_cell` functionality that captures currently editing cells from JupyterLab frontend:

#### 1. Install the JupyterLab Extension

```bash
# Navigate to the extension directory
cd servers/jupyter_qcodes/labextension

# Clean any existing artifacts
rm -rf node_modules package-lock.json yarn.lock .yarn lib tsconfig.tsbuildinfo

# Install dependencies using jlpm (JupyterLab's package manager)
jlpm install

# Build the TypeScript library
jlpm run build:lib

# Build the extension
jupyter labextension build .

# Install the extension in development mode
jupyter labextension develop . --overwrite

# Or install in production mode
jupyter labextension install .
```

#### Version Compatibility

**Important**: The extension requires JupyterLab 4.2+ for compatibility. Check your version:
```bash
jupyter --version
# Should show jupyterlab: 4.2.0 or higher
```

#### Troubleshooting

**Error: "Could not find @jupyterlab/builder"**
- This indicates version mismatch between JupyterLab and extension dependencies
- The extension is configured for JupyterLab 4.2+ - ensure you have compatible versions
- Solution: Clean and reinstall:
  ```bash
  cd servers/jupyter_qcodes/labextension
  rm -rf node_modules yarn.lock .yarn lib
  jlpm install
  jlpm run build:lib
  jupyter labextension build .
  ```

**Error: "This package doesn't seem to be present in your lockfile"**
- This happens when mixing `npm` and `jlpm` package managers
- Solution: Clean and reinstall with `jlpm` only:
  ```bash
  rm -rf node_modules package-lock.json lib
  jlpm install
  jlpm run build
  ```

**Yarn PnP Issues**
- If you see Yarn PnP (Plug'n'Play) related errors, the extension includes a `.yarnrc.yml` file that disables PnP mode
- This forces traditional `node_modules` structure that JupyterLab expects

#### 2. Verify Installation

```bash
# List installed extensions
jupyter labextension list

# Should show: mcp-active-cell-bridge enabled
```

#### 3. Load the Jupyter MCP Extension

In your Jupyter notebook, load the MCP extension:

```python
# Load the extension
%load_ext servers.jupyter_qcodes.jupyter_mcp_extension

# Verify it's running
# You should see: 🚀 QCoDeS MCP Server starting...
```

#### 4. Test the Editing Cell Capture

Once both the JupyterLab extension and MCP server are running, the `get_editing_cell` tool will capture the content of the currently active/editing cell in real-time via kernel communication.

**Usage Examples:**
- `get_editing_cell()` - Get current editing cell content (any age)
- `get_editing_cell(fresh_ms=1000)` - Get content no older than 1 second

**Note**: The extension uses a 2-second debounce for content changes to prevent excessive updates during typing.

#### 5. Debug Information

For debugging the extension:

```bash
# Check if extension is installed and enabled
jupyter labextension list

# View browser console for extension logs (look for "MCP Active Cell Bridge")
# Open browser developer tools in JupyterLab

# Check kernel-side comm registration
# In notebook: print("Comm target registered") should appear on extension load
```

**Console Debug Messages:**
- `"MCP Active Cell Bridge extension activated"` - Extension loaded
- `"MCP Active Cell Bridge: Comm opened with kernel"` - Communication established  
- `"MCP Active Cell Bridge: Sent snapshot (X chars)"` - Cell content sent to kernel
- `"MCP Active Cell Bridge: Tracking new active cell"` - New cell selected

## Architecture

### Station-Based Design
- **YAML Configuration**: Define instruments in `config/station.station.yaml`
- **Lazy Loading**: Instruments loaded on-demand for safety
- **Snapshot Health**: Read-only instrument status via `snapshot()` methods

### MCP Tools
- `all_instr_health(update=False)` - Get station-wide instrument status
- `inst_health(name, update=True)` - Get single instrument snapshot  
- `load_instrument(name)` - Load instrument from configuration
- `station_info()` - General station information

### Resources
- `available_instr` - JSON list of configured instruments

## Configuration Example

```yaml
# config/station.station.yaml
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
```

## Usage with LLMs

```
User: "Show me the health status of all instruments"
LLM → all_instr_health()

User: "Load the mock DAC and check its status"  
LLM → load_instrument("mock_dac")
LLM → inst_health("mock_dac")
```

## Safety Features

- **Read-Only by Default**: Only snapshot/health tools enabled initially
- **Configuration Control**: Instruments disabled by default in YAML
- **Validation**: Parameter bounds checking and error handling
- **Isolated Environments**: Virtual environment per module

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Code formatting
black servers/ tools/ tests/
```

## Project Structure

```
instrMCP/
├── plan.md                    # Implementation roadmap
├── servers/qcodes/           # QCodes MCP server
├── config/                   # Configuration files  
├── state/                    # Runtime state
├── tools/                    # Helper utilities
└── tests/                    # Test suite
```

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

