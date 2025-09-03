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

