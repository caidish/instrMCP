"""
Comprehensive code suggestion generation for QCodes datasets.

Provides intelligent code generation based on sweep type with automatic
grouping of related sweeps (Sweep2D parent runs, SweepQueue batches).

Thread Safety Fix:
    This module uses the canonical thread_safe_db_connection from
    query_tools to avoid "SQLite objects created in a thread can only be
    used in that same thread" errors.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Import the canonical thread-safe connection helper
from ..query_tools import thread_safe_db_connection


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
    """Extract sweep information for all runs in the database.

    Uses thread_safe_db_connection to ensure the MCP server can safely
    access the database from a different thread than the Jupyter kernel.
    """
    sweeps = []

    with thread_safe_db_connection(database_path) as conn:
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

        for row in cursor.fetchall():
            # Access by column name thanks to Row factory
            row_dict = dict(row)
            run_id = row_dict["run_id"]
            exp_id = row_dict["exp_id"]
            run_desc = row_dict["run_description"]
            measureit = row_dict["measureit"]
            exp_name = row_dict["exp_name"]
            sample_name = row_dict["sample_name"]

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
    # Extract column info from metadata
    follow_params = sweep.follow_params or {}
    follow_cols = [p.replace(".", "_") for p in follow_params.keys()]
    first_follow = follow_cols[0] if follow_cols else "measured"
    follow_comment = (
        f"# Measured: {follow_cols}" if follow_cols else "# Measured: (see df.columns)"
    )

    return f"""# Load Sweep0D dataset (time-based measurement)
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
df = ds.to_pandas_dataframe().reset_index()

# Columns: time + measured parameters
{follow_comment}
print("Columns:", df.columns.tolist())
print(df.head())

# Optional: Quick plot (uncomment to use)
# import matplotlib.pyplot as plt
# df.plot(x="time", y="{first_follow}")
"""


def _generate_sweep1d_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a Sweep1D dataset."""
    # Extract column info from metadata
    set_params = sweep.set_params or {}
    follow_params = sweep.follow_params or {}

    set_cols = [p.replace(".", "_") for p in set_params.keys()]
    follow_cols = [p.replace(".", "_") for p in follow_params.keys()]
    first_set = set_cols[0] if set_cols else "x"
    first_follow = follow_cols[0] if follow_cols else "measured"

    set_comment = f"# Swept: {set_cols}" if set_cols else "# Swept: (see df.columns)"
    follow_comment = (
        f"# Measured: {follow_cols}" if follow_cols else "# Measured: (see df.columns)"
    )

    return f"""# Load Sweep1D dataset
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
df = ds.to_pandas_dataframe().reset_index()

# Columns: swept parameter + time + measured parameters
{set_comment}
{follow_comment}
print("Columns:", df.columns.tolist())
print(df.head())

# Optional: Quick plot (uncomment to use)
# import matplotlib.pyplot as plt
# df.plot(x="{first_set}", y="{first_follow}")
"""


def _generate_sweep2d_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a single Sweep2D dataset.

    Note: In MeasureIt, each Sweep2D run typically contains only ONE y-line
    (one value of the outer sweep parameter). The complete 2D data is split
    across multiple runs in the same experiment (Sweep2D parent group).
    """
    # Extract column info from metadata
    inner = sweep.inner_sweep or {}
    outer = sweep.outer_sweep or {}
    follow_params = sweep.follow_params or {}

    inner_col = f"{inner.get('instr_name', 'instr')}_{inner.get('param', 'x')}"
    outer_col = f"{outer.get('instr_name', 'instr')}_{outer.get('param', 'y')}"
    follow_cols = [p.replace(".", "_") for p in follow_params.keys()]
    first_follow = follow_cols[0] if follow_cols else "measured"

    inner_comment = f"# Inner (x, fast): {inner_col}"
    outer_comment = f"# Outer (y, slow): {outer_col}"
    follow_comment = (
        f"# Measured: {follow_cols}" if follow_cols else "# Measured: (see df.columns)"
    )

    return f"""# Load Sweep2D dataset (single run = one y-line)
# NOTE: Each Sweep2D run contains only ONE y-value (outer sweep).
# For complete 2D data, load all runs in the experiment and combine with pd.concat().
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
df = ds.to_pandas_dataframe().reset_index()

# Columns from metadata:
{inner_comment}
{outer_comment}
{follow_comment}
print("Columns:", df.columns.tolist())
print(df.head())

# Optional: Quick 1D line plot (uncomment to use)
# import matplotlib.pyplot as plt
# df.plot(x="{inner_col}", y="{first_follow}")
"""


def _generate_sweep2d_parent_code(group: SweepGroup, db_path: str) -> str:
    """Generate code for loading a Sweep2D parent (multiple 2D sweeps).

    In MeasureIt, a Sweep2D parent group consists of multiple runs, where each
    run contains ONE y-line (one value of the outer sweep parameter). This
    function generates code to combine all runs into a complete 2D dataset.
    """
    # Extract column info from metadata
    first_sweep = group.sweeps[0]
    inner = first_sweep.inner_sweep or {}
    outer = first_sweep.outer_sweep or {}
    follow_params = first_sweep.follow_params or {}

    inner_col = f"{inner.get('instr_name', 'instr')}_{inner.get('param', 'x')}"
    outer_col = f"{outer.get('instr_name', 'instr')}_{outer.get('param', 'y')}"
    follow_cols = [p.replace(".", "_") for p in follow_params.keys()]
    first_follow = follow_cols[0] if follow_cols else "measured"

    inner_comment = f"# Inner (x, fast): {inner_col}"
    outer_comment = f"# Outer (y, slow): {outer_col}"
    follow_comment = (
        f"# Measured: {follow_cols}" if follow_cols else "# Measured: (see df.columns)"
    )

    run_ids_str = ", ".join(str(r) for r in group.run_ids)

    return f"""# Load Sweep2D Parent - {len(group.run_ids)} runs in experiment "{group.exp_name}"
# Sample: {group.sample_name}
# Each run contains ONE y-line; combine them for the full 2D dataset.
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at
import pandas as pd

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

# All run IDs in this Sweep2D parent (each run = one y-line)
run_ids = [{run_ids_str}]

# Combine all runs into one DataFrame
dfs = []
for run_id in run_ids:
    ds = load_by_id(run_id)
    df = ds.to_pandas_dataframe().reset_index()
    dfs.append(df)

df = pd.concat(dfs, ignore_index=True)

# Columns from metadata:
{inner_comment}
{outer_comment}
{follow_comment}
print("Columns:", df.columns.tolist())
print("Shape:", df.shape)

# Optional: Create 2D scatter plot (uncomment to use)
# import matplotlib.pyplot as plt
# plt.scatter(df["{inner_col}"], df["{outer_col}"], c=df["{first_follow}"], s=10, cmap='viridis')
# plt.colorbar(label="{first_follow}")
# plt.xlabel("{inner_col}")
# plt.ylabel("{outer_col}")
"""


def _generate_simulsweep_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a SimulSweep dataset."""
    # Extract column info from metadata
    set_params = sweep.set_params or {}
    follow_params = sweep.follow_params or {}

    set_cols = [p.replace(".", "_") for p in set_params.keys()]
    follow_cols = [p.replace(".", "_") for p in follow_params.keys()]
    first_set = set_cols[0] if set_cols else "x"
    first_follow = follow_cols[0] if follow_cols else "measured"

    set_comment = (
        f"# Swept (simultaneous): {set_cols}"
        if set_cols
        else "# Swept: (see df.columns)"
    )
    follow_comment = (
        f"# Measured: {follow_cols}" if follow_cols else "# Measured: (see df.columns)"
    )

    return f"""# Load SimulSweep dataset (simultaneous parameter sweep)
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
df = ds.to_pandas_dataframe().reset_index()

# Columns from metadata:
{set_comment}
{follow_comment}
print("Columns:", df.columns.tolist())
print(df.head())

# Optional: Quick plot (uncomment to use)
# import matplotlib.pyplot as plt
# df.plot(x="{first_set}", y="{first_follow}")
"""


def _generate_sweep_queue_code(group: SweepGroup, db_path: str) -> str:
    """Generate code for loading a SweepQueue batch."""
    run_ids_str = ", ".join(str(r) for r in group.run_ids)

    # Determine the sweep type in the queue
    sweep_types = set(s.sweep_type.value for s in group.sweeps)
    sweep_type_desc = ", ".join(sweep_types)

    # Extract column info from first sweep's metadata
    first_sweep = group.sweeps[0] if group.sweeps else None
    if first_sweep:
        set_params = first_sweep.set_params or {}
        follow_params = first_sweep.follow_params or {}
        set_cols = [p.replace(".", "_") for p in set_params.keys()]
        follow_cols = [p.replace(".", "_") for p in follow_params.keys()]
        set_comment = (
            f"# Swept: {set_cols}" if set_cols else "# Swept: (see df.columns)"
        )
        follow_comment = (
            f"# Measured: {follow_cols}"
            if follow_cols
            else "# Measured: (see df.columns)"
        )
    else:
        set_comment = "# Swept: (see df.columns)"
        follow_comment = "# Measured: (see df.columns)"

    return f"""# Load SweepQueue batch - {len(group.run_ids)} runs ({sweep_type_desc})
# Experiment: "{group.exp_name}", Sample: {group.sample_name}
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

# All run IDs in this SweepQueue batch
run_ids = [{run_ids_str}]

# Expected columns (from first sweep metadata):
{set_comment}
{follow_comment}

# Load all datasets as DataFrames
dfs = {{}}
for run_id in run_ids:
    ds = load_by_id(run_id)
    dfs[run_id] = ds.to_pandas_dataframe().reset_index()
    print(f"Run {{run_id}}: {{len(dfs[run_id])}} points, columns: {{dfs[run_id].columns.tolist()}}")

# Access individual run: df = dfs[run_ids[0]]
"""


def _generate_qcodes_code(sweep: SweepInfo, db_path: str) -> str:
    """Generate code for loading a raw QCodes dataset (no MeasureIt metadata)."""
    return f"""# Load QCodes dataset
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db_path = "{db_path}"
initialise_or_create_database_at(db_path)

ds = load_by_id({sweep.run_id})
df = ds.to_pandas_dataframe().reset_index()

# DataFrame columns: setpoints (index) + measured parameters
print("Columns:", df.columns.tolist())
print(df.head())
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
