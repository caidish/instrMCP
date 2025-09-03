# QCodes MCP Server

MCP server for QCodes-based physics laboratory instrumentation control.

## Overview

This module provides an MCP (Model Context Protocol) interface to QCodes, enabling Large Language Models to interact with physics instruments through standardized tool calls.

## Features

- **Instrument Discovery**: Automatically find available instruments
- **Connection Management**: Connect/disconnect instruments safely
- **Parameter Operations**: Read and write instrument parameters
- **Measurement Execution**: Run measurement sequences and sweeps
- **Data Handling**: Stream and save measurement data

## Quick Start

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Server

```bash
python src/server.py --port 8000
```

### Usage with MCP Client

```python
# Connect to Keithley 2400 sourcemeter
connect_instrument(driver="keithley_2400", address="GPIB0::24::INSTR")

# Set voltage and measure current
set_parameter(instrument="k2400", parameter="voltage", value=1.0)
current = get_parameter(instrument="k2400", parameter="current")

# Run IV sweep measurement
execute_measurement(
    type="iv_sweep",
    voltage_start=-1.0,
    voltage_stop=1.0, 
    voltage_step=0.1
)
```

## Available Tools

### Instrument Management
- `discover_instruments`: Find available QCodes drivers
- `connect_instrument`: Establish instrument connection
- `disconnect_instrument`: Close connection safely
- `list_connected`: Show active instruments

### Parameter Operations  
- `get_parameter`: Read parameter value
- `set_parameter`: Write parameter value
- `get_all_parameters`: Bulk parameter read
- `validate_parameter`: Check parameter limits

### Measurements
- `execute_measurement`: Run measurement protocols
- `stream_data`: Real-time data acquisition  
- `save_measurement`: Store data to file
- `load_dataset`: Retrieve saved measurements

## Architecture

```
src/
├── server.py           # FastMCP HTTP server
├── handlers.py         # MCP request handlers  
├── instrument_tools.py # QCodes tool implementations
└── __init__.py
```

## Development

### Testing

```bash
pytest tests/
```

### Adding New Instruments

1. Add driver imports to `instrument_tools.py`
2. Register instrument in `AVAILABLE_DRIVERS` 
3. Add instrument-specific parameter mappings
4. Write tests for new functionality

## Safety & Validation

- Parameter bounds checking prevents equipment damage
- Connection state management ensures proper cleanup
- Input validation on all measurement parameters
- Emergency stop capability for long measurements