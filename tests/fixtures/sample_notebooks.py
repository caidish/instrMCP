"""
Sample Jupyter notebook data for testing.

Provides realistic notebook cell examples for testing cell manipulation,
execution, and analysis features.
"""

from typing import Dict, List, Any


# Sample cell contents for different scenarios
CELL_IMPORT_QCODES = """import qcodes as qc
import numpy as np
import matplotlib.pyplot as plt
"""

CELL_CREATE_INSTRUMENT = """# Initialize mock DAC
from qcodes.instrument_drivers.mock import MockDAC
mock_dac = MockDAC('mock_dac', num_channels=4)
print(f"Created instrument: {mock_dac.name}")
"""

CELL_READ_PARAMETER = """# Read voltage from channel 1
voltage = mock_dac.ch01.voltage()
print(f"Channel 1 voltage: {voltage} V")
"""

CELL_SWEEP_1D = """# Simple 1D sweep
from qcodes.dataset import Measurement, initialise_or_create_database_at

# Initialize database
initialise_or_create_database_at('./test_measurements.db')

# Create measurement
meas = Measurement(name='voltage_sweep')
meas.register_parameter(mock_dac.ch01.voltage)
meas.register_parameter(mock_dmm.voltage)

# Run sweep
with meas.run() as datasaver:
    for v in np.linspace(0, 1, 11):
        mock_dac.ch01.voltage(v)
        measured_v = mock_dmm.voltage()
        datasaver.add_result(
            (mock_dac.ch01.voltage, v),
            (mock_dmm.voltage, measured_v)
        )
"""

CELL_MEASUREIT_SWEEP = """# MeasureIt 1D sweep
from MeasureIt.sweep import Sweep1D

sweep = Sweep1D(
    set_param=mock_dac.ch01.voltage,
    start=0,
    stop=1,
    num_points=11,
    inter_delay=0.01
)
sweep.follow_param(mock_dmm.voltage)
sweep.run()
"""

CELL_DATA_ANALYSIS = """# Analyze measurement data
import pandas as pd

# Load last measurement
ds = qc.load_by_run_spec(captured_run_id=-1)
data = ds.to_pandas_dataframe()

# Plot results
fig, ax = plt.subplots()
ax.plot(data['mock_dac_ch01_voltage'], data['mock_dmm_voltage'], 'o-')
ax.set_xlabel('Gate Voltage (V)')
ax.set_ylabel('Measured Voltage (V)')
ax.set_title('IV Characteristic')
plt.show()
"""

CELL_MARKDOWN_HEADER = """## Measurement Session
Date: 2024-01-01
Sample: Test Device A
Temperature: 4.2 K
"""

CELL_MARKDOWN_NOTES = """### Notes
- Device looks stable
- Need to check gate leakage
- Plan next: measure at different temperatures
"""

CELL_ERROR_EXAMPLE = """# This cell will cause an error
undefined_variable = nonexistent_function()
"""


def get_sample_cells() -> List[Dict[str, Any]]:
    """Get a list of sample notebook cells with metadata."""
    return [
        {
            "cell_type": "markdown",
            "source": CELL_MARKDOWN_HEADER,
            "metadata": {}
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "source": CELL_IMPORT_QCODES,
            "outputs": [],
            "metadata": {}
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "source": CELL_CREATE_INSTRUMENT,
            "outputs": [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": "Created instrument: mock_dac\n"
                }
            ],
            "metadata": {}
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "source": CELL_READ_PARAMETER,
            "outputs": [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": "Channel 1 voltage: 0.0 V\n"
                }
            ],
            "metadata": {}
        },
        {
            "cell_type": "markdown",
            "source": CELL_MARKDOWN_NOTES,
            "metadata": {}
        },
        {
            "cell_type": "code",
            "execution_count": 4,
            "source": CELL_DATA_ANALYSIS,
            "outputs": [
                {
                    "output_type": "display_data",
                    "data": {
                        "image/png": "iVBORw0KGgoAAAANS...",
                        "text/plain": "<Figure size 640x480 with 1 Axes>"
                    },
                    "metadata": {}
                }
            ],
            "metadata": {}
        }
    ]


def get_measureit_cells() -> List[Dict[str, Any]]:
    """Get sample cells specifically for MeasureIt testing."""
    return [
        {
            "cell_type": "code",
            "execution_count": 1,
            "source": CELL_IMPORT_QCODES,
            "outputs": []
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "source": CELL_CREATE_INSTRUMENT,
            "outputs": [{"output_type": "stream", "text": "Created instrument: mock_dac\n"}]
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "source": CELL_MEASUREIT_SWEEP,
            "outputs": [{"output_type": "stream", "text": "Sweep completed: 11 points\n"}]
        }
    ]


def get_error_cells() -> List[Dict[str, Any]]:
    """Get sample cells that contain errors (for error handling tests)."""
    return [
        {
            "cell_type": "code",
            "execution_count": 1,
            "source": CELL_ERROR_EXAMPLE,
            "outputs": [
                {
                    "output_type": "error",
                    "ename": "NameError",
                    "evalue": "name 'nonexistent_function' is not defined",
                    "traceback": [
                        "\u001b[0;31m---------------------------------------------------------------------------\u001b[0m",
                        "\u001b[0;31mNameError\u001b[0m                                 Traceback (most recent call last)",
                        "Cell \u001b[0;32mIn[1], line 2\u001b[0m\n\u001b[1;32m      1\u001b[0m \u001b[38;5;66;03m# This cell will cause an error\u001b[39;00m\n\u001b[0;32m----> 2\u001b[0m undefined_variable \u001b[38;5;241m=\u001b[39m \u001b[43mnonexistent_function\u001b[49m()\n",
                        "\u001b[0;31mNameError\u001b[0m: name 'nonexistent_function' is not defined"
                    ]
                }
            ]
        }
    ]
