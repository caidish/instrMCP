# InstrMCP Comprehensive Human Test Plan

**Version**: Consolidated Full Functionality Test
**Date**: 2026-01-18
**Tester**: ________________
**Branch**: AI_safety

---

## Overview

This consolidated test plan covers all aspects of InstrMCP:
- Environment setup and server lifecycle
- Safe mode tools (read-only)
- Unsafe mode tools (with consent)
- Dangerous mode (consent bypass)
- Optional features (MeasureIt, Database, Dynamic Tools)
- Cell targeting features (cell_id_notebook, index:N navigation)
- Security scanner testing
- Frontend widget testing

---

## Prerequisites

Before starting tests, ensure:
- [ ] JupyterLab is installed and working
- [ ] instrmcp is installed (`pip install -e .` or `pip install -e .[dev]`)
- [ ] MCP Inspector available (https://inspector.tools.anthropic.com or local)
- [ ] A QCodes station with at least one instrument (or mock - see below)
- [ ] NumPy and Pandas installed

Optional prerequisites:
- [ ] MeasureIt package installed (for MeasureIt tests)
- [ ] QCodes database with sample data (for database tests)

### Recommended Environment

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev
jupyter lab
```

### Mock QCodes Station Setup

If no real instruments are available, run this in your notebook:

```python
from qcodes import Station, Parameter
from qcodes.instrument import Instrument

class MockInstrument(Instrument):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.add_parameter('voltage', unit='V', get_cmd=lambda: 1.23, set_cmd=lambda x: None)
        self.add_parameter('current', unit='A', get_cmd=lambda: 0.001, set_cmd=lambda x: None)
        self.add_parameter('frequency', unit='Hz', get_cmd=lambda: 1000, set_cmd=lambda x: None)

# Create station with mock instrument
mock_instr = MockInstrument('mock_dmm')
station = Station()
station.add_component(mock_instr)
```

---

## Part 1: Environment Setup and Server Lifecycle

### 1.1 Extension Loading

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Open JupyterLab | JupyterLab opens successfully | [ ] |
| 2 | Create new Python notebook | New notebook opens | [ ] |
| 3 | Check toolbar (without `%load_ext`) | MCP toolbar widget appears automatically | [ ] |
| 4 | Run: `%load_ext instrmcp.extensions` | No error; widget remains visible | [ ] |
| 5 | Check toolbar again | Widget still visible and functional | [ ] |

### 1.2 Server Start (Safe Mode Default)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_status` | Shows server not running, mode safe, lists commands | [ ] |
| 2 | Run: `%mcp_start` | Shows server started on http://localhost:PORT | [ ] |
| 3 | Run: `%mcp_status` | Shows server running, host, port, mode safe | [ ] |
| 4 | Note the port number | Port: _______ | [ ] |

### 1.3 MCP Inspector Connection

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Open MCP Inspector in browser | Inspector UI loads | [ ] |
| 2 | Set transport: Streamable HTTP | Transport selected | [ ] |
| 3 | Enter URL: `http://localhost:<PORT>/mcp` | URL entered | [ ] |
| 4 | Click Connect | Connection successful, tools list appears | [ ] |
| 5 | Verify safe tool list | See Part 2 for expected tools | [ ] |
| 6 | Verify unsafe tools absent | Unsafe tools not shown in safe mode | [ ] |

### 1.4 Server Stop and Restart

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_stop` | Server stops | [ ] |
| 2 | Run: `%mcp_status` | Shows server not running | [ ] |
| 3 | In Inspector, call any tool | Connection error or timeout | [ ] |
| 4 | Run: `%mcp_start` | Server starts again | [ ] |
| 5 | In Inspector, reconnect | Connection successful | [ ] |
| 6 | Run: `%mcp_restart` | Server restarts | [ ] |
| 7 | Verify Inspector tools still work | Tools accessible after reconnect | [ ] |

---

## Part 2: Safe Mode Tools Testing (via MCP Inspector)

### Current Safe Mode Tools

Expected tools in safe mode:
- `mcp_list_resources`, `mcp_get_resource`
- `notebook_server_status`, `notebook_list_variables`, `notebook_read_variable`
- `notebook_read_active_cell`, `notebook_read_active_cell_output`, `notebook_read_content`, `notebook_move_cursor`
- `qcodes_instrument_info`, `qcodes_get_parameter_info`, `qcodes_get_parameter_values`

### 2.1 notebook_server_status

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_server_status` with no parameters | Returns status, mode, enabled_options, tools list | [ ] |
| 2 | Verify mode | mode = "safe" | [ ] |
| 3 | Verify enabled_options | Empty or expected options | [ ] |

### 2.2 mcp_list_resources

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `mcp_list_resources` | Returns list of resources with URIs and descriptions | [ ] |
| 2 | Verify core resources present | Should see available resources | [ ] |

### 2.3 mcp_get_resource

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with valid resource URI | Returns resource content | [ ] |
| 2 | Call with invalid URI | Error response with available_uris | [ ] |

### 2.4 notebook_list_variables

**Setup**: Run in notebook:
```python
import numpy as np
import pandas as pd

x = 42
my_list = [1, 2, 3]
my_dict = {"a": 1, "b": 2}
class MyClass: pass
obj = MyClass()

arr = np.array([[1, 2, 3], [4, 5, 6]])
df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
large_arr = np.zeros((1000, 1000))
```

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_list_variables` with no params | Returns variables including x, my_list, my_dict, obj, arr, df, large_arr | [ ] |
| 2 | Call with `type_filter="int"` | Returns only int variables | [ ] |
| 3 | Call with `type_filter="list"` | Returns list variables | [ ] |
| 4 | Call with `type_filter="NonExistentType"` | Returns empty list | [ ] |
| 5 | Call with `type_filter="ndarray"` | Returns NumPy arrays | [ ] |
| 6 | Call with `type_filter="DataFrame"` | Returns DataFrames | [ ] |

### 2.5 notebook_read_variable

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `name="x"`, `detailed=false` | Concise info | [ ] |
| 2 | Call with `name="x"`, `detailed=true` | Detailed info with metadata | [ ] |
| 3 | Call with `name="arr"` | Returns truncated repr and metadata | [ ] |
| 4 | Call with `name="df"` | Returns DataFrame metadata | [ ] |
| 5 | Call with `name="large_arr"` | Returns summary without memory explosion | [ ] |
| 6 | Call with `name="nonexistent_var"` | Error: variable not found | [ ] |

### 2.6 notebook_read_active_cell

**Setup**: Click on a code cell and type `print("hello world")`

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `detailed=false` | Returns cell_type, cell_id_notebook, source | [ ] |
| 2 | Call with `detailed=true` | Includes cursor, selection, line info, freshness | [ ] |
| 3 | Call with `fresh_ms=100` | Returns is_stale true if older than 100ms | [ ] |
| 4 | Call with `line_start=1, line_end=1` | Returns only line 1 | [ ] |
| 5 | Select a markdown cell with content | cell_type = markdown, content returned | [ ] |

### 2.7 notebook_read_active_cell_output

**Setup**: Execute a cell with output first

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run cell: `print("test output")` | Output visible | [ ] |
| 2 | Call with `detailed=false` | Concise output summary | [ ] |
| 3 | Call with `detailed=true` | Full output with outputs array | [ ] |
| 4 | Run cell with error: `1/0` | Error visible | [ ] |
| 5 | Call tool | has_error true, error info present | [ ] |
| 6 | Run cell with no output: `x = 1` | No output | [ ] |
| 7 | Call tool | status completed, has_error false | [ ] |
| 8 | Select a markdown cell | status not_code_cell | [ ] |

### 2.8 notebook_read_content (with Cell Targeting)

**Setup**: Create test notebook with 8 cells:
- Position 0: markdown `# Test Notebook Header`
- Position 1: code `x = 1` (execute -> [1])
- Position 2: markdown `## Section 1`
- Position 3: code `y = 2` (execute -> [2])
- Position 4: code `# unexecuted code cell` (DO NOT execute)
- Position 5: markdown `## Section 2`
- Position 6: code `z = x + y` (execute -> [3])
- Position 7: code `print("hello")` (execute -> [4])

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `num_cells=3` | Returns last 3 cells | [ ] |
| 2 | Verify `total_cells` field | Should show 8 | [ ] |
| 3 | Verify each cell has `cell_id_notebook` | 0-indexed positions present | [ ] |
| 4 | Verify each cell has `cell_type` | "code", "markdown", or "raw" | [ ] |
| 5 | Verify each cell has `source` field | Cell content present | [ ] |
| 6 | Call with `num_cells=10`, `include_output=true` | Returns all cells with outputs | [ ] |
| 7 | Call with `num_cells=2`, `include_output=false` | Returns cells without output field | [ ] |
| 8 | Call with `detailed=true` | Returns full metadata per cell | [ ] |

#### Cell Targeting by Position (cell_id_notebooks)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_id_notebooks="[0]"` | Returns ONLY cell 0 (markdown header) | [ ] |
| 2 | Verify cell_type | Should be "markdown" | [ ] |
| 3 | Call with `cell_id_notebooks="[4]"` | Returns cell 4 (unexecuted code) | [ ] |
| 4 | Verify status | Should be "not_executed" | [ ] |
| 5 | Call with `cell_id_notebooks="[0, 2, 5]"` | Returns 3 cells (all markdown) | [ ] |
| 6 | Call with `cell_id_notebooks="[1, 2, 4, 6]"` | Returns mixed cell types | [ ] |
| 7 | Call with `cell_id_notebooks="[100]"` | Returns empty cells array (out of bounds) | [ ] |

### 2.9 notebook_move_cursor

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `target="above"` | Moves cursor to cell above | [ ] |
| 2 | Verify in notebook | Previous cell is now active | [ ] |
| 3 | Call with `target="below"` | Moves cursor to cell below | [ ] |
| 4 | Call with `target="bottom"` | Moves to last cell | [ ] |

#### index:N Navigation (Position-Based)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `target="index:0"` | Moves to position 0 (markdown header) | [ ] |
| 2 | Verify in JupyterLab | First cell (markdown) is selected | [ ] |
| 3 | Call with `target="index:4"` | Moves to unexecuted code cell | [ ] |
| 4 | Verify in JupyterLab | Unexecuted cell is selected | [ ] |
| 5 | Call with `target="index:7"` | Moves to last cell | [ ] |
| 6 | Call with `target="index:100"` | Error: invalid index | [ ] |

### 2.10 qcodes_instrument_info

**Prerequisite**: QCodes station with instrument loaded

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `name="*"` | Returns list of all instruments | [ ] |
| 2 | Call with `name="<instrument>"`, `detailed=false` | Concise summary | [ ] |
| 3 | Call with `name="<instrument>"`, `detailed=true` | Full info with parameters | [ ] |
| 4 | Call with `with_values=true` | Includes cached values | [ ] |
| 5 | Call with invalid name | Error returned | [ ] |

### 2.11 qcodes_get_parameter_info

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with valid `instrument` and `parameter`, `detailed=false` | Core metadata only | [ ] |
| 2 | Call with `detailed=true` | Includes extended metadata and cache | [ ] |
| 3 | Call with invalid parameter | Error returned | [ ] |

### 2.12 qcodes_get_parameter_values

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with single query JSON string | Returns value | [ ] |
| 2 | Call with batch JSON string | Returns list of values | [ ] |
| 3 | Call with `detailed=true` | Includes timestamps and source | [ ] |
| 4 | Query invalid parameter | Returns error for that query | [ ] |
| 5 | Send invalid JSON | JSON parse error | [ ] |

---

## Part 3: Unsafe Mode Tools Testing

### 3.1 Switch to Unsafe Mode

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_unsafe` | Shows warning about unsafe mode | [ ] |
| 2 | Run: `%mcp_status` | Shows mode unsafe (pending restart) | [ ] |
| 3 | Run: `%mcp_restart` | Server restarts in unsafe mode | [ ] |
| 4 | Reconnect Inspector | Unsafe tools appear | [ ] |
| 5 | Verify unsafe tools | Should see: notebook_update_editing_cell, notebook_execute_active_cell, notebook_add_cell, notebook_delete_cell, notebook_apply_patch | [ ] |

### 3.2 notebook_update_editing_cell (Requires Consent)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create a cell with `old content` | Cell has content | [ ] |
| 2 | Call `notebook_update_editing_cell` with new content | Consent dialog appears | [ ] |
| 3 | Click Deny | Tool returns denied, cell unchanged | [ ] |
| 4 | Call again and Approve | Cell content updated | [ ] |
| 5 | Verify in notebook | Cell shows new content | [ ] |

### 3.3 notebook_execute_active_cell (Requires Consent)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cell: `print("executed by MCP")` | Cell ready | [ ] |
| 2 | Call `notebook_execute_active_cell` | Consent dialog appears | [ ] |
| 3 | Approve | Cell executes | [ ] |
| 4 | Verify tool returns | Returns status, has_output, outputs | [ ] |
| 5 | Run error cell: `raise ValueError("test")` | has_error true, error details | [ ] |
| 6 | Set `timeout=1.0`, run `import time; time.sleep(10)` | Returns timeout status | [ ] |

### 3.4 notebook_add_cell

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_type="code"`, `position="below"`, `content="# new cell"` | New cell created | [ ] |
| 2 | Verify in notebook | New code cell appears below with content | [ ] |
| 3 | Call with `cell_type="markdown"`, `position="above"`, `content="# Header"` | Markdown cell created | [ ] |
| 4 | Call with invalid `cell_type` | Error returned | [ ] |
| 5 | Call with invalid `position` | Error returned | [ ] |

### 3.5 notebook_delete_cell (Requires Consent)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create a cell with `DELETE ME` | Cell exists | [ ] |
| 2 | Click on the cell to select it | Cell is active | [ ] |
| 3 | Call `notebook_delete_cell` | Consent dialog appears | [ ] |
| 4 | Deny | Cell remains | [ ] |
| 5 | Approve | Selected cell deleted | [ ] |

#### Delete Cells by Position (cell_id_notebooks)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Add 3 test cells at end | 3 new cells exist | [ ] |
| 2 | Note their positions | Positions recorded | [ ] |
| 3 | Call with `cell_id_notebooks="[pos1, pos2, pos3]"` | Consent shows 3 cells | [ ] |
| 4 | Approve | All 3 cells deleted | [ ] |
| 5 | Verify deleted_count | Should be 3 | [ ] |
| 6 | Call with `cell_id_notebooks="[100]"` | Success but deleted_count=0 | [ ] |

### 3.6 notebook_apply_patch (Requires Consent)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cell: `x = 1\ny = 2\nz = 3` | Cell ready | [ ] |
| 2 | Call with `old_text="y = 2"`, `new_text="y = 200"` | Consent dialog appears | [ ] |
| 3 | Approve | Patch applied once | [ ] |
| 4 | Verify in notebook | Cell shows `y = 200` | [ ] |
| 5 | Call with non-matching old_text | Error: text not found | [ ] |

---

## Part 4: Dangerous Mode

### 4.1 Switch to Dangerous Mode

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_dangerous` | Shows dangerous mode warnings | [ ] |
| 2 | Run: `%mcp_restart` | Server restarts in dangerous mode | [ ] |
| 3 | Run: `%mcp_status` | mode = dangerous | [ ] |

### 4.2 Consent Bypass Verification

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cell with content | Cell exists | [ ] |
| 2 | Call `notebook_update_editing_cell` | NO consent dialog appears | [ ] |
| 3 | Operation completes immediately | Success response | [ ] |
| 4 | Verify in notebook | Cell updated without consent prompt | [ ] |

---

## Part 5: Security Scanner Testing (Unsafe Mode)

### 5.1 Setup

```python
%mcp_unsafe
%mcp_restart
```

### 5.2 Environment Modification (Should be BLOCKED)

| # | Test Code | Expected Result | Pass |
|---|-----------|-----------------|------|
| 1 | `os.environ["QCODES_USER_PATH"] = "/tmp/malicious"` | BLOCKED | [ ] |
| 2 | `os.environ.update({"PATH": "/evil"})` | BLOCKED | [ ] |
| 3 | `os.putenv("LD_PRELOAD", "/tmp/evil.so")` | BLOCKED | [ ] |

### 5.3 Dynamic Code Execution (Should be BLOCKED)

| # | Test Code | Expected Result | Pass |
|---|-----------|-----------------|------|
| 1 | `exec("print('hello')")` | BLOCKED | [ ] |
| 2 | `eval("1+1")` | BLOCKED | [ ] |
| 3 | `compile("x=1", "", "exec")` | BLOCKED | [ ] |

### 5.4 Subprocess/Shell Commands (Should be BLOCKED)

| # | Test Code | Expected Result | Pass |
|---|-----------|-----------------|------|
| 1 | `os.system("ls")` | BLOCKED | [ ] |
| 2 | `subprocess.run(["ls"], shell=True)` | BLOCKED | [ ] |
| 3 | `subprocess.Popen("cat /etc/passwd", shell=True)` | BLOCKED | [ ] |

### 5.5 Aliased Import Bypass Attempts (Should be BLOCKED)

| # | Test Code | Expected Result | Pass |
|---|-----------|-----------------|------|
| 1 | `from os import system as s; s("ls")` | BLOCKED | [ ] |
| 2 | `from os import environ as e; e["X"]="Y"` | BLOCKED | [ ] |
| 3 | `import os as o; o.system("ls")` | BLOCKED | [ ] |

### 5.6 Safe Code (Should PASS)

| # | Test Code | Expected Result | Pass |
|---|-----------|-----------------|------|
| 1 | `import numpy as np; np.array([1,2,3])` | PASS | [ ] |
| 2 | `print("Hello, World!")` | PASS | [ ] |
| 3 | `x = 1 + 2` | PASS | [ ] |
| 4 | `os.path.join("a", "b")` | PASS | [ ] |
| 5 | `os.getcwd()` | PASS | [ ] |

---

## Part 6: Optional Features

### 6.1 MeasureIt Tools (Optional)

**Enable**:
```python
%mcp_option measureit
%mcp_restart
```

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Verify tools appear | measureit_get_status, measureit_wait_for_sweep, measureit_kill_sweep | [ ] |
| 2 | Call `measureit_get_status` (no sweeps) | active=false, sweeps empty | [ ] |
| 3 | Start a sweep in notebook | Sweep running | [ ] |
| 4 | Call `measureit_get_status` | active true, sweep info present | [ ] |
| 5 | Call `measureit_wait_for_sweep` with `variable_name`, `timeout` | Waits until sweep completes | [ ] |
| 6 | Call `measureit_kill_sweep` | Sweep stops and returns success | [ ] |

### 6.2 MeasureIt Resources (Optional)

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `mcp_list_resources` | MeasureIt templates listed | [ ] |
| 2 | Call `mcp_get_resource` for a template | Returns code template text | [ ] |

### 6.3 Database Tools (Optional)

**Enable**:
```python
%mcp_option database
%mcp_restart
```

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Verify tools appear | database_list_all_available_db, database_list_experiments, database_get_dataset_info, database_get_database_stats | [ ] |
| 2 | Call `database_list_all_available_db` | Returns databases list | [ ] |
| 3 | Call `database_list_experiments` | Returns experiments list | [ ] |
| 4 | Call `database_get_dataset_info` with valid id | Returns dataset info | [ ] |
| 5 | Call with `code_suggestion=true` in safe mode | Returns code_suggestion only | [ ] |
| 6 | Switch to unsafe mode, call with `code_suggestion=true` | Auto-inserts and executes code cell | [ ] |
| 7 | Call `database_get_database_stats` | Returns db stats | [ ] |
| 8 | Call with invalid id or path | Error returned | [ ] |

### 6.4 Dynamic Tools (Dangerous Mode + Option)

**Enable**:
```python
%mcp_dangerous
%mcp_option dynamictool
%mcp_restart
```

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Verify tools appear | dynamic_register_tool, dynamic_update_tool, dynamic_revoke_tool, dynamic_list_tools, dynamic_inspect_tool, dynamic_registry_stats | [ ] |
| 2 | Call `dynamic_list_tools` | Returns empty or default list | [ ] |
| 3 | Register a simple echo tool | Tool created successfully | [ ] |
| 4 | Call newly registered tool | Returns expected output | [ ] |
| 5 | Inspect tool | Shows schema and code | [ ] |
| 6 | Update tool and call again | Updated behavior | [ ] |
| 7 | Revoke tool | Tool removed | [ ] |
| 8 | Call `dynamic_registry_stats` | Counts reflect changes | [ ] |

---

## Part 7: Frontend Widget Testing (JupyterLab Toolbar)

### 7.1 Toolbar Widget Visibility

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Open a new notebook | Notebook opens | [ ] |
| 2 | Do not run `%load_ext` | Toolbar widget appears automatically | [ ] |
| 3 | Run `%load_ext instrmcp.extensions` (optional) | No error; widget remains | [ ] |
| 4 | Widget shows status and controls | Controls visible | [ ] |

### 7.2 Status Indicator

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Before starting server | Status shows Stopped | [ ] |
| 2 | Start server | Status shows Running | [ ] |
| 3 | Stop server | Status shows Stopped | [ ] |

### 7.3 Mode Selector

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Stop server | Server stopped | [ ] |
| 2 | Open mode dropdown | Shows Safe, Unsafe, Dangerous | [ ] |
| 3 | Select Safe | Mode set to safe | [ ] |
| 4 | Select Unsafe | Mode set to unsafe | [ ] |
| 5 | Select Dangerous | Mode set to dangerous | [ ] |
| 6 | Start server | Starts in selected mode | [ ] |
| 7 | Try changing mode while running | Disabled or warning shown | [ ] |

### 7.4 Server Control Buttons

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Server stopped | Start enabled, Stop/Restart disabled | [ ] |
| 2 | Click Start | Server starts, buttons update | [ ] |
| 3 | Server running | Stop/Restart enabled | [ ] |
| 4 | Click Stop | Server stops, buttons update | [ ] |
| 5 | Click Restart | Server restarts | [ ] |

### 7.5 Options Panel

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Stop server | Server stopped | [ ] |
| 2 | Open options panel | Panel shows available options | [ ] |
| 3 | Toggle measureit on | Toggle reflects on | [ ] |
| 4 | Toggle database on | Toggle reflects on | [ ] |
| 5 | Dynamictool shows mode requirement | Requires dangerous mode | [ ] |
| 6 | Enable dynamictool in dangerous mode | Toggle reflects on | [ ] |
| 7 | Start server | Options active | [ ] |
| 8 | Toggle options while running | Disabled or warning shown | [ ] |

### 7.6 Port and Host Display

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Start server | Server running | [ ] |
| 2 | Toolbar displays host:port | Matches `%mcp_status` | [ ] |

### 7.7 Kernel Restart Handling

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Start MCP server | Server running | [ ] |
| 2 | Restart kernel | Kernel restarts | [ ] |
| 3 | Toolbar updates | Shows stopped or prompts reload | [ ] |
| 4 | Reload extension | Widget functional again | [ ] |

---

## Part 8: Consent Dialog Testing (Unsafe Mode)

### 8.1 Consent Dialog Appearance

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Switch to unsafe mode, restart server | Unsafe mode active | [ ] |
| 2 | Call `notebook_update_editing_cell` | Consent dialog appears | [ ] |
| 3 | Observe dialog content | Shows: operation type, old content, new content | [ ] |
| 4 | Verify buttons | "Approve" and "Deny" buttons present | [ ] |
| 5 | Verify dialog is modal | Cannot interact with notebook while dialog open | [ ] |

### 8.2 Consent Deny Flow

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Trigger consent dialog | Dialog appears | [ ] |
| 2 | Click "Deny" | Dialog closes | [ ] |
| 3 | Check tool response | Returns consent_denied or similar error | [ ] |
| 4 | Verify no change occurred | Notebook state unchanged | [ ] |

### 8.3 Consent Approve Flow

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Trigger consent dialog | Dialog appears | [ ] |
| 2 | Click "Approve" | Dialog closes | [ ] |
| 3 | Check tool response | Returns success | [ ] |
| 4 | Verify change occurred | Operation completed | [ ] |

---

## Part 9: Cleanup and Final Verification

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_safe` | Switch back to safe mode | [ ] |
| 2 | Run: `%mcp_restart` | Server restarts in safe mode | [ ] |
| 3 | Verify unsafe tools hidden | Only safe tools visible | [ ] |
| 4 | Run: `%mcp_stop` | Server stops | [ ] |
| 5 | Close Inspector | Connection closed | [ ] |

---

## Summary Checklist

### Core Features
- [ ] Extension loads and toolbar appears
- [ ] Server starts/stops/restarts correctly
- [ ] MCP Inspector connects successfully
- [ ] Mode switching works (safe/unsafe/dangerous)

### Safe Mode Tools
- [ ] All read-only notebook tools work
- [ ] All QCodes tools work
- [ ] Resources listing and retrieval work
- [ ] Cell targeting (cell_id_notebooks) works
- [ ] index:N navigation works

### Unsafe Mode Tools
- [ ] Consent dialogs appear for unsafe operations
- [ ] Deny prevents operation
- [ ] Approve allows operation
- [ ] Cell execution returns output
- [ ] Cell add/delete/patch work correctly

### Dangerous Mode
- [ ] Consent bypass works
- [ ] Operations complete immediately

### Security
- [ ] Dangerous patterns are blocked
- [ ] Safe code is allowed
- [ ] Aliased imports are detected

### Optional Features
- [ ] MeasureIt tools work when enabled
- [ ] Database tools work when enabled
- [ ] Dynamic tools work in dangerous mode

### Frontend
- [ ] Toolbar widget displays correctly
- [ ] Mode selector works
- [ ] Options toggles work
- [ ] Kernel restart handled gracefully

---

## Known Issues (Historical - Verify if Fixed)

The following issues were noted in previous test cycles. Verify current behavior:

1. **notebook_delete_cell**: Previously deleted 2-5 cells instead of just the selected one
2. **notebook_apply_patch**: Previously applied patch 2-3 times
3. **notebook_add_cell**: Content sometimes not set properly for markdown cells
4. **notebook_move_cursor with invalid target**: May return success instead of error

---

## Notes

_Space for tester notes:_

---

**Test Completed**: [ ] Yes / [ ] No
**Date Completed**: ________________
**Issues Found**: ________________
