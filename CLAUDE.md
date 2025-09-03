# InstrMCP: Instrumentation Control MCP Server

## Overview

InstrMCP is a Model Context Protocol (MCP) server suite designed for physics laboratory instrumentation control. It enables Large Language Models to interact directly with physics instruments and measurement systems through standardized MCP interfaces.

## Architecture

### Core Modules

1. **qcodes-mcp-server**: Quantum measurement and physics instrumentation via QCodes
2. **redpitaya-mcp-server**: RedPitaya FPGA-based measurement platform integration  
3. **labassist-mcp-server**: General-purpose lab assistance and unusual framework support

### Technology Stack

- **MCP Framework**: fastmcp for rapid MCP server development
- **Transport**: HTTP-based MCP communication
- **QCodes Integration**: Direct instrument driver access
- **RedPitaya Control**: PyRPL library integration
- **Python Environment**: Virtual environment isolation per module

## Project Structure

```
instrMCP/
├── CLAUDE.md                   # This overview
├── README.md                   # User documentation  
├── .gitignore                  # Python project ignores
├── requirements.txt            # Core dependencies
├── setup_venv.sh              # Environment setup automation
│
├── qcodes-mcp-server/         # Module 1: QCodes Integration
│   ├── README.md              # Module-specific docs
│   ├── requirements.txt       # QCodes + FastMCP deps
│   ├── src/
│   │   ├── server.py          # FastMCP HTTP server
│   │   ├── handlers.py        # MCP request handlers
│   │   └── instrument_tools.py # QCodes tool implementations
│   └── tests/
│
├── redpitaya-mcp-server/      # Module 2: RedPitaya Control
│   ├── requirements.txt       # PyRPL dependencies
│   └── src/
│
└── labassist-mcp-server/      # Module 3: General Lab Support
    └── src/
```

## QCodes MCP Server Design

### Tool Categories

**Instrument Management:**
- `discover_instruments`: Scan for available instruments
- `connect_instrument`: Establish instrument connection
- `disconnect_instrument`: Close instrument connection
- `list_connected`: Show active instrument connections

**Parameter Operations:**
- `get_parameter`: Read instrument parameter values
- `set_parameter`: Write instrument parameter values
- `get_all_parameters`: Bulk parameter reading
- `validate_parameter`: Check parameter constraints

**Measurements:**
- `execute_measurement`: Run measurement sequences
- `stream_data`: Real-time data acquisition
- `save_measurement`: Persist measurement data
- `load_dataset`: Retrieve stored measurements

### HTTP Transport Implementation

The server uses FastMCP's HTTP transport for cross-platform compatibility and easy integration with web-based lab management systems.

## Development Environment

### Virtual Environment Setup

Each module maintains isolated Python environments to prevent dependency conflicts:

```bash
# Setup core environment
./setup_venv.sh

# Activate module-specific environment
source qcodes-mcp-server/venv/bin/activate
```

### Dependencies

**Core (`requirements.txt`):**
- fastmcp
- mcp
- pytest
- pytest-asyncio

**QCodes Module:**
- qcodes
- numpy
- pandas
- matplotlib

**RedPitaya Module:**
- pyrpl
- scipy

## Usage Patterns

### LLM Integration
The MCP servers enable natural language control of lab instruments:

```
User: "Connect to the Keithley 2400 and measure IV curve from -1V to 1V"
LLM → connect_instrument(driver="keithley_2400")
LLM → execute_measurement(type="iv_sweep", voltage_range=(-1, 1))
```

### Direct API Access
Programmatic control through MCP client libraries for automation scripts.

## Security & Safety

- Parameter validation prevents dangerous instrument states
- Connection management ensures proper instrument cleanup
- Measurement bounds checking protects equipment
- Isolated virtual environments prevent system conflicts

## Future Extensions

- Real-time experiment monitoring dashboards
- Multi-instrument coordination protocols
- Cloud-based measurement data storage
- Integration with electronic lab notebooks