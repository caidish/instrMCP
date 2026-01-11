"""
Comprehensive code suggestion generation for QCodes datasets.

Provides intelligent code generation based on sweep type with automatic
grouping of related sweeps (Sweep2D parent runs, SweepQueue batches).
"""

import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class SweepType(Enum):
    """Enumeration of supported sweep types from MeasureIt."""

    SWEEP_0D = "Sweep0D"
    SWEEP_1D = "Sweep1D"
    SWEEP_2D = "Sweep2D"
    SIMUL_SWEEP = "SimulSweep"
    QCODES = "qcodes"  # Raw QCodes measurement (no MeasureIt metadata)
    UNKNOWN = "unknown"


@dataclass
class SweepInfo:
    """Information about a single sweep/dataset."""

    run_id: int
    exp_id: int
    exp_name: str
    sample_name: str
    sweep_type: SweepType
    measureit_metadata: Optional[dict] = None
    setpoints: list = field(default_factory=list)
    dependents: list = field(default_factory=list)
    launched_by: Optional[str] = None
    inner_sweep: Optional[dict] = None
    outer_sweep: Optional[dict] = None
    set_param: Optional[dict] = None
    set_params: Optional[dict] = None
    follow_params: Optional[dict] = None


@dataclass
class SweepGroup:
    """A group of related sweeps (e.g., Sweep2D parent, SweepQueue batch)."""

    group_type: str  # "sweep2d_parent", "sweep_queue", "single"
    sweep_type: SweepType
    run_ids: list
    exp_id: int
    exp_name: str
    sample_name: str
    sweeps: list  # List of SweepInfo
    description: str = ""


def _parse_sweep_type(measureit_metadata: Optional[dict]) -> SweepType:
    """Parse sweep type from MeasureIt metadata."""
    if not measureit_metadata:
        return SweepType.QCODES

    sweep_class = measureit_metadata.get("class", "")
    type_map = {
        "Sweep0D": SweepType.SWEEP_0D,
        "Sweep1D": SweepType.SWEEP_1D,
        "Sweep2D": SweepType.SWEEP_2D,
        "SimulSweep": SweepType.SIMUL_SWEEP,
    }
    return type_map.get(sweep_class, SweepType.UNKNOWN)


def _get_all_runs_info(database_path: str) -> list[SweepInfo]:
    """Extract sweep information for all runs in the database."""
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # Get all runs with their metadata
    cursor.execute(
        """
        SELECT r.run_id, r.exp_id, r.run_description, r.measureit,
               e.name as exp_name, e.sample_name
        FROM runs r
        JOIN experiments e ON r.exp_id = e.exp_id
        ORDER BY r.run_id
    """
    )

    sweeps = []
    for row in cursor.fetchall():
        run_id, exp_id, run_desc, measureit, exp_name, sample_name = row

        # Parse run description for parameters
        setpoints = []
        dependents = []
        if run_desc:
            try:
                desc_data = json.loads(run_desc)
                interdeps = desc_data.get("interdependencies", {})
                paramspecs = interdeps.get("paramspecs", [])
                for p in paramspecs:
                    if not p.get("depends_on"):
                        setpoints.append(p["name"])
                    else:
                        dependents.append(p["name"])
            except json.JSONDecodeError:
                pass

        # Parse MeasureIt metadata
        measureit_metadata = None
        launched_by = None
        inner_sweep = None
        outer_sweep = None
        set_param = None
        set_params = None
        follow_params = None

        if measureit:
            try:
                measureit_metadata = json.loads(measureit)
                attrs = measureit_metadata.get("attributes", {})
                launched_by = attrs.get("launched_by")
                inner_sweep = measureit_metadata.get("inner_sweep")
                outer_sweep = measureit_metadata.get("outer_sweep")
                set_param = measureit_metadata.get("set_param")
                set_params = measureit_metadata.get("set_params")
                follow_params = measureit_metadata.get("follow_params")
            except json.JSONDecodeError:
                pass

        sweep_type = _parse_sweep_type(measureit_metadata)

        sweeps.append(
            SweepInfo(
                run_id=run_id,
                exp_id=exp_id,
                exp_name=exp_name,
                sample_name=sample_name,
                sweep_type=sweep_type,
                measureit_metadata=measureit_metadata,
                setpoints=setpoints,
                dependents=dependents,
                launched_by=launched_by,
                inner_sweep=inner_sweep,
                outer_sweep=outer_sweep,
                set_param=set_param,
                set_params=set_params,
                follow_params=follow_params,
            )
        )

    conn.close()
    return sweeps


def analyze_sweep_groups(database_path: str) -> list[SweepGroup]:
    """
    Analyze all sweeps in the database and group related runs.

    Groups are formed for:
    - Sweep2D parent: Multiple Sweep2D runs in the same experiment
    - SweepQueue: Runs launched by SweepQueue in sequence
    - Single: Individual sweeps that don't form groups

    Args:
        database_path: Path to the QCodes database

    Returns:
        List of SweepGroup objects representing grouped sweeps
    """
    sweeps = _get_all_runs_info(database_path)
    if not sweeps:
        return []

    groups = []
    processed_ids = set()

    # Group Sweep2D runs by experiment
    sweep2d_by_exp = {}
    for sweep in sweeps:
        if sweep.sweep_type == SweepType.SWEEP_2D:
            key = sweep.exp_id
            if key not in sweep2d_by_exp:
                sweep2d_by_exp[key] = []
            sweep2d_by_exp[key].append(sweep)

    for exp_id, exp_sweeps in sweep2d_by_exp.items():
        if len(exp_sweeps) > 1:
            # This is a Sweep2D parent group
            run_ids = [s.run_id for s in exp_sweeps]
            groups.append(
                SweepGroup(
                    group_type="sweep2d_parent",
                    sweep_type=SweepType.SWEEP_2D,
                    run_ids=run_ids,
                    exp_id=exp_id,
                    exp_name=exp_sweeps[0].exp_name,
                    sample_name=exp_sweeps[0].sample_name,
                    sweeps=exp_sweeps,
                    description=f"Sweep2D parent with {len(exp_sweeps)} runs",
                )
            )
            processed_ids.update(run_ids)
        else:
            # Single Sweep2D, process later
            pass

    # Group SweepQueue runs (consecutive runs with launched_by="SweepQueue")
    # Note: SweepQueue runs may span multiple experiments, so we group by
    # consecutive run IDs rather than by experiment
    queue_runs = []
    for sweep in sweeps:
        if sweep.launched_by == "SweepQueue" and sweep.run_id not in processed_ids:
            queue_runs.append(sweep)

    if queue_runs:
        # Group consecutive queue runs (regardless of experiment)
        current_group = [queue_runs[0]]
        for sweep in queue_runs[1:]:
            # Check if this run is consecutive (run_id differs by 1)
            if sweep.run_id == current_group[-1].run_id + 1:
                current_group.append(sweep)
            else:
                # Save current group and start new one
                if len(current_group) >= 1:  # Include even single queue runs
                    run_ids = [s.run_id for s in current_group]
                    sweep_types = list(set(s.sweep_type.value for s in current_group))
                    groups.append(
                        SweepGroup(
                            group_type="sweep_queue",
                            sweep_type=current_group[0].sweep_type,
                            run_ids=run_ids,
                            exp_id=current_group[0].exp_id,
                            exp_name=current_group[0].exp_name,
                            sample_name=current_group[0].sample_name,
                            sweeps=current_group,
                            description=f"SweepQueue batch: {len(current_group)} runs ({', '.join(sweep_types)})",
                        )
                    )
                    processed_ids.update(run_ids)
                current_group = [sweep]

        # Handle last group - always save queue runs
        if current_group:
            run_ids = [s.run_id for s in current_group]
            sweep_types = list(set(s.sweep_type.value for s in current_group))
            groups.append(
                SweepGroup(
                    group_type="sweep_queue",
                    sweep_type=current_group[0].sweep_type,
                    run_ids=run_ids,
                    exp_id=current_group[0].exp_id,
                    exp_name=current_group[0].exp_name,
                    sample_name=current_group[0].sample_name,
                    sweeps=current_group,
                    description=f"SweepQueue batch: {len(current_group)} runs ({', '.join(sweep_types)})",
                )
            )
            processed_ids.update(run_ids)

    # Add remaining sweeps as single groups
    for sweep in sweeps:
        if sweep.run_id not in processed_ids:
            groups.append(
                SweepGroup(
                    group_type="single",
                    sweep_type=sweep.sweep_type,
                    run_ids=[sweep.run_id],
                    exp_id=sweep.exp_id,
                    exp_name=sweep.exp_name,
                    sample_name=sweep.sample_name,
                    sweeps=[sweep],
                    description=f"Single {sweep.sweep_type.value}",
                )
            )

    return sorted(groups, key=lambda g: min(g.run_ids))


def _generate_sweep0d_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a Sweep0D dataset."""
    follow_params = sweep.follow_params or {}
    param_names = list(follow_params.keys())

    # First follow param is used as reference for extracting time
    first_param = param_names[0].replace(".", "_") if param_names else "measured"

    param_vars = []
    for p in param_names:
        var_name = p.replace(".", "_")
        param_vars.append(f'{var_name} = data["{var_name}"]["{var_name}"]')

    param_code = "\n".join(param_vars) if param_vars else "# No follow parameters"

    return f"""# Load Sweep0D dataset (time-based measurement)
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
data = ds.get_parameter_data()

# Time array (extracted from first dependent parameter)
time = data["{first_param}"]["time"]

# Measured parameters
{param_code}

# Quick plot
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.set_xlabel("Time (s)")
ax.set_ylabel("Value (a.u.)")
# ax.plot(time, {first_param}, label="{first_param}")
# ax.legend()
"""


def _generate_sweep1d_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a Sweep1D dataset."""
    set_param = sweep.set_param or {}
    param_name = set_param.get("param", "x")
    instr_name = set_param.get("instr_name", "instr")
    setpoint_name = f"{instr_name}_{param_name}"

    follow_params = sweep.follow_params or {}
    param_names = list(follow_params.keys())
    first_param = param_names[0].replace(".", "_") if param_names else "measured"

    param_vars = []
    for p in param_names:
        var_name = p.replace(".", "_")
        param_vars.append(f'{var_name} = data["{var_name}"]["{var_name}"]')

    param_code = "\n".join(param_vars) if param_vars else "# No follow parameters"

    return f"""# Load Sweep1D dataset
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
data = ds.get_parameter_data()

# Setpoint array (extracted from first dependent parameter)
{setpoint_name} = data["{first_param}"]["{setpoint_name}"]

# Measured parameters
{param_code}

# Quick plot
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.set_xlabel("{param_name} ({instr_name})")
ax.set_ylabel("Value (a.u.)")
# ax.plot({setpoint_name}, {first_param}, label="{first_param}")
# ax.legend()
"""


def _generate_sweep2d_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a single Sweep2D dataset.

    Note: In MeasureIt, each Sweep2D run typically contains only ONE y-line
    (one value of the outer sweep parameter). The complete 2D data is split
    across multiple runs in the same experiment (Sweep2D parent group).
    """
    inner = sweep.inner_sweep or {}
    outer = sweep.outer_sweep or {}

    inner_param = inner.get("param", "x")
    inner_instr = inner.get("instr_name", "instr")
    inner_name = f"{inner_instr}_{inner_param}"

    outer_param = outer.get("param", "y")
    outer_instr = outer.get("instr_name", "instr")
    outer_name = f"{outer_instr}_{outer_param}"

    follow_params = sweep.follow_params or {}
    first_follow = list(follow_params.keys())[0] if follow_params else "measured"
    first_follow_var = first_follow.replace(".", "_")

    return f"""# Load Sweep2D dataset (single run = one y-line)
# NOTE: This run contains only ONE value of {outer_param} (outer sweep parameter).
# For complete 2D data, load all Sweep2D runs in this experiment and combine them.
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at
import numpy as np

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
data = ds.get_parameter_data()

# Extract data - this is ONE horizontal line at a single y value
# Inner sweep ({inner_param}) is the x-axis, outer ({outer_param}) is constant for this run
{inner_name} = data["{first_follow_var}"]["{inner_name}"]
{outer_name} = data["{outer_name}"]["{outer_name}"]
{first_follow_var} = data["{first_follow_var}"]["{first_follow_var}"]

# Check y-value for this run
y_value = np.unique({outer_name})[0]
print(f"This run is at {outer_param} = {{y_value}}")
print(f"X range: [{{{inner_name}.min():.3f}}, {{{inner_name}.max():.3f}}], {{len({inner_name})}} points")

# Quick 1D line plot (since this is just one y-line)
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot({inner_name}, {first_follow_var}, 'o-', markersize=3)
ax.set_xlabel("{inner_param} ({inner_instr})")
ax.set_ylabel("{first_follow_var}")
ax.set_title(f"Sweep2D run {sweep.run_id}: {outer_param} = {{y_value}}")
"""


def _generate_sweep2d_parent_code(group: SweepGroup, db_path: str) -> str:
    """Generate code for loading a Sweep2D parent (multiple 2D sweeps).

    In MeasureIt, a Sweep2D parent group consists of multiple runs, where each
    run contains ONE y-line (one value of the outer sweep parameter). This
    function generates code to combine all runs into a complete 2D dataset.
    """
    first_sweep = group.sweeps[0]
    inner = first_sweep.inner_sweep or {}
    outer = first_sweep.outer_sweep or {}

    inner_param = inner.get("param", "x")
    inner_instr = inner.get("instr_name", "instr")
    inner_name = f"{inner_instr}_{inner_param}"

    outer_param = outer.get("param", "y")
    outer_instr = outer.get("instr_name", "instr")
    outer_name = f"{outer_instr}_{outer_param}"

    follow_params = first_sweep.follow_params or {}
    first_follow = list(follow_params.keys())[0] if follow_params else "measured"
    first_follow_var = first_follow.replace(".", "_")

    run_ids_str = ", ".join(str(r) for r in group.run_ids)

    return f"""# Load Sweep2D Parent - {len(group.run_ids)} runs in experiment "{group.exp_name}"
# Sample: {group.sample_name}
# Each run contains ONE y-line; combine them for the full 2D dataset.
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at
import numpy as np
import matplotlib.pyplot as plt

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

# All run IDs in this Sweep2D parent (each run = one y-line)
run_ids = [{run_ids_str}]

# Collect data from all runs
all_x = []
all_y = []
all_z = []

for run_id in run_ids:
    ds = load_by_id(run_id)
    data = ds.get_parameter_data()

    # Each run has one y value (outer sweep) and many x values (inner sweep)
    x = data["{first_follow_var}"]["{inner_name}"]
    y = data["{outer_name}"]["{outer_name}"]
    z = data["{first_follow_var}"]["{first_follow_var}"]

    all_x.extend(x)
    all_y.extend(y)
    all_z.extend(z)

# Convert to numpy arrays
{inner_name} = np.array(all_x)
{outer_name} = np.array(all_y)
{first_follow_var} = np.array(all_z)

# Get unique values for the grid
x_unique = np.unique({inner_name})
y_unique = np.unique({outer_name})
n_x = len(x_unique)
n_y = len(y_unique)

print(f"Combined 2D grid: {{n_x}} x-points × {{n_y}} y-points = {{n_x * n_y}} total")
print(f"X ({inner_param}) range: [{{x_unique[0]:.3f}}, {{x_unique[-1]:.3f}}]")
print(f"Y ({outer_param}) range: [{{y_unique[0]:.3f}}, {{y_unique[-1]:.3f}}]")

# Create 2D plot using scatter (handles non-uniform grids)
fig, ax = plt.subplots(figsize=(8, 6))
scatter = ax.scatter({inner_name}, {outer_name}, c={first_follow_var}, s=10, cmap='viridis')
ax.set_xlabel("{inner_param} ({inner_instr})")
ax.set_ylabel("{outer_param} ({outer_instr})")
ax.set_title("Sweep2D Parent: {first_follow_var}")
plt.colorbar(scatter, ax=ax, label="{first_follow_var}")

# Alternative: If data is on a regular grid, use pcolormesh for smoother visualization
# try:
#     Z = {first_follow_var}.reshape(n_y, n_x)
#     fig2, ax2 = plt.subplots()
#     im = ax2.pcolormesh(x_unique, y_unique, Z, shading='auto', cmap='viridis')
#     plt.colorbar(im, ax=ax2)
# except ValueError:
#     print("Data not on regular grid, using scatter plot")
"""


def _generate_simulsweep_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a SimulSweep dataset."""
    set_params = sweep.set_params or {}
    param_names = list(set_params.keys())

    follow_params = sweep.follow_params or {}
    follow_names = list(follow_params.keys())
    first_follow = follow_names[0].replace(".", "_") if follow_names else "measured"

    # Get the first setpoint as the x-axis reference
    first_setpoint = param_names[0].replace(".", "_") if param_names else "x"

    setpoint_code = []
    for p in param_names:
        var_name = p.replace(".", "_")
        setpoint_code.append(f'{var_name} = data["{first_follow}"]["{var_name}"]')

    follow_code = []
    for p in follow_names:
        var_name = p.replace(".", "_")
        follow_code.append(f'{var_name} = data["{var_name}"]["{var_name}"]')

    all_code = "\n".join(setpoint_code + follow_code)

    return f"""# Load SimulSweep dataset (simultaneous parameter sweep)
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
data = ds.get_parameter_data()

# Extract setpoints and measured parameters
{all_code}

# Quick plot
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.set_xlabel("{first_setpoint}")
ax.set_ylabel("Value (a.u.)")
# ax.plot({first_setpoint}, {first_follow}, label="{first_follow}")
# ax.legend()
"""


def _generate_sweep_queue_code(group: SweepGroup, db_path: str) -> str:
    """Generate code for loading a SweepQueue batch."""
    first_sweep = group.sweeps[0]
    run_ids_str = ", ".join(str(r) for r in group.run_ids)

    # Determine the sweep type in the queue
    sweep_types = set(s.sweep_type.value for s in group.sweeps)
    sweep_type_desc = ", ".join(sweep_types)

    return f"""# Load SweepQueue batch - {len(group.run_ids)} runs ({sweep_type_desc})
# Experiment: "{group.exp_name}", Sample: {group.sample_name}
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at
import matplotlib.pyplot as plt

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

# All run IDs in this SweepQueue batch
run_ids = [{run_ids_str}]

# Load all datasets
datasets = {{run_id: load_by_id(run_id) for run_id in run_ids}}

# Extract data from each run
all_data = {{}}
for run_id, ds in datasets.items():
    all_data[run_id] = ds.get_parameter_data()
    print(f"Run {{run_id}}: {{len(ds)}} points")

# Access individual run data:
# data = all_data[run_ids[0]]  # First run in queue

# Plot all runs together
fig, axes = plt.subplots(1, len(run_ids), figsize=(4*len(run_ids), 3))
if len(run_ids) == 1:
    axes = [axes]

for ax, run_id in zip(axes, run_ids):
    ax.set_title(f"Run {{run_id}}")
    # Add your plotting code here based on sweep type

plt.tight_layout()
"""


def _generate_qcodes_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a raw QCodes dataset (no MeasureIt metadata)."""
    setpoints = sweep.setpoints
    dependents = sweep.dependents

    setpoint_str = setpoints[0] if setpoints else "setpoint"
    dependent_code = []
    for d in dependents:
        dependent_code.append(f'{d} = data["{setpoint_str}"]["{d}"]')

    all_code = (
        "\n".join(dependent_code)
        if dependent_code
        else "# Extract parameters from data dict"
    )

    return f"""# Load QCodes dataset (no MeasureIt metadata)
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
data = ds.get_parameter_data()

# Setpoint: {setpoint_str}
{setpoint_str} = data["{setpoint_str}"]["{setpoint_str}"]

# Dependent parameters
{all_code}

# Explore available parameters
print("Available parameters:", list(data.keys()))
for param, values in data.items():
    print(f"  {{param}}: {{list(values.keys())}}")
"""


def generate_code_suggestion(
    database_path: str,
    run_id: Optional[int] = None,
    include_groups: bool = True,
) -> dict:
    """
    Generate comprehensive code suggestions for loading QCodes datasets.

    This function analyzes the database and generates appropriate loading code
    based on sweep type, automatically grouping related sweeps.

    Args:
        database_path: Path to the QCodes database
        run_id: Specific run ID to generate code for. If None, analyzes all runs.
        include_groups: If True, include grouped sweeps (Sweep2D parent, SweepQueue)

    Returns:
        Dictionary containing:
        - "groups": List of sweep groups with their code suggestions
        - "summary": Overall database summary
        - "code_by_run_id": Dict mapping run_id to code suggestion
    """
    db_path = str(Path(database_path).resolve())

    # Analyze all sweeps and groups
    groups = analyze_sweep_groups(db_path)

    result = {
        "database_path": db_path,
        "groups": [],
        "summary": {
            "total_groups": len(groups),
            "total_runs": sum(len(g.run_ids) for g in groups),
            "group_types": {},
            "sweep_types": {},
        },
        "code_by_run_id": {},
    }

    # Count group and sweep types
    for group in groups:
        gt = group.group_type
        st = group.sweep_type.value
        result["summary"]["group_types"][gt] = (
            result["summary"]["group_types"].get(gt, 0) + 1
        )
        result["summary"]["sweep_types"][st] = result["summary"]["sweep_types"].get(
            st, 0
        ) + len(group.run_ids)

    # Generate code for each group
    for group in groups:
        # If specific run_id requested, skip groups that don't contain it
        if run_id is not None and run_id not in group.run_ids:
            continue

        group_info = {
            "group_type": group.group_type,
            "sweep_type": group.sweep_type.value,
            "run_ids": group.run_ids,
            "exp_id": group.exp_id,
            "exp_name": group.exp_name,
            "sample_name": group.sample_name,
            "description": group.description,
            "code": "",
        }

        # Generate appropriate code based on group type
        if group.group_type == "sweep2d_parent" and include_groups:
            group_info["code"] = _generate_sweep2d_parent_code(group, db_path)
        elif group.group_type == "sweep_queue" and include_groups:
            group_info["code"] = _generate_sweep_queue_code(group, db_path)
        else:
            # Single sweep or groups disabled
            sweep = group.sweeps[0]
            if sweep.sweep_type == SweepType.SWEEP_0D:
                group_info["code"] = _generate_sweep0d_code(sweep, db_path)
            elif sweep.sweep_type == SweepType.SWEEP_1D:
                group_info["code"] = _generate_sweep1d_code(sweep, db_path)
            elif sweep.sweep_type == SweepType.SWEEP_2D:
                group_info["code"] = _generate_sweep2d_code(sweep, db_path)
            elif sweep.sweep_type == SweepType.SIMUL_SWEEP:
                group_info["code"] = _generate_simulsweep_code(sweep, db_path)
            else:
                group_info["code"] = _generate_qcodes_code(sweep, db_path)

        result["groups"].append(group_info)

        # Also map individual run_ids to their code
        for rid in group.run_ids:
            result["code_by_run_id"][rid] = group_info["code"]

    return result


def generate_single_dataset_code(
    database_path: str,
    run_id: int,
    dataset_info: Optional[dict] = None,
) -> str:
    """
    Generate code suggestion for a single dataset.

    This is a simpler interface for generating code for one dataset,
    compatible with the existing database_tools._generate_code_suggestion.

    Args:
        database_path: Path to the QCodes database
        run_id: Dataset run ID
        dataset_info: Optional pre-fetched dataset info dict

    Returns:
        Python code string for loading the dataset
    """
    result = generate_code_suggestion(
        database_path=database_path,
        run_id=run_id,
        include_groups=True,
    )

    return result.get("code_by_run_id", {}).get(
        run_id, _generate_fallback_code(database_path, run_id)
    )


def _generate_fallback_code(db_path: str, run_id: int) -> str:
    """Generate basic fallback code when sweep type cannot be determined."""
    return f"""# Load dataset
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({run_id})
data = ds.get_parameter_data()

# Explore available parameters
print("Available parameters:", list(data.keys()))
for param, values in data.items():
    print(f"  {{param}}: {{list(values.keys())}}")
"""
