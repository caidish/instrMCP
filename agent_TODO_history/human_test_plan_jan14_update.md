# InstrMCP Comprehensive Human Test Plan (Jan 14 Update)

**Version**: Full functionality test (safe, unsafe, dangerous, optional features)
**Date**: 2025-01-14
**Tester**: ________________

---

## Prerequisites

Before starting tests, ensure:
- [x] JupyterLab is installed and working
- [x] instrmcp is installed (`pip install -e .` or `pip install -e .[dev]`)
- [x] MCP Inspector is available (https://inspector.tools.anthropic.com or local)
- [x] A QCoDeS station with at least one instrument is available (or mock - see below)
- [x] MeasureIt package is installed (for optional tests)
- [x] QCoDeS database exists with sample data (for optional tests)
- [x] NumPy and Pandas installed (for complex data type tests)

Recommended environment:
- [x] Use conda env `instrMCPdev`
  - `source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev`

### Mock QCoDeS Station Setup
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
| 1 | Open JupyterLab | JupyterLab opens successfully | [x] |
| 2 | Create new Python notebook | New notebook opens | [x] |
| 3 | Check toolbar (no `%load_ext`) | MCP toolbar widget appears automatically | [x] |
| 4 | Run: `%load_ext instrmcp.extensions` (optional) | No error; widget remains visible | [x] |
| 5 | Check toolbar again | Widget still visible and functional | [x] |

### 1.2 Server Start (Safe Mode Default)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_status` | Shows server not running, mode safe, lists commands | [x] |
| 2 | Run: `%mcp_start` | Shows server started on http://localhost:PORT | [x] |
| 3 | Run: `%mcp_status` | Shows server running, host, port, mode safe | [x] |
| 4 | Note the port number | Port recorded | [x] |

### 1.3 MCP Inspector Connection
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Open MCP Inspector in browser | Inspector UI loads | [x] |
| 2 | Set transport: Streamable HTTP | Transport selected | [x] |
| 3 | Enter URL: `http://localhost:<PORT>/mcp` | URL entered | [x] |
| 4 | Click Connect | Connection successful, tools list appears | [x] |
| 5 | Verify safe tool list | Core tools only (see Part 2) | [x] |
| 6 | Verify unsafe tools absent | Unsafe tools not shown in safe mode | [x] |

### 1.4 Server Stop and Restart
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_stop` (or `%mcp_close` if configured) | Server stops | [x] |
| 2 | Run: `%mcp_status` | Shows server not running | [x] |
| 3 | In Inspector, call any tool | Connection error or timeout | [x] |
| 4 | Run: `%mcp_start` | Server starts again | [x] |
| 5 | In Inspector, reconnect | Connection successful | [x] |
| 6 | Run: `%mcp_restart` | Server restarts | [x] |
| 7 | Verify Inspector tools still work | Tools accessible after reconnect | [x] |

---

## Part 2: Safe Mode Tools Testing (via MCP Inspector)

### 2.1 notebook_server_status
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_server_status` with no parameters | Returns status, mode, enabled_options, tools list (first 20), dynamic_tools_count | [x] |
| 2 | Verify mode | mode = "safe" | [x] |
| 3 | Verify enabled_options | Empty or expected options | [x] |

### 2.2 mcp_list_resources
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `mcp_list_resources` | Returns list of resources with URIs and descriptions | [x] |
| 2 | Verify core resources present | resource://available_instruments, resource://station_state | [x] |

### 2.3 mcp_get_resource (Core)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `mcp_get_resource` with `uri="resource://available_instruments"` | JSON list of instruments | [x] |
| 2 | Call `mcp_get_resource` with `uri="resource://station_state"` | Station metadata summary with instruments_resource reference | [x] |
| 3 | Call with invalid URI | Error response with available_uris | [x] |

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
| 1 | Call `notebook_list_variables` with no params | Returns variables (name/type only) including x, my_list, my_dict, obj, arr, df, large_arr | [x] |
| 2 | Call with `type_filter="int"` | Returns only int variables | [ ] |
| 3 | Call with `type_filter="list"` | Returns list variables | [ ] |
| 4 | Call with `type_filter="NonExistentType"` | Returns empty list | [ ] |
| 5 | Call with `type_filter="ndarray"` | Returns NumPy arrays | [ ] |
| 6 | Call with `type_filter="DataFrame"` | Returns DataFrames | [ ] |
| 7 | Call with `type_filter="null"` (string) | Treated as None, returns full list | [ ] |

### 2.5 notebook_get_variable_info
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `name="x"`, `detailed=false` | Concise info | [ ] |
| 2 | Call with `name="x"`, `detailed=true` | Detailed info | [ ] |
| 3 | Call with `name="arr"` | Returns truncated repr and metadata | [ ] |
| 4 | Call with `name="df"` | Returns DataFrame metadata | [ ] |
| 5 | Call with `name="large_arr"` | Returns summary without large output | [ ] |
| 6 | Call with `name="nonexistent_var"` | Error: variable not found | [ ] |

### 2.6 notebook_get_editing_cell
**Setup**: Click on a code cell and type `print("hello world")`

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_get_editing_cell` with `detailed=false` | cell_type, cell_index, cell_content | [x] |
| 2 | Call with `detailed=true` | Includes cursor, selection, line info, freshness | [x] |
| 3 | Call with `fresh_ms=100` | Returns is_stale true if older than 100ms | [x] |
| 4 | Call with `line_start=1, line_end=1` | Returns only line 1 | [x] |
| 5 | Select a markdown cell with content | cell_type = markdown, content returned | [x] |

### 2.7 notebook_get_editing_cell_output
**Setup**: Execute a cell with output first

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run cell: `print("test output")` | Output visible | [x] |
| 2 | Call `notebook_get_editing_cell_output` with `detailed=false` | Concise output summary | [x] |
| 3 | Call with `detailed=true` | Full output with outputs array | [x] |
| 4 | Run cell with error: `1/0` | Error visible | [x] |
| 5 | Call tool | has_error true, error info present | [x] |
| 6 | Run cell with no output: `x = 1` | No output | [x] |
| 7 | Call tool | status completed_no_output, has_error false | [x] |
| 8 | Select a markdown cell | status not_code_cell | [x] |

### 2.8 notebook_get_notebook_cells
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Ensure notebook has 5+ executed cells | Multiple cells exist | [ ] |
| 2 | Call with `num_cells=3` | Returns last 3 cells | [ ] |
| 3 | Call with `num_cells=10`, `include_output=true` | Returns up to 10 cells with outputs | [ ] |
| 4 | Call with `num_cells=2`, `include_output=false` | Returns cells without output field | [ ] |
| 5 | Call with `detailed=true` | Returns full metadata per cell | [ ] |

### 2.9 notebook_move_cursor
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Ensure notebook has 5+ executed cells | Multiple executed cells exist | [ ] |
| 2 | Call with `target="above"` | Moves cursor to cell above | [ ] |
| 3 | Call with `target="below"` | Moves cursor to cell below | [ ] |
| 4 | Call with `target="bottom"` | Moves to last cell | [ ] |
| 5 | Call with `target="<exec_count>"` | Moves to that execution count cell | [ ] |
| 6 | Call with `target="999"` | Returns error for missing cell | [ ] |

### 2.10 qcodes_instrument_info (need another test)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `name="*"` | Returns list of instruments | [ ] |
| 2 | Call with `name="<instrument>"`, `detailed=false` | Concise summary | [ ] |
| 3 | Call with `name="<instrument>"`, `detailed=true` | Full info with hierarchy | [ ] |
| 4 | Call with `with_values=true` | Includes cached values | [ ] |
| 5 | Call with invalid name | Error returned | [ ] |

### 2.11 qcodes_get_parameter_info (need another test)
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

## Part 3: Unsafe Mode Tools

### 3.1 Switch to Unsafe Mode
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_unsafe` | Shows warning about unsafe mode | [ ] |
| 2 | Run: `%mcp_status` | Shows mode unsafe (pending restart) | [ ] |
| 3 | Run: `%mcp_restart` | Server restarts in unsafe mode | [ ] |
| 4 | Reconnect Inspector | Unsafe tools appear | [ ] |

### 3.2 notebook_update_editing_cell (Consent)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create a cell with `old content` | Cell has content | [ ] |
| 2 | Call `notebook_update_editing_cell` with new content | Consent dialog appears | [ ] |
| 3 | Click Deny | Tool returns denied, cell unchanged | [ ] |
| 4 | Call again and Approve | Cell content updated | [ ] |

### 3.3 notebook_execute_cell (Consent)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cell: `print("executed by MCP")` | Cell ready | [ ] |
| 2 | Call `notebook_execute_cell` | Consent dialog appears | [ ] |
| 3 | Approve | Cell executes, tool returns output | [ ] |
| 4 | Run error cell: `raise ValueError("test")` | has_error true, error details | [ ] |
| 5 | Run long cell with timeout=1.0 | Returns timeout status | [ ] |

### 3.4 notebook_add_cell
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_type=code`, `position=below`, `content="# new cell"` | New cell created with content | [ ] |
| 2 | Call with `cell_type=markdown`, `position=above`, `content="# Header"` | Markdown cell created with content | [ ] |
| 3 | Call with invalid `cell_type` | Error returned | [ ] |
| 4 | Call with invalid `position` | Error returned | [ ] |

### 3.5 notebook_delete_cell (Consent)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create a cell with `DELETE ME` | Cell exists | [ ] |
| 2 | Call `notebook_delete_cell` | Consent dialog appears | [ ] |
| 3 | Deny | Cell remains | [ ] |
| 4 | Approve | Selected cell deleted | [ ] |

### 3.6 notebook_delete_cells
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Execute 3 cells, note execution counts | Counts recorded | [ ] |
| 2 | Call `notebook_delete_cells` with two counts | Those cells deleted | [ ] |
| 3 | Call with invalid count | Error returned | [ ] |

### 3.7 notebook_apply_patch (Consent)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cell: `x = 1\ny = 2\nz = 3` | Cell ready | [ ] |
| 2 | Call `notebook_apply_patch` with old_text `y = 2`, new_text `y = 200` | Consent dialog appears | [ ] |
| 3 | Approve | Patch applied once | [ ] |
| 4 | Call with non-matching old_text | Error returned | [ ] |

### 3.8 Code Scanner Block (Unsafe)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_update_editing_cell` with dangerous pattern (e.g., `import subprocess`) | Tool blocks before consent, returns security error | [ ] |

---

## Part 4: Dangerous Mode

### 4.1 Switch to Dangerous Mode
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_dangerous` | Shows dangerous mode warning | [ ] |
| 2 | Run: `%mcp_restart` | Server restarts in dangerous mode | [ ] |
| 3 | Run: `%mcp_status` | mode = dangerous | [ ] |

### 4.2 Consent Bypass
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call any unsafe tool | No consent dialog | [ ] |
| 2 | Operation completes immediately | Success response | [ ] |
| 3 | Verify code scanner still blocks unsafe patterns | Dangerous patterns rejected | [ ] |

---

## Part 5: Optional Features

### 5.1 MeasureIt Tools (Optional)
**Enable**:
```python
%mcp_option measureit
%mcp_restart
```

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Verify tools appear | measureit_get_status, measureit_wait_for_sweep, measureit_wait_for_all_sweeps, measureit_kill_sweep | [ ] |
| 2 | Call `measureit_get_status` (no sweeps) | active=false, sweeps empty | [ ] |
| 3 | Start a sweep in notebook | Sweep running | [ ] |
| 4 | Call `measureit_get_status` | active true, sweep info present | [ ] |
| 5 | Call `measureit_wait_for_sweep` with variable_name | Waits until sweep completes | [ ] |
| 6 | Call `measureit_wait_for_all_sweeps` | Waits until all complete | [ ] |
| 7 | Call `measureit_kill_sweep` | Sweep stops and returns success | [ ] |

### 5.2 MeasureIt Resources (Optional)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `mcp_list_resources` | MeasureIt templates listed | [ ] |
| 2 | Call `mcp_get_resource` for a template | Returns code template text | [ ] |

### 5.3 Database Tools (Optional)
**Enable**:
```python
%mcp_option database
%mcp_restart
```

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Verify tools appear | database_list_available, database_list_experiments, database_get_dataset_info, database_get_database_stats | [ ] |
| 2 | Call `database_list_available` | Returns databases list | [ ] |
| 3 | Call `database_list_experiments` | Returns experiments list | [ ] |
| 4 | Call `database_get_dataset_info` with valid id | Returns dataset info | [ ] |
| 5 | Call with `code_suggestion=true` in safe mode | Returns code_suggestion only | [ ] |
| 6 | Switch to unsafe mode and call with `code_suggestion=true` | Adds and executes code cell, returns code_executed | [ ] |
| 7 | Call `database_get_database_stats` | Returns db stats | [ ] |
| 8 | Call with invalid id or path | Error returned | [ ] |

### 5.4 Database Resources (Optional)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `mcp_get_resource` with `resource://database_config` | Returns database path and status | [ ] |
| 2 | Call `mcp_get_resource` with `resource://recent_measurements` | Returns recent measurements | [ ] |
| 3 | Call database access templates | Returns template code text | [ ] |

---

## Part 6: Dynamic Tools (Dangerous Mode + Option)

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
| 3 | Register a tool (simple echo) | Tool created successfully | [ ] |
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

## Part 8: Shutdown and Cleanup

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Stop server | Server stopped | [ ] |
| 2 | Close Inspector connection | Connection closed | [ ] |
| 3 | Verify no lingering processes | No running MCP server | [ ] |
