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

# To pause: s.stop()
""",
        "tips": [
            "Always call init_database before s.start()",
            "`print(s.progressState)` to check the state",
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
        "basic_pattern": """# Sweep1D - Single parameter sweep
import os
from measureit import Sweep1D
from measureit.tools import ensure_qt, init_database

# Configure sweep
s = Sweep1D(
    gate.voltage,           # Parameter to sweep
    start=-1.0,             # Start value
    stop=1.0,               # Stop value
    step=0.01,              # Step Size(*not step number!*) between measurements
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

# To pause: s.stop()
""",
        "tips": [
            "Always call init_database before s.start()",
            "`print(s.progressState)` to check the state",
            "continual=True will sweep for indefinite time until manual stop",
        ],
    }

    return json.dumps(template, indent=2)


def get_sweep2d_template() -> str:
    """
    Get Sweep2D template with common patterns for 2D parameter mapping.

    Returns structured examples for 2D parameter sweeps.
    """
    template = {
        "description": "Sweep2D - Create 2D maps by sweeping two parameters, inner and outer parameter",
        "basic_pattern": """# Sweep2D - 2D parameter mapping
import os
from measureit import Sweep2D
from measureit.tools import ensure_qt, init_database

# Define sweep parameters
inner_param = gate1.voltage     # Fast axis (swept back/forth)
inner_start = -1.0
inner_end = 1.0
inner_step = 0.02              # Step Size(*not step number!*)

outer_param = gate2.voltage     # Slow axis (stepped)
outer_start = -0.5
outer_end = 0.5
outer_step = 0.05              # Step Size(*not step number!*)

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

# To pause: s.stop()
""",
        "tips": [
            "Always call init_database before s.start()",
            "`print(s.progressState)` to check the state",
            "continual=True will sweep for indefinite time until manual stop",
            "Inner parameter is swept relatively rapidly back and forth",
            "back_multiplier speeds up return sweeps",
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
        "description": "SimulSweep - Sweep multiple parameters together, rather than sweep inner and outer parameters",
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

# To pause: s.stop()
""",
        "tips": [
            "Always call init_database before s.start()",
            "`print(s.progressState)` to check the state",
            "continual=True will sweep for indefinite time until manual stop",
            "All parameters must have same number of steps",
            "Calculate steps: (stop-start)/step should be equal for all parameters",
            "Useful for diagonal cuts through multi-dimensional parameter space",
            "Good for maintaining parameter relationships/ratios",
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

# To pause: sq.stop()
""",
        "tips": [
            "Use += operator to add items to queue",
            "Functions can take arguments: sq += (func, arg1, arg2)",
            "DatabaseEntry required for each sweep that saves data",
            "Queue is iterable - you can inspect contents before starting",
            "`print(s.progressState)` to check the state",
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
        },
        "troubleshooting": {
            "slow_measurements": "Increase plot_bin, reduce inter_delay if safe",
            "database_errors": "Check relative path vs absolute path",
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
        "data_structure": "DataFrame with time as first column, measured params as other columns",
        "code": """from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
df = ds.to_pandas_dataframe().reset_index()

# DataFrame columns: time + all measured parameters
print("Columns:", df.columns.tolist())
print(df.head())

# Optional: Plot (uncomment to use)
# import matplotlib.pyplot as plt
# df.plot(x="time", y=df.columns[1])
""",
        "gotchas": [
            "Use to_pandas_dataframe().reset_index() for easy access to all data",
        ],
    }
    return json.dumps(template, indent=2)


def get_database_access1d_template() -> str:
    """Get template for loading Sweep1D data from QCodes database."""
    template = {
        "description": "Load Sweep1D data from QCodes database",
        "data_structure": "DataFrame with setpoint as first column, then time + measured params",
        "code": """from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
df = ds.to_pandas_dataframe().reset_index()

# DataFrame columns: setpoint + time + all measured parameters
print("Columns:", df.columns.tolist())
print(df.head())

# Optional: Plot (uncomment to use)
# import matplotlib.pyplot as plt
# df.plot(x=df.columns[0], y=df.columns[2])
""",
        "gotchas": [
            "Use to_pandas_dataframe().reset_index() for easy access to all data",
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

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
df = ds.to_pandas_dataframe().reset_index()

# DataFrame columns: x (inner setpoint) + y (outer) + measured params
print("Columns:", df.columns.tolist())
print(df.head())
""",
        "parent_group_code": """# Full 2D: Combine all runs in parent group
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at
import pandas as pd

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

# All run IDs in Sweep2D parent (same experiment)
run_ids = [6, 7, 8, 9, 10, 11]  # Adjust to actual IDs

# Combine all runs into one DataFrame
dfs = []
for rid in run_ids:
    ds = load_by_id(rid)
    df = ds.to_pandas_dataframe().reset_index()
    dfs.append(df)

df = pd.concat(dfs, ignore_index=True)

print("Columns:", df.columns.tolist())
print("Shape:", df.shape)

# Optional: Scatter plot (uncomment to use)
# import matplotlib.pyplot as plt
# x_col, y_col, z_col = df.columns[0], df.columns[1], df.columns[2]
# plt.scatter(df[x_col], df[y_col], c=df[z_col], s=10, cmap='viridis')
# plt.colorbar()
""",
        "gotchas": [
            "Single run = ONE y-line, not full 2D grid",
            "Use pd.concat() to combine multiple runs into full 2D data",
            "Use to_pandas_dataframe().reset_index() for easy access",
        ],
    }
    return json.dumps(template, indent=2)


def get_database_access_simulsweep_template() -> str:
    """Get template for loading SimulSweep data from QCodes database."""
    template = {
        "description": "Load SimulSweep data from QCodes database",
        "data_structure": "DataFrame with all setpoints and measured params as columns",
        "code": """from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "path/to/database.db"
initialise_or_create_database_at(db_path)

ds = load_by_id(RUN_ID)
df = ds.to_pandas_dataframe().reset_index()

# DataFrame columns: setpoints (swept simultaneously) + measured params
print("Columns:", df.columns.tolist())
print(df.head())

# Optional: Plot (uncomment to use)
# import matplotlib.pyplot as plt
# df.plot(x=df.columns[0], y=df.columns[1])
""",
        "gotchas": [
            "Use to_pandas_dataframe().reset_index() for easy access to all data",
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
        "measurement_sweep_guidance": {
            "note": "Use separate resources for detailed sweep templates",
            "resources": [
                "resource://measureit_sweep0d_template",
                "resource://measureit_sweep1d_template",
                "resource://measureit_sweep2d_template",
                "resource://measureit_simulsweep_template",
                "resource://measureit_sweepqueue_template",
                "resource://measureit_common_patterns_template",
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
