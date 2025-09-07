# MoTe2 QAHE Device Simulator

A QCoDeS instrument simulator for MoTe2 Quantum Anomalous Hall Effect (QAHE) devices that provides interpolated measurements from processed experimental data.

## Overview

This simulator loads experimental data from MATLAB `.mat` files and provides a QCoDeS instrument interface with fast 2D interpolation for realistic device behavior simulation. It's designed for testing measurement scripts and developing analysis tools without requiring actual hardware.

## Features

- **QCoDeS Integration**: Full QCoDeS instrument implementation
- **Fast Interpolation**: Efficient 2D interpolation using scipy
- **Gate Voltage Control**: Settable top gate (Vtg) and back gate (Vbg) parameters
- **Lockin Measurements**: Three interpolated lockin channels (xx, xy, current)
- **Data Validation**: Comprehensive data structure validation
- **Flexible Configuration**: Multiple interpolation methods and boundary handling

## Requirements

- Python 3.7+
- qcodes
- scipy
- numpy
- Optional: matplotlib (for plotting examples)

## Installation

The simulator is included in the jupyter_qcodes MCP server. Ensure you have the required dependencies:

```bash
pip install qcodes scipy numpy matplotlib
```

## Data Format

The simulator expects a MATLAB `.mat` file (`processed_data.mat`) with the following structure:

```matlab
- Vtg: [n×1] array - Top gate voltages (V)
- Vbg: [m×1] array - Back gate voltages (V)  
- lockin_xx: [m×n] array - Lock-in XX measurements (V)
- lockin_xy: [m×n] array - Lock-in XY measurements (V)
- lockin_i: [m×n] array - Lock-in current measurements (A)
```

The 2D arrays should be organized as `[vbg_index, vtg_index]` for proper interpolation.

## Usage

### Basic Usage

```python
from tests.MoTe2QAHE_instr import MoTe2Device

# Create simulator instance
device = MoTe2Device('mote2_device', 'path/to/processed_data.mat')

# Set gate voltages
device.Vtg(0.5)  # Set top gate to 0.5V
device.Vbg(-1.0)  # Set back gate to -1.0V

# Read interpolated measurements
xx_voltage = device.lockin_xx()    # Lock-in XX (V)
xy_voltage = device.lockin_xy()    # Lock-in XY (V)  
current = device.lockin_i()        # Lock-in current (A)

# Convenience method
measurements = device.set_voltages(vtg=0.2, vbg=-0.8)
print(measurements)  # {'Vtg': 0.2, 'Vbg': -0.8, 'lockin_xx': ..., ...}

device.close()
```

### Advanced Configuration

```python
# Custom interpolation settings
device = MoTe2Device(
    'mote2_device',
    'data/processed_data.mat',
    interpolation_method='cubic',  # 'linear', 'nearest', 'cubic'
    bounds_error=False,           # Don't raise error for out-of-bounds
    fill_value=np.nan            # Fill value for extrapolation
)
```

### QCoDeS Station Integration

```python
from qcodes import Station

station = Station()
device = MoTe2Device('mote2', 'processed_data.mat')
station.add_component(device)

# Use with QCoDeS measurement loops
# ... measurement code ...

station.close_all_instruments()
```

## File Structure

```
MoTe2QAHE_instr/
├── __init__.py           # Package initialization
├── data_loader.py        # MATLAB file handling
├── mote2_simulator.py    # Main simulator class
├── example_usage.py      # Usage examples
├── test_simulator.py     # Unit tests
└── README.md            # This file
```

## Examples

### Voltage Sweeps

```python
import numpy as np
import matplotlib.pyplot as plt

device = MoTe2Device('device', 'processed_data.mat')
vtg_range, vbg_range = device.get_voltage_ranges()

# Sweep Vtg at fixed Vbg
vbg_fixed = 0.0
vtg_sweep = np.linspace(vtg_range[0], vtg_range[1], 100)

device.Vbg(vbg_fixed)
xx_values = []

for vtg in vtg_sweep:
    device.Vtg(vtg)
    xx_values.append(device.lockin_xx())

plt.plot(vtg_sweep, xx_values)
plt.xlabel('Vtg (V)')
plt.ylabel('lockin_xx (V)')
plt.show()
```

### 2D Parameter Maps

```python
# Create parameter map
vtg_grid = np.linspace(-1, 1, 50)
vbg_grid = np.linspace(-2, 2, 40)

xx_map = np.zeros((len(vbg_grid), len(vtg_grid)))

for i, vbg in enumerate(vbg_grid):
    for j, vtg in enumerate(vtg_grid):
        measurements = device.set_voltages(vtg, vbg)
        xx_map[i, j] = measurements['lockin_xx']

# Plot heatmap
plt.pcolormesh(vtg_grid, vbg_grid, xx_map, shading='auto')
plt.xlabel('Vtg (V)')
plt.ylabel('Vbg (V)')
plt.colorbar(label='lockin_xx (V)')
plt.show()
```

## Performance

The simulator uses `scipy.interpolate.RegularGridInterpolator` for efficient 2D interpolation:

- **Typical performance**: 1000+ measurements/second
- **Memory efficient**: Data loaded once, cached interpolators
- **Thread safe**: Can be used in parallel measurement loops

## Testing

Run the included tests to verify functionality:

```python
from tests.MoTe2QAHE_instr.test_simulator import run_all_tests
run_all_tests()
```

Or run the example scripts:

```python
from tests.MoTe2QAHE_instr.example_usage import main
main()  # Update data file path in the script first
```

## Data Preparation

To use your own data:

1. Export your measurement data to MATLAB format with the required variable names
2. Ensure `Vtg` and `Vbg` are sorted in ascending order
3. Verify the 2D arrays have shape `[len(Vbg), len(Vtg)]`
4. Handle NaN/infinite values appropriately

Example MATLAB export:
```matlab
save('processed_data.mat', 'Vtg', 'Vbg', 'lockin_xx', 'lockin_xy', 'lockin_i');
```

## Troubleshooting

**Import Errors**: Ensure qcodes and scipy are installed
**Data Loading Errors**: Check .mat file structure and variable names
**Interpolation Errors**: Verify data arrays have consistent shapes and finite values
**Out of Bounds**: Use `bounds_error=False` and appropriate `fill_value` for extrapolation

## Integration with MCP Server

The simulator integrates with the Jupyter QCoDeS MCP server. Once created, the instrument appears in:
- `list_instruments()` - Shows the simulator in available instruments
- `instrument_info()` - Provides parameter details  
- `get_parameter_value()` - Reads interpolated values
- All standard QCoDeS MCP tools work seamlessly

This enables LLM-based control and analysis of the simulated device through natural language interactions.