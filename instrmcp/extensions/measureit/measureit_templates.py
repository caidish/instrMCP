"""
MeasureIt code template definitions for AI-assisted measurement generation.

These templates provide structured code examples that AI can use to generate
appropriate MeasureIt measurement code in Jupyter cells.
"""

import json


def get_sweep0d_template() -> str:
    """
    Get Sweep0D template with common patterns for time-based monitoring.

    Returns structured examples for monitoring parameters vs time.
    """
    template = {
        "description": "Sweep0D - Monitor parameters as a function of time",
        "use_cases": [
            "Monitor noise over time",
            "Track parameter stability",
            "Long-term monitoring",
            "Background monitoring while other processes run",
        ],
        "basic_pattern": """# Sweep0D - Monitor parameters vs time
import os
from measureit import Sweep0D
from measureit.tools import ensure_qt, init_database

# Configure time-based monitoring
s = Sweep0D(
    inter_delay=0.1,        # Delay between measurements (s)
    save_data=True,         # Save to database
    plot_bin=4,             # Plot every 4th point for performance
    max_time=100            # Maximum monitoring time (s)
)

# Set parameters to monitor
s.follow_param(
    instrument.parameter1,   # Replace with actual parameters
    instrument.parameter2,
    # Add more parameters as needed
)

# Initialize database
database_name = "measurements.db"
exp_name = "monitoring_experiment"
sample_name = "sample_001"
init_database(database_name, exp_name, sample_name, s)

# Start monitoring
ensure_qt()
s.start()

# To pause: s.pause() or press ESC
""",
        "advanced_patterns": {},
        "common_parameters": {
            "inter_delay": "Time between measurements (seconds)",
            "save_data": "Whether to save data to database (True/False)",
            "plot_bin": "Plot every Nth point for performance (integer)",
            "max_time": "Maximum monitoring time in seconds",
        },
        "tips": [
            "Use ESC key to stop measurement gracefully",
            "Larger plot_bin values improve plotting performance",
            "inter_delay controls sampling rate (0.1s = 10 Hz max)",
            "Always call init_database before s.start()",
            "Use ensure_qt() for interactive plots",
            "To see if the sweep is finished or not, check s.progressState.state == SweepState.DONE",
        ],
    }

    return json.dumps(template, indent=2)


def get_sweep1d_template() -> str:
    """
    Get Sweep1D template with common patterns for single parameter sweeps.

    Returns structured examples for sweeping one parameter.
    """
    template = {
        "description": "Sweep1D - Sweep one parameter while monitoring others",
        "use_cases": [
            "Gate voltage sweeps",
            "Frequency sweeps",
            "Temperature ramps",
            "Field sweeps",
            "Characterization measurements",
        ],
        "basic_pattern": """# Sweep1D - Single parameter sweep
import os
from measureit import Sweep1D
from measureit.tools import ensure_qt, init_database

# Configure sweep
s = Sweep1D(
    gate.voltage,           # Parameter to sweep
    start=-1.0,             # Start value
    stop=1.0,               # Stop value
    step=0.01,              # Step size between measurements
    inter_delay=0.1,        # Delay between measurements
    save_data=True,
    bidirectional=True,     # Sweep back and forth
    continual=False         # Stop after one sweep
)

# Set parameters to follow
s.follow_param(
    lockin.x, lockin.y, lockin.r,    # Lock-in signals
    voltmeter.voltage,               # Additional measurements
    # Add more parameters as needed
)

# Initialize database
database_name = "measurements.db"
exp_name = "gate_sweep"
sample_name = "sample_001"
init_database(database_name, exp_name, sample_name, s)

# Start sweep
ensure_qt()
s.start()

# To pause: s.pause()
""",
        "advanced_patterns": {
            "fast_sweep": """# Fast sweep with reduced plotting
s = Sweep1D(
    freq_source.frequency,
    start=1e6, stop=10e6,   # 1-10 MHz
    step=1e5,               # 100 kHz steps
    inter_delay=0.1,       # Fast measurements
    save_data=True,
    bidirectional=False,
    plot_bin=1            # Plot every point
)
s.follow_param(spectrum_analyzer.power)
init_database("fast_sweep.db", "frequency_response", "device_B", s)
s.start()
""",
            "temperature_ramp": """# Slow temperature ramp
s = Sweep1D(
    temperature.setpoint,
    start=4.0, stop=300.0,  # 4K to 300K
    step=0.5,               # 0.5 K steps
    inter_delay=5.0,        # 5s between measurements
    save_data=True,
    bidirectional=False
)
s.follow_param(
    temperature.temperature,    # Actual temperature
    resistance.resistance,      # Sample resistance
    heater.power               # Heater power
)
init_database("temperature.db", "warmup", "sample_C", s)
s.start()
""",
            "continual_sweep": """# Continuous sweeping
s = Sweep1D(
    gate.voltage,
    start=-2.0, stop=2.0,
    step=0.05,
    inter_delay=0.1,
    save_data=True,
    bidirectional=True,
    continual=True          # Sweep continuously
)
s.follow_param(current.current, voltage.voltage)
init_database("continuous.db", "iv_curves", "device_D", s)
s.start()
# Will sweep continuously until stopped
""",
        },
        "common_parameters": {
            "parameter": "QCoDeS parameter object to sweep",
            "start": "Starting value for sweep",
            "stop": "Ending value for sweep",
            "step": "Step size between measured datapoints",
            "inter_delay": "Delay between measurements (seconds), don't be <0.01 so the measurement is stable.",
            "bidirectional": "True: sweep back and forth, False: one direction",
            "continual": "True: sweep continuously, False: stop after completion",
            "plot_bin": "Plot every Nth point for performance",
        },
        "tips": [
            "Parameter will safely ramp to start value if not already there",
            "Use spacebar during sweep to reverse direction",
            "Bidirectional sweeps are useful for hysteresis measurements",
            "Set appropriate step size to avoid damaging instruments",
            "continual=True useful for real-time monitoring",
        ],
    }

    return json.dumps(template, indent=2)


def get_sweep2d_template() -> str:
    """
    Get Sweep2D template with common patterns for 2D parameter mapping.

    Returns structured examples for 2D parameter sweeps.
    """
    template = {
        "description": "Sweep2D - Create 2D maps by sweeping two parameters",
        "use_cases": [
            "Gate voltage maps",
            "Frequency vs power maps",
            "Temperature vs field maps",
            "Stability diagrams",
            "Charge sensing maps",
        ],
        "basic_pattern": """# Sweep2D - 2D parameter mapping
import os
from measureit import Sweep2D
from measureit.tools import ensure_qt, init_database

# Define sweep parameters
inner_param = gate1.voltage     # Fast axis (swept back/forth)
inner_start = -1.0
inner_end = 1.0
inner_step = 0.02              # Step size

outer_param = gate2.voltage     # Slow axis (stepped)
outer_start = -0.5
outer_end = 0.5
outer_step = 0.05              # Step size

# Configure 2D sweep
s = Sweep2D(
    [inner_param, inner_start, inner_end, inner_step],
    [outer_param, outer_start, outer_end, outer_step],
    inter_delay=0.1,           # Delay between measurements
    outer_delay=1.0,           # Delay when stepping outer parameter
    save_data=True,
    plot_data=True,
    plot_bin=5,                # Plotting performance
    back_multiplier=4,         # Speed up return sweep
    out_ministeps=1            # Steps per outer parameter change
)

# Set parameters to follow
s.follow_param(
    lockin.x, lockin.y,        # Standard measurements
    current.current            # Additional signals
)

# Set parameters for heatmap plotting
s.follow_heatmap_param([lockin.x, current.current])

# Initialize database
database_name = "measurements.db"
exp_name = "2d_mapping"
sample_name = "sample_001"
init_database(database_name, exp_name, sample_name, s)

# Start 2D sweep
ensure_qt()
s.start()

# To pause: s.pause() or press ESC
""",
        "advanced_patterns": {
            "fine_mapping": """# High-resolution 2D map
s = Sweep2D(
    [gate1.voltage, -2.0, 2.0, 0.005],    # 0.005V steps (800 points)
    [gate2.voltage, -1.0, 1.0, 0.01],     # 0.01V steps (200 points)
    inter_delay=0.05,      # Fast measurements
    outer_delay=0.5,       # Quick outer steps
    save_data=True,
    plot_data=True,
    plot_bin=10,           # Plot every 10th point
    back_multiplier=8      # Fast return sweep
)
s.follow_param(sensor.conductance, sensor.current)
s.follow_heatmap_param([sensor.conductance])
init_database("fine_map.db", "high_res", "device_E", s)
s.start()
""",
            "frequency_power_map": """# Frequency vs Power 2D sweep
s = Sweep2D(
    [rf_source.frequency, 1e6, 10e6, 50e3],    # 1-10 MHz, 50kHz steps
    [rf_source.power, -30, 0, 1],               # -30 to 0 dBm, 1dB steps
    inter_delay=0.1,      # Fast RF measurements
    outer_delay=0.1,       # Quick power changes
    save_data=True,
    plot_data=True
)
s.follow_param(
    spectrum_analyzer.amplitude,
    phase_detector.phase
)
s.follow_heatmap_param([spectrum_analyzer.amplitude])
init_database("rf_map.db", "frequency_power", "resonator_A", s)
s.start()
""",
            "slow_2d_map": """# Slow/careful 2D mapping
s = Sweep2D(
    [magnetic_field.field, 0, 1.0, 0.01],      # 0-1T, 10mT steps
    [temperature.setpoint, 4, 20, 0.5],        # 4-20K, 0.5K steps
    inter_delay=2.0,       # 2s for field settling
    outer_delay=30.0,      # 30s for temperature settling
    save_data=True,
    plot_data=True,
    back_multiplier=2      # Slower field return
)
s.follow_param(
    resistance.resistance,
    hall_voltage.voltage,
    temperature.temperature  # Monitor actual temp
)
s.follow_heatmap_param([resistance.resistance])
init_database("magneto.db", "field_temp_map", "sample_F", s)
s.start()
""",
        },
        "common_parameters": {
            "inner_param": "Fast axis parameter (swept back and forth)",
            "outer_param": "Slow axis parameter (stepped)",
            "inner_start/end/step": "Inner sweep range and resolution",
            "outer_start/end/step": "Outer sweep range and resolution",
            "inter_delay": "Delay between measurements (seconds)",
            "outer_delay": "Delay when stepping outer parameter (seconds)",
            "back_multiplier": "Speed multiplier for return sweep (>1 = faster)",
            "plot_bin": "Plot every Nth point for performance",
            "out_ministeps": "Number of mini-steps per outer parameter change",
        },
        "tips": [
            "Inner parameter is swept relatively rapidly back and forth",
            "Outer parameter steps when inner sweep completes",
            "Use follow_heatmap_param() for real-time 2D plotting",
            "back_multiplier speeds up return sweeps",
            "Adjust outer_delay for instrument settling time",
            "Large maps can take hours - plan accordingly",
        ],
    }

    return json.dumps(template, indent=2)


def get_simulsweep_template() -> str:
    """
    Get SimulSweep template for simultaneous parameter sweeping.

    Returns structured examples for sweeping multiple parameters simultaneously.
    """
    template = {
        "description": "SimulSweep - Sweep multiple parameters simultaneously",
        "use_cases": [
            "Correlated parameter sweeps",
            "Diagonal cuts through parameter space",
            "Maintaining parameter ratios",
        ],
        "basic_pattern": """# SimulSweep - Simultaneous parameter sweeping
import os
from measureit import SimulSweep
from measureit.tools import ensure_qt, init_database

# Define parameter sweep dictionary
parameter_dict = {
    gate1.voltage: {'start': 0, 'stop': 1.0, 'step': 0.01},
    gate2.voltage: {'start': 0, 'stop': 0.5, 'step': 0.005}    # Half the range, half the step
}

# Configure simultaneous sweep
sweep_args = {
    'bidirectional': True,     # Sweep back and forth
    'plot_bin': 4,            # Plotting performance
    'continual': False,       # Stop after one sweep
    'save_data': True,
    'inter_delay': 0.1        # Delay between measurements
}

s = SimulSweep(parameter_dict, **sweep_args)

# Set parameters to follow
s.follow_param(
    lockin.x, lockin.y,       # Lock-in measurements
    current_meter.current,    # Current measurement
    # Add more parameters as needed
)

# Initialize database
database_name = "measurements.db"
exp_name = "simul_sweep"
sample_name = "sample_001"
init_database(database_name, exp_name, sample_name, s)

# Start simultaneous sweep
ensure_qt()
s.start()

# To pause: s.pause() or press ESC
""",
        "advanced_patterns": {
            "ratio_sweep": """# Maintain parameter ratio during sweep
parameter_dict = {
    gate1.voltage: {'start': -1.0, 'stop': 1.0, 'step': 0.02},
    gate2.voltage: {'start': -0.5, 'stop': 0.5, 'step': 0.01}   # 2:1 ratio maintained
}

sweep_args = {
    'bidirectional': True,
    'save_data': True,
    'inter_delay': 0.1
}

s = SimulSweep(parameter_dict, **sweep_args)
s.follow_param(differential_current.current, sum_voltage.voltage)
init_database("ratio_sweep.db", "gate_ratio", "double_dot", s)
s.start()
""",
            "frequency_phase_sweep": """# Synchronized frequency and phase sweep
parameter_dict = {
    rf_source.frequency: {'start': 1e6, 'stop': 10e6, 'step': 50e3},
    rf_source.phase: {'start': 0, 'stop': 360, 'step': 2}       # Phase follows frequency
}

sweep_args = {
    'bidirectional': False,    # One direction only
    'save_data': True,
    'inter_delay': 0.05,       # Fast RF measurements
    'plot_bin': 10
}

s = SimulSweep(parameter_dict, **sweep_args)
s.follow_param(
    iq_demod.i, iq_demod.q,
    power_meter.power
)
init_database("freq_phase.db", "iq_measurement", "cavity_A", s)
s.start()
""",
            "three_parameter_sweep": """# Three parameters simultaneously
parameter_dict = {
    gate1.voltage: {'start': -0.5, 'stop': 0.5, 'step': 0.01},
    gate2.voltage: {'start': -0.3, 'stop': 0.3, 'step': 0.006},
    bias.voltage: {'start': 0, 'stop': 0.1, 'step': 0.001}
}

sweep_args = {
    'bidirectional': True,
    'save_data': True,
    'inter_delay': 0.2,        # Slower for stability
    'continual': False
}

s = SimulSweep(parameter_dict, **sweep_args)
s.follow_param(
    sensor.conductance,
    current.current,
    voltage.voltage
)
init_database("triple_sweep.db", "3d_characterization", "device_G", s)
s.start()
""",
        },
        "common_parameters": {
            "parameter_dict": "Dictionary mapping parameters to sweep ranges",
            "start/stop/step": "Sweep range and resolution for each parameter",
            "bidirectional": "True: sweep back and forth, False: one direction",
            "continual": "True: sweep continuously, False: stop after completion",
            "inter_delay": "Delay between measurements (seconds)",
            "plot_bin": "Plot every Nth point for performance",
        },
        "tips": [
            "All parameters must have same number of steps",
            "Calculate steps: (stop-start)/step should be equal for all parameters",
            "Useful for diagonal cuts through multi-dimensional parameter space",
            "Parameters sweep simultaneously at each measurement point",
            "Good for maintaining parameter relationships/ratios",
            "To see if the sweep is finished or not, check s.progressState.state == SweepState.DONE",
        ],
    }

    return json.dumps(template, indent=2)


def get_sweepqueue_template() -> str:
    """
    Get SweepQueue template for sequential measurement workflows.

    Returns structured examples for chaining multiple measurements.
    """
    template = {
        "description": "SweepQueue - Chain multiple measurements and functions sequentially",
        "use_cases": [
            "Automated measurement sequences",
            "Multi-step characterization protocols",
            "Parameter space exploration",
            "Overnight measurement routines",
            "Complex measurement workflows",
        ],
        "basic_pattern": """# SweepQueue - Sequential measurement workflow
import os
from pathlib import Path
from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry
from measureit import Sweep1D, Sweep2D
from measureit.tools import ensure_qt, init_database

# Initialize sweep queue
sq = SweepQueue()

# Common follow parameters
follow_params = {
    lockin.x, lockin.y, lockin.r,
    current_meter.current
}

# Database setup
db_name = 'measurements.db'
db_path = str(Path(f'{os.environ.get("MeasureItHome", ".")}/Databases/{db_name}'))
exp_name = "measurement_sequence"

# Step 1: Initial characterization sweep
s1 = Sweep1D(
    gate.voltage, start=-1.0, stop=1.0, step=0.02,
    inter_delay=0.1, save_data=True, bidirectional=True
)
s1.follow_param(*follow_params)
db_entry1 = DatabaseEntry(db_path, exp_name, "initial_sweep")
sq += (db_entry1, s1)

# Step 2: Custom function (e.g., analysis or instrument adjustment)
def adjust_settings():
    print("Adjusting measurement settings...")
    # Add custom logic here
    lockin.time_constant(0.3)  # Example: change time constant
    time.sleep(2)              # Wait for settling

sq += (adjust_settings,)

# Step 3: Fine measurement at interesting region
s2 = Sweep1D(
    gate.voltage, start=-0.1, stop=0.1, step=0.005,
    inter_delay=0.2, save_data=True, bidirectional=False
)
s2.follow_param(*follow_params)
db_entry2 = DatabaseEntry(db_path, exp_name, "fine_sweep")
sq += (db_entry2, s2)

# View queue contents
for n, item in enumerate(sq):
    print(f"{n}. {item}")

# Start sequential execution
ensure_qt()
sq.start()

# To pause: sq.pause()
""",
        "advanced_patterns": {
            "overnight_sequence": """# Overnight measurement sequence
sq = SweepQueue()
follow_params = {sensor.conductance, temperature.temperature}

# Morning: Cooldown check
def cooldown_check():
    temp = temperature.temperature()
    if temp > 10:
        print(f"Temperature {temp}K too high, waiting...")
        return False
    print(f"Temperature {temp}K OK, starting measurements")
    return True

sq += (cooldown_check,)

# Measurement 1: Gate sweep at base temperature
s1 = Sweep1D(gate.voltage, -2, 2, 0.01, inter_delay=0.5, save_data=True)
s1.follow_param(*follow_params)
db1 = DatabaseEntry(db_path, "overnight", "base_temp_sweep")
sq += (db1, s1)

# Measurement 2: 2D stability diagram
s2 = Sweep2D(
    [gate1.voltage, -1, 1, 0.02],
    [gate2.voltage, -0.5, 0.5, 0.01],
    inter_delay=0.3, outer_delay=1.0, save_data=True
)
s2.follow_param(*follow_params)
s2.follow_heatmap_param([sensor.conductance])
db2 = DatabaseEntry(db_path, "overnight", "stability_diagram")
sq += (db2, s2)

# Final: Warmup sequence
def start_warmup():
    print("Starting controlled warmup")
    temperature.setpoint(20)  # Start warmup

sq += (start_warmup,)

sq.start()
""",
            "parameter_space_exploration": """# Systematic parameter space exploration
sq = SweepQueue()

# Explore different bias points
bias_points = [-0.1, -0.05, 0, 0.05, 0.1]
follow_params = {lockin.x, lockin.y, current.current}

for i, bias in enumerate(bias_points):
    # Set bias point
    def set_bias(bias_val=bias):
        bias_source.voltage(bias_val)
        time.sleep(1)  # Settling time
        print(f"Set bias to {bias_val}V")

    sq += (set_bias,)

    # Measure at this bias point
    s = Sweep1D(
        gate.voltage, start=-1, stop=1, step=0.02,
        inter_delay=0.1, save_data=True, bidirectional=True
    )
    s.follow_param(*follow_params)

    db_entry = DatabaseEntry(db_path, "bias_series", f"bias_{bias:.3f}V")
    sq += (db_entry, s)

# Return to zero bias
def reset_bias():
    bias_source.voltage(0)
    print("Reset bias to 0V")

sq += (reset_bias,)
sq.start()
""",
            "multi_device_sequence": """# Multi-device measurement sequence
sq = SweepQueue()

devices = ["device_A", "device_B", "device_C"]
switch_channels = [1, 2, 3]

for device, channel in zip(devices, switch_channels):
    # Switch to device
    def switch_device(ch=channel, name=device):
        switch.channel(ch)
        time.sleep(0.5)  # Switching time
        print(f"Switched to {name} (channel {ch})")

    sq += (switch_device,)

    # Characterize device
    s = Sweep1D(
        gate.voltage, start=-0.5, stop=0.5, step=0.01,
        inter_delay=0.1, save_data=True
    )
    s.follow_param(lockin.x, lockin.y)

    db_entry = DatabaseEntry(db_path, "multi_device", device)
    sq += (db_entry, s)

sq.start()
""",
        },
        "common_patterns": {
            "adding_sweeps": "sq += (DatabaseEntry(path, exp, sample), sweep_object)",
            "adding_functions": "sq += (function_name, arg1, arg2, ...)",
            "database_entry": "DatabaseEntry(db_path, experiment_name, sample_name)",
            "queue_iteration": "for n, item in enumerate(sq): print(f'{n}. {item}')",
        },
        "tips": [
            "Use += operator to add items to queue",
            "Functions can take arguments: sq += (func, arg1, arg2)",
            "DatabaseEntry required for each sweep that saves data",
            "Queue is iterable - you can inspect contents before starting",
            "Each sweep in queue can have different parameters",
            "Functions execute immediately when reached in queue",
            "To see if the sweep is finished or not, check s.progressState.state == SweepState.DONE",
        ],
    }

    return json.dumps(template, indent=2)


def get_common_patterns_template() -> str:
    """
    Get common MeasureIt patterns and best practices.

    Returns structured examples of common measurement workflows.
    """
    template = {
        "description": "Common MeasureIt patterns and best practices",
        "database_setup": {
            "description": "Standard database initialization patterns",
            "basic": """# Basic database setup
from measureit.tools import init_database

database_name = "measurements.db"
exp_name = "experiment_001"
sample_name = "sample_A"
init_database(database_name, exp_name, sample_name, sweep_object)
""",
            "with_path": """# Database with explicit path
import os
from pathlib import Path

db_name = "my_measurements.db"
db_path = str(Path(f'{os.environ.get("MeasureItHome", ".")}/Databases/{db_name}'))
exp_name = "gate_characterization"
sample_name = "device_001"

# For SweepQueue
from measureit.tools.sweep_queue import DatabaseEntry
db_entry = DatabaseEntry(db_path, exp_name, sample_name)
""",
            "organized": """# Organized database structure
import datetime

# Use date-based organization
today = datetime.date.today()
db_name = f"measurements_{today.strftime('%Y%m%d')}.db"
exp_name = f"sample_characterization_{today.strftime('%m%d')}"
sample_name = "device_A_gate_sweep"

init_database(db_name, exp_name, sample_name, sweep_object)
""",
        },
        "parameter_following": {
            "description": "Best practices for parameter following",
            "basic": """# Basic parameter following
sweep.follow_param(
    lockin.x, lockin.y, lockin.r,    # Lock-in amplifier
    voltmeter.voltage,               # DC measurements
    current_source.current           # Current measurements
)
""",
            "organized": """# Organized parameter groups
# Define parameter groups for clarity
lockin_params = {lockin.x, lockin.y, lockin.r, lockin.phase}
dc_params = {voltmeter.voltage, current_meter.current}
temp_params = {temperature.temperature, heater.power}

# Combine as needed
sweep.follow_param(*(lockin_params | dc_params))
""",
            "with_labels": """# Set meaningful parameter labels
lockin.x.label = "Lock-in X (V)"
lockin.y.label = "Lock-in Y (V)"
current_meter.current.label = "Sample Current (A)"
gate.voltage.label = "Gate Voltage (V)"

sweep.follow_param(lockin.x, lockin.y, current_meter.current)
""",
        },
        "plotting_setup": {
            "description": "Plotting configuration patterns",
            "basic": """# Basic plotting setup
ensure_qt()

# For 2D measurements, set heatmap parameters
sweep2d.follow_heatmap_param([primary_signal, secondary_signal])
""",
            "performance": """# Optimized plotting for performance
sweep = Sweep1D(
    parameter, start, stop, step,
    plot_bin=10,        # Plot every 10th point
    inter_delay=0.05    # Fast measurements
)

# For long measurements
sweep = Sweep0D(
    plot_bin=20,        # Plot every 20th point
    max_time=3600       # 1 hour
)
""",
            "multiple_plots": """# Multiple plot windows
ensure_qt()

# Start first measurement
sweep1.start()

# In separate cell, start second measurement
# This creates a second plot window
sweep2.start()
""",
        },
        "safety_patterns": {
            "description": "Safe measurement practices",
            "ramp_safely": """# Safe parameter ramping
# MeasureIt automatically ramps to start value
current_value = gate.voltage()
if abs(current_value - start_value) > 0.1:
    print(f"Will ramp from {current_value}V to {start_value}V")

sweep = Sweep1D(gate.voltage, start_value, stop_value, safe_step_size)
""",
            "limits_check": """# Check parameter limits before sweeping
param_limits = gate.voltage.vals
print(f"Parameter limits: {param_limits}")

if start_value < param_limits.min or stop_value > param_limits.max:
    print("WARNING: Sweep range exceeds parameter limits!")
    # Adjust range or exit
""",
            "instrument_settling": """# Allow for instrument settling
sweep = Sweep1D(
    slow_instrument.parameter,
    start, stop, step,
    inter_delay=2.0,        # 2s settling time
    outer_delay=5.0         # 5s for outer parameter (2D sweeps)
)
""",
        },
        "error_handling": {
            "description": "Error handling and recovery patterns",
            "basic": """# Basic error handling
try:
    init_database(db_name, exp_name, sample_name, sweep)
    sweep.start()
except Exception as e:
    print(f"Error during measurement: {e}")
    if sweep.progressState.state in (SweepState.RAMPING, SweepState.RUNNING):
        sweep.pause()
""",
            "graceful_stop": """# Graceful stopping
import signal

def signal_handler(sig, frame):
    print("Received interrupt signal, pausing measurement...")
    if 'sweep' in globals() and sweep.progressState.state in (SweepState.RAMPING, SweepState.RUNNING):
        sweep.pause()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Your measurement code here
sweep.start()
""",
            "recovery": """# Measurement recovery
# Check if measurement is still running
if sweep.progressState.state in (SweepState.RAMPING, SweepState.RUNNING):
    print("Measurement is running")
    print(f"Current status: {sweep}")
else:
    print("Measurement stopped")

# Resume if needed (for continual sweeps)
if sweep.progressState.state == SweepState.PAUSED and sweep.continual:
    print("Resuming measurement...")
    sweep.resume()
""",
        },
        "optimization_tips": [
            "Use plot_bin parameter to improve plotting performance for long measurements",
            "Set appropriate inter_delay for instrument settling times",
            "Use bidirectional=False for one-way sweeps to save time",
            "For 2D sweeps, use back_multiplier > 1 to speed up return sweeps",
            "Group related parameters when following multiple instruments",
            "Use continual=True for real-time monitoring applications",
            "Save data locally and backup to network storage periodically",
        ],
        "troubleshooting": {
            "slow_measurements": "Increase plot_bin, reduce inter_delay if safe",
            "plot_not_updating": "Check ensure_qt() is set, restart kernel if needed",
            "database_errors": "Check file permissions and disk space",
            "instrument_errors": "Verify connections and parameter limits",
            "memory_issues": "Use plot_bin parameter for long measurements",
        },
    }

    return json.dumps(template, indent=2)


# =============================================================================
# Data Access Templates - For loading saved data from QCodes database
# =============================================================================


def get_database_access0d_template() -> str:
    """Get template for loading Sweep0D data from QCodes database."""
    template = {
        "description": "Load Sweep0D (time-based) data from QCodes database",
        "data_structure": "data['dependent']['time'] for time array",
        "code": """from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
data = ds.get_parameter_data()

# Extract time and measured values
# Key: data is keyed by DEPENDENT param, not 'time'
first_param = list(data.keys())[0]
time = data[first_param]["time"]
values = data[first_param][first_param]

# Plot
import matplotlib.pyplot as plt
plt.plot(time, values)
plt.xlabel("Time (s)")
""",
        "gotchas": [
            "Time is accessed via data['dependent']['time'], NOT data['time']",
        ],
    }
    return json.dumps(template, indent=2)


def get_database_access1d_template() -> str:
    """Get template for loading Sweep1D data from QCodes database."""
    template = {
        "description": "Load Sweep1D data from QCodes database",
        "data_structure": "data['dependent']['setpoint'] for x, data['dependent']['dependent'] for y",
        "code": """from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
data = ds.get_parameter_data()

# Extract setpoint and measured values
# Key: access setpoint via dependent param key
dependent_name = "instr_measured"  # e.g., "lockin_x"
setpoint_name = "instr_swept"      # e.g., "gate_voltage"

x = data[dependent_name][setpoint_name]
y = data[dependent_name][dependent_name]

# Plot
import matplotlib.pyplot as plt
plt.plot(x, y)
""",
        "gotchas": [
            "Use data['dependent']['setpoint'], NOT data['setpoint']['dependent']",
        ],
    }
    return json.dumps(template, indent=2)


def get_database_access2d_template() -> str:
    """Get template for loading Sweep2D data from QCodes database."""
    template = {
        "description": "Load Sweep2D data from QCodes database",
        "critical_info": "Each run = ONE y-line. Full 2D requires loading ALL runs in experiment.",
        "single_run_code": """# Single run = one horizontal line at constant y
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at
import numpy as np

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
data = ds.get_parameter_data()

# Extract data - this is ONE y-line only
dependent = "instr_z"  # measured param
inner = "instr_x"      # fast axis (swept)
outer = "instr_y"      # slow axis (constant for this run)

x = data[dependent][inner]
y_value = np.unique(data[outer][outer])[0]  # Single y value
z = data[dependent][dependent]

print(f"This run: y = {y_value}, {len(x)} x-points")
# Plot as 1D line
""",
        "parent_group_code": """# Full 2D: Combine all runs in parent group
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at
import numpy as np
import matplotlib.pyplot as plt

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

# All run IDs in Sweep2D parent (same experiment)
run_ids = [6, 7, 8, 9, 10, 11]  # Adjust to actual IDs

all_x, all_y, all_z = [], [], []
for rid in run_ids:
    ds = load_by_id(rid)
    data = ds.get_parameter_data()
    all_x.extend(data["instr_z"]["instr_x"])
    all_y.extend(data["instr_y"]["instr_y"])  # y is separate dependent!
    all_z.extend(data["instr_z"]["instr_z"])

x, y, z = np.array(all_x), np.array(all_y), np.array(all_z)

# Scatter handles non-uniform grids from bidirectional sweeps
plt.scatter(x, y, c=z, s=10, cmap='viridis')
plt.colorbar()
""",
        "gotchas": [
            "Single run = ONE y-line, not full 2D grid",
            "Outer param (y) stored as SEPARATE dependent: data['y']['y']",
            "Bidirectional sweeps have extra points; use scatter not pcolormesh",
            "Full 2D requires combining all runs in same experiment",
        ],
    }
    return json.dumps(template, indent=2)


def get_database_access_simulsweep_template() -> str:
    """Get template for loading SimulSweep data from QCodes database."""
    template = {
        "description": "Load SimulSweep data from QCodes database",
        "data_structure": "Multiple setpoints swept simultaneously",
        "code": """from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
data = ds.get_parameter_data()

# SimulSweep: multiple setpoints, access via first dependent
first_dep = list(data.keys())[0]

# Setpoints (all swept simultaneously)
x1 = data[first_dep]["instr1_param"]
x2 = data[first_dep]["instr2_param"]

# Measured values - each is its own dependent
z1 = data["instr1_measured"]["instr1_measured"]
z2 = data["instr2_measured"]["instr2_measured"]

# Plot
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2)
axes[0].plot(x1, z1)
axes[1].plot(x2, z2)
""",
        "gotchas": [
            "Setpoints accessed via data['dependent']['setpoint']",
            "Each dependent param is its own outer key",
        ],
    }
    return json.dumps(template, indent=2)


def get_database_access_sweepqueue_template() -> str:
    """Get template for loading SweepQueue data from QCodes database."""
    template = {
        "description": "Load SweepQueue batch data from QCodes database",
        "info": "SweepQueue creates multiple consecutive runs, each may be different sweep type",
        "code": """from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

# SweepQueue batch: consecutive run IDs
run_ids = [4, 5, 6]  # Adjust to actual IDs

datasets = {}
for rid in run_ids:
    ds = load_by_id(rid)
    datasets[rid] = ds.get_parameter_data()
    print(f"Run {rid}: {len(ds)} points, params: {list(datasets[rid].keys())}")

# Access individual run
data = datasets[run_ids[0]]
# Then use appropriate pattern based on sweep type (0D/1D/2D/SimulSweep)
""",
        "gotchas": [
            "Each run in queue may be different sweep type",
            "Check run metadata to determine sweep type before loading",
            "Runs have 'launched_by: SweepQueue' in measureit metadata",
        ],
    }
    return json.dumps(template, indent=2)


def get_measureit_code_examples() -> str:
    """
    Get all available MeasureIt patterns in a structured format.

    Returns comprehensive examples covering all sweep types and patterns.
    """
    all_examples = {
        "description": "Complete MeasureIt code examples and patterns library",
        "version": "1.0.0",
        "categories": {
            "sweep0d": {
                "description": "Time-based monitoring patterns",
                "template": json.loads(get_sweep0d_template()),
            },
            "sweep1d": {
                "description": "Single parameter sweep patterns",
                "template": json.loads(get_sweep1d_template()),
            },
            "sweep2d": {
                "description": "2D parameter mapping patterns",
                "template": json.loads(get_sweep2d_template()),
            },
            "simulsweep": {
                "description": "Simultaneous parameter sweeping patterns",
                "template": json.loads(get_simulsweep_template()),
            },
            "sweepqueue": {
                "description": "Sequential measurement workflow patterns",
                "template": json.loads(get_sweepqueue_template()),
            },
            "common_patterns": {
                "description": "Best practices and common workflows",
                "template": json.loads(get_common_patterns_template()),
            },
        },
        "quick_reference": {
            "basic_imports": """# Essential MeasureIt imports
import os
from pathlib import Path
from measureit import Sweep0D, Sweep1D, Sweep2D, SimulSweep
from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry
from measureit.tools import init_database
""",
            "database_setup": """# Standard database initialization
database_name = "measurements.db"
exp_name = "experiment_name"
sample_name = "sample_name"
init_database(database_name, exp_name, sample_name, sweep_object)
""",
            "parameter_following": """# Follow parameters during measurement
sweep.follow_param(
    instrument.parameter1,
    instrument.parameter2,
    # Add more parameters as needed
)
""",
            "plotting_setup": """# Enable interactive plotting
ensure_qt()

# For 2D measurements, enable heatmap
sweep2d.follow_heatmap_param([primary_signal])
""",
        },
        "measurement_selection_guide": {
            "sweep0d": {
                "when_to_use": "Monitor parameters vs time",
                "examples": [
                    "Stability monitoring",
                    "Noise characterization",
                    "Long-term tracking",
                ],
                "key_parameters": ["inter_delay", "max_time", "plot_bin"],
            },
            "sweep1d": {
                "when_to_use": "Sweep one parameter while monitoring others",
                "examples": ["Gate voltage sweeps", "Frequency response", "IV curves"],
                "key_parameters": ["start", "stop", "step", "bidirectional"],
            },
            "sweep2d": {
                "when_to_use": "Create 2D maps by sweeping two parameters",
                "examples": ["Stability diagrams", "Gate maps", "Frequency vs power"],
                "key_parameters": [
                    "inner/outer ranges",
                    "step sizes",
                    "back_multiplier",
                ],
            },
            "simulsweep": {
                "when_to_use": "Sweep multiple parameters simultaneously",
                "examples": [
                    "Correlated sweeps",
                    "Maintaining ratios",
                    "Diagonal cuts",
                ],
                "key_parameters": ["parameter_dict", "step coordination"],
            },
            "sweepqueue": {
                "when_to_use": "Chain multiple measurements sequentially",
                "examples": [
                    "Automated protocols",
                    "Multi-step characterization",
                    "Overnight runs",
                ],
                "key_parameters": ["queue composition", "database entries"],
            },
        },
        "code_generation_hints": {
            "ai_instructions": [
                "Always use appropriate sweep type based on user requirements",
                "Include proper database initialization with meaningful names",
                "Set realistic step sizes and delays for instrument safety",
                "Add parameter following for relevant measurements",
                "Include plotting setup for real-time monitoring",
                "Consider using SweepQueue for complex measurement protocols",
                "Always include proper imports at the beginning",
                "Use descriptive variable names and comments",
            ],
            "safety_guidelines": [
                "Check instrument parameter limits before sweeping",
                "Use safe step sizes to avoid damaging equipment",
                "Include proper settling delays (inter_delay, outer_delay)",
                "Validate sweep ranges against instrument specifications",
                "Consider using bidirectional=False for sensitive parameters",
            ],
            "performance_tips": [
                "Use plot_bin parameter for long measurements",
                "Adjust inter_delay based on instrument response time",
                "For 2D sweeps, use back_multiplier > 1 for faster returns",
            ],
        },
        "data_loading_guidance": {
            "note": "Use separate resources for detailed data loading templates",
            "resources": [
                "resource://database_access0d_template",
                "resource://database_access1d_template",
                "resource://database_access2d_template",
                "resource://database_access_simulsweep_template",
                "resource://database_access_sweepqueue_template",
            ],
            "critical_rule": "data['dependent']['setpoint'], NOT data['setpoint']['dependent']",
        },
    }

    return json.dumps(all_examples, indent=2)
