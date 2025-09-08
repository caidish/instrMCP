"""
Example usage of the Jupyter QCoDeS MCP extension.

Run this in a Jupyter notebook to demonstrate the functionality.
"""

# Cell 1: Setup QCoDeS instruments
import qcodes as qc
import numpy as np

# Create station and mock instruments
station = qc.Station()

# Load instruments from config or create mock ones
try:
    # Try to load from your station config
    station = qc.Station(config_file='../config/station.yaml')
    mock_dac1 = station.load_mock_dac1()
    mock_dac2 = station.load_mock_dac2()
except:
    # Fallback to manual creation
    from qcodes.instrument_drivers.mock_instruments import MockDAC
    mock_dac1 = MockDAC('mock_dac1', num_channels=2)
    mock_dac2 = MockDAC('mock_dac2', num_channels=2)
    station.add_component(mock_dac1)
    station.add_component(mock_dac2)

# Set some initial values
mock_dac1.ch01.voltage(0.1)
mock_dac1.ch02.voltage(0.2)
mock_dac2.ch01.voltage(1.1)
mock_dac2.ch02.voltage(1.2)

# Create some data
measurement_data = np.random.randn(100)
config = {'sweep_range': (-1, 1), 'points': 100}

print("✅ QCoDeS setup complete")

# Cell 2: Load the MCP extension
%load_ext servers.jupyter_qcodes.jupyter_mcp_extension

# Cell 3: Check server status (optional)
from servers.jupyter_qcodes.jupyter_mcp_extension import get_server_status
print("Server status:", get_server_status())

# Cell 4: Now you can interact with Claude!
"""
The MCP server is now running and has access to all your instruments and variables.

Claude can now:

1. **Read instrument parameters:**
   - "What's the current voltage on mock_dac1 channel 1?"
   - "Show me all parameters for mock_dac2"

2. **Inspect your workspace:**
   - "What instruments do I have available?"
   - "What variables are in my namespace?"
   - "Show me the configuration of my QCoDeS station"

3. **Monitor parameters:**
   - "Subscribe to voltage updates from mock_dac1.ch01"
   - "Monitor both DAC channels every 2 seconds"

4. **Suggest measurement code:**
   - "I want to sweep DAC1 channel 1 from 0 to 1V and measure DAC2 channel 2"
   - "Help me set up an IV measurement"

5. **Analyze data:**
   - "Look at my measurement_data array and tell me about it"
   - "What's in my config dictionary?"

Example interactions:
- Claude: "I see you have mock_dac1 and mock_dac2. Channel 1 of mock_dac1 is at 0.1V."
- Claude: "Here's code to sweep your DAC: `for v in np.linspace(0, 1, 21): mock_dac1.ch01.voltage(v)`"
- Claude: "Your measurement_data has 100 points with mean=0.05 and std=0.98"
"""

# Cell 5: Example of what Claude can access
print("Available instruments:", [name for name, obj in globals().items() 
                                if hasattr(obj, 'parameters')])
print("Data shapes:", {name: getattr(obj, 'shape', 'no shape') 
                       for name, obj in globals().items() 
                       if hasattr(obj, 'shape')})

# Cell 6: You can continue with your normal work
# The MCP server runs in the background and Claude has read-only access
# to everything you do!