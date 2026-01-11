# Human Testing Instructions for Bug Fixes & Features

## Overview

This document provides step-by-step instructions to verify bug fixes and new features:

1. **Bug 1: SQLite Threading Error** - Database tools now use direct SQLite connections instead of QCoDeS cached connections
2. **Bug 2: Persistent Cell Error State** - Cell output cache now has timestamp-based TTL validation
3. **Feature 3: Intelligent Sweep Grouping** - Database tools detect and group related sweeps (Sweep2D parent, SweepQueue) with sweep-type-aware code suggestions

---

## Prerequisites

1. JupyterLab running with the instrMCP extension loaded
2. MCP Inspector connected to the instrMCP server
3. A QCoDeS database with at least one experiment/dataset (for Bug 1 testing)

---

## Setup

### Step 1: Start JupyterLab

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev
jupyter lab
```

### Step 2: Open TestNotebook.ipynb and Start MCP Server

In JupyterLab, run these cells:

```python
# Cell 1: Load extension
%load_ext instrmcp.extensions

# Cell 2: Start server in unsafe mode (needed for some tests)
%mcp_unsafe
%mcp_start
```

### Step 3: Connect MCP Inspector

Open MCP Inspector and connect to the server (default: `http://127.0.0.1:8123`)

---

## Bug 1: SQLite Threading Error Fix

### What We're Testing

The database tools should work even when QCoDeS has active connections in the kernel thread.

### Test Steps

#### Test 1.1: Basic Database Query (Without Active Sweep)

1. In MCP Inspector, call `database_list_experiments`
2. **Expected**: Returns list of experiments without error
3. **Previously**: Would work (no thread conflict yet)

#### Test 1.2: Database Query During/After Sweep (The Critical Test)

1. In JupyterLab, run a cell that creates a QCoDeS database connection:

```python
import qcodes as qc
from qcodes.dataset import experiments, load_by_id

# This creates a SQLite connection in the kernel thread
exps = experiments()
print(f"Found {len(exps)} experiments")
```

2. **While the kernel is still active** (don't restart), in MCP Inspector call:
   - `database_list_experiments`
   - `database_get_dataset_info` with `id: 1` (or any valid run_id)
   - `database_get_database_stats`

3. **Expected Results**:
   - All calls succeed with valid JSON responses
   - No "SQLite objects created in a thread can only be used in that same thread" error

4. **Previously**: Would fail with SQLite threading error

#### Test 1.3: Verify Parameter Info Includes All Fields

1. In MCP Inspector, call `database_get_dataset_info` with `id: 1`
2. Check the `parameters` section in the response
3. **Expected**: Each parameter should have:
   - `name`
   - `type`
   - `label`
   - `unit`
   - `depends_on`
   - `inferred_from`
   - `shape` (will be `null` - this is expected, as shape is a runtime attribute)

---

## Bug 2: Persistent Cell Error State Fix

### What We're Testing

Cell error states should not persist beyond the cache TTL (60 seconds).

### Test Steps

#### Test 2.1: Error State Clears After TTL

1. In JupyterLab, create a new cell with an intentional error:

```python
# This will fail
1 / 0
```

2. Run the cell (it will raise ZeroDivisionError)

3. In MCP Inspector, call `notebook_get_notebook_cells` with `num_cells: 5`

4. **Expected**: The cell should show `has_error: true`

5. **Wait 60+ seconds** (the cache TTL)

6. In MCP Inspector, call `notebook_get_notebook_cells` again

7. **Expected**:
   - The error should either be refreshed from frontend (still showing error if cell wasn't re-run)
   - OR the stale cached error should be invalidated

#### Test 2.2: Error State Updates After Fix

1. In JupyterLab, fix the erroring cell:

```python
# Fixed version
1 + 1
```

2. Run the fixed cell

3. **Immediately** in MCP Inspector, call `notebook_get_notebook_cells`

4. **Expected**: The cell should show `has_error: false` and have the correct output

5. **Previously**: Would sometimes still show the old error state

#### Test 2.3: Verify Cache Metadata

1. In JupyterLab, run any cell with output:

```python
print("Hello, World!")
```

2. In MCP Inspector, call `notebook_get_editing_cell_output`

3. **Expected**: Response includes output data

4. Check the server logs (in JupyterLab terminal) for messages like:
   - `Cached outputs for N cells (with timestamps)` - confirms timestamping is working

#### Test 2.4: Multiple Rapid Executions

1. In JupyterLab, create a cell:

```python
import time
print(f"Executed at: {time.time()}")
```

2. Run the cell 3 times rapidly (within 10 seconds)

3. After each run, call `notebook_get_notebook_cells` in MCP Inspector

4. **Expected**: Each call should return the latest output (latest timestamp)

5. **Previously**: Might return stale cached output from earlier execution

---

## Verification Checklist

### Bug 1: SQLite Threading

| Test | Expected | Pass/Fail |
|------|----------|-----------|
| 1.1 Basic query | Returns experiments | |
| 1.2 Query after kernel DB access | No threading error | |
| 1.3 Parameter fields complete | All 7 fields present | |

### Bug 2: Cache TTL

| Test | Expected | Pass/Fail |
|------|----------|-----------|
| 2.1 Error clears after 60s | Stale cache invalidated | |
| 2.2 Fixed cell shows correct state | `has_error: false` | |
| 2.3 Cache has timestamps | Log shows timestamping | |
| 2.4 Rapid executions | Latest output each time | |

---

## Troubleshooting

### If Bug 1 tests fail with threading error

The fix may not be properly installed. Verify:
```bash
pip install -e . --force-reinstall --no-deps
```

Then restart JupyterLab and the MCP server.

### If Bug 2 tests show stale data

1. Check server logs for cache-related messages
2. Verify the 60-second TTL by checking timestamps in logs
3. Try calling `notebook_get_notebook_cells` with `detailed: true` for more info

### Log Locations

- Server logs: JupyterLab terminal where you started the server
- Look for messages containing:
  - `Cache entry for cell X expired` (TTL working)
  - `Cached outputs for N cells (with timestamps)` (timestamping working)
  - Direct SQLite query messages (threading fix working)

---

## Additional Notes

- The cache TTL is set to 60 seconds (`CELL_OUTPUT_CACHE_TTL_SECONDS`)
- Direct SQLite connections are created per-request and immediately closed
- The `invalidate_cell_output_cache` function is available for manual cache clearing if needed

---

## Feature 3: Intelligent Sweep Grouping & Code Suggestion

### What We're Testing

The database tools intelligently detect and group related measurements:
- **Sweep2D Parent**: Multiple Sweep2D runs in the same experiment (each run = one y-line of the 2D grid)
- **SweepQueue Batch**: Consecutive runs launched by SweepQueue
- **Code Suggestion**: Sweep-type-aware Python code generation for data loading

### Prerequisites

A QCoDeS database with MeasureIt measurements containing:
- Sweep0D (time-based measurement)
- Sweep1D (single parameter sweep)
- Sweep2D (creates multiple runs in one experiment)
- SweepQueue (creates consecutive runs)

### Test Steps

#### Test 3.1: Sweep Group Detection in List Experiments

1. In MCP Inspector, call `database_list_experiments` with `detailed: true`

2. **Expected Response** should include a `sweep_groups` field:
```json
{
  "database_path": "...",
  "experiments": [...],
  "sweep_groups": [
    {
      "type": "sweep2d_parent",
      "sweep_type": "Sweep2D",
      "run_ids": [5, 6, 7, 8],
      "description": "Sweep2D parent with 4 runs"
    },
    {
      "type": "sweep_queue",
      "sweep_type": "Sweep1D",
      "run_ids": [10, 11, 12],
      "description": "SweepQueue batch: 3 runs (Sweep1D)"
    }
  ]
}
```

3. **Verify**:
   - Groups with `len(run_ids) > 1` appear in `sweep_groups`
   - Single runs are NOT shown in `sweep_groups`
   - Group types are `sweep2d_parent`, `sweep_queue`, or `single`

#### Test 3.2: Sweep2D Parent Code Suggestion

1. Find a Sweep2D run_id from a multi-run experiment (check `sweep_groups` from Test 3.1)

2. In MCP Inspector, call `database_get_dataset_info` with:
   - `id`: (one of the Sweep2D run_ids)
   - `code_suggestion: true`

3. **Expected**: The `code_suggestion` field should contain code that:
   - Lists ALL run_ids in the Sweep2D parent group
   - Loops through runs to combine data
   - Creates a 2D plot using scatter or pcolormesh
   - Example snippet:
   ```python
   # All run IDs in this Sweep2D parent (each run = one y-line)
   run_ids = [5, 6, 7, 8]

   for run_id in run_ids:
       ds = load_by_id(run_id)
       ...
   ```

4. **Verify**: Copy the generated code to JupyterLab and run it - should produce a 2D plot

#### Test 3.3: SweepQueue Batch Code Suggestion

1. Find a SweepQueue run_id (from `sweep_groups`)

2. In MCP Inspector, call `database_get_dataset_info` with:
   - `id`: (one of the SweepQueue run_ids)
   - `code_suggestion: true`

3. **Expected**: Code should:
   - List all run_ids in the SweepQueue batch
   - Load all datasets into a dict
   - Create subplots for each run
   - Example snippet:
   ```python
   # All run IDs in this SweepQueue batch
   run_ids = [10, 11, 12]
   datasets = {run_id: load_by_id(run_id) for run_id in run_ids}
   ```

#### Test 3.4: Sweep1D Code Suggestion

1. Find a standalone Sweep1D run_id (not in a queue)

2. In MCP Inspector, call `database_get_dataset_info` with:
   - `id`: (Sweep1D run_id)
   - `code_suggestion: true`

3. **Expected**: Code should:
   - Load single dataset
   - Extract setpoint and measured parameters by name
   - Include correct axis labels from metadata
   - Example snippet:
   ```python
   ds = load_by_id(15)
   data = ds.get_parameter_data()

   # Setpoint array
   instr_voltage = data["measured_param"]["instr_voltage"]
   ```

#### Test 3.5: Sweep0D Code Suggestion

1. Find a Sweep0D run_id (time-based measurement)

2. In MCP Inspector, call `database_get_dataset_info` with:
   - `id`: (Sweep0D run_id)
   - `code_suggestion: true`

3. **Expected**: Code should:
   - Extract time array
   - Extract follow parameters
   - Set x-axis label to "Time (s)"

#### Test 3.6: Raw QCodes Dataset (No MeasureIt Metadata)

1. Find a dataset without MeasureIt metadata (raw QCodes measurement)

2. In MCP Inspector, call `database_get_dataset_info` with:
   - `id`: (QCodes run_id)
   - `code_suggestion: true`

3. **Expected**: Code should:
   - Use generic parameter extraction
   - Print available parameters for exploration
   - Example snippet:
   ```python
   print("Available parameters:", list(data.keys()))
   for param, values in data.items():
       print(f"  {param}: {list(values.keys())}")
   ```

#### Test 3.7: Concise Mode (No Sweep Groups)

1. In MCP Inspector, call `database_list_experiments` with `detailed: false` (default)

2. **Expected**: Response should NOT include `sweep_groups` (concise mode)

3. **Verify**: Only `database_path`, `experiments` (names only), and `count` are returned

---

## Verification Checklist

### Bug 1: SQLite Threading

| Test | Expected | Pass/Fail |
|------|----------|-----------|
| 1.1 Basic query | Returns experiments | |
| 1.2 Query after kernel DB access | No threading error | |
| 1.3 Parameter fields complete | All 7 fields present | |

### Bug 2: Cache TTL

| Test | Expected | Pass/Fail |
|------|----------|-----------|
| 2.1 Error clears after 60s | Stale cache invalidated | |
| 2.2 Fixed cell shows correct state | `has_error: false` | |
| 2.3 Cache has timestamps | Log shows timestamping | |
| 2.4 Rapid executions | Latest output each time | |

### Feature 3: Sweep Grouping

| Test | Expected | Pass/Fail |
|------|----------|-----------|
| 3.1 Sweep groups in list | `sweep_groups` field present | |
| 3.2 Sweep2D parent code | Multi-run combining code | |
| 3.3 SweepQueue batch code | Batch loading code | |
| 3.4 Sweep1D code | Single sweep code | |
| 3.5 Sweep0D code | Time-based code | |
| 3.6 Raw QCodes code | Generic exploration code | |
| 3.7 Concise mode | No sweep_groups | |
