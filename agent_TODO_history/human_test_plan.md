# InstrMCP Comprehensive Human Test Plan

**Version**: Post-Update Full Functionality Test
**Date**: 2025-12-23
**Tester**: __caidish_

---

## Prerequisites

Before starting tests, ensure:
- [x] JupyterLab is installed and working
- [x] instrMCP is installed (`pip install -e .`)
- [x] MCP Inspector is available (https://inspector.tools.anthropic.com or local)
- [x] A QCodes station with at least one instrument is available (or mock - see below)
- [x] MeasureIt package is installed (for optional tests)
- [x] QCodes database exists with sample data (for optional tests)
- [x] NumPy and Pandas installed (for complex data type tests)

### Mock QCodes Station Setup
If no real instruments available, run this in your notebook to create a mock station:
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

## Part 1: Environment Setup & Server Lifecycle

### 1.1 Extension Loading
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Open JupyterLab | JupyterLab opens successfully | [x] |
| 2 | Create new Python notebook | New notebook opens | [x] |
| 3 | Run: `%load_ext instrmcp.extensions` | Extension loads without error, shows version info | [x] |
| 4 | Check toolbar | MCP toolbar widget appears in notebook toolbar | [x] |

### 1.2 Server Start (Safe Mode - Default)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_status` | Shows "Server is NOT running", mode: safe, lists available commands | [x] |
| 2 | Run: `%mcp_start` | Shows "MCP server started on http://localhost:XXXX", 🛡️ icon | [x] |
| 3 | Run: `%mcp_status` | Shows "Server is running", host, port, mode: safe | [x] |
| 4 | Note the port number | Port: __8123_ | [x] |

### 1.3 MCP Inspector Connection
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Open MCP Inspector in browser | Inspector UI loads | [x] |
| 2 | Set transport: "Streamable HTTP" | Transport selected | [x] |
| 3 | Enter URL: `http://localhost:<PORT>/mcp` | URL entered | [x] |
| 4 | Click "Connect" | Connection successful, tools list appears | [x] |
| 5 | Verify tools listed | Should see: qcodes_instrument_info, qcodes_get_parameter_values, notebook_list_variables, notebook_get_variable_info, notebook_get_editing_cell, notebook_get_editing_cell_output, notebook_get_notebook_cells, notebook_move_cursor, notebook_server_status, mcp_list_resources, mcp_get_resource | [x] |
| 6 | Verify NO unsafe tools | Should NOT see: notebook_update_editing_cell, notebook_execute_cell, notebook_add_cell, notebook_delete_cell, notebook_delete_cells, notebook_apply_patch | [x] |

### 1.4 Server Stop & Restart
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_close` | Shows "MCP server stopped" | [ ] | **Bug: hangs if there is a MCP server connectivity in Inspector. This needs to be fixed.**
| 2 | Run: `%mcp_status` | Shows "Server is NOT running" | [x] |
| 3 | In MCP Inspector, try any tool | Connection error or timeout | [x] |
| 4 | Run: `%mcp_start` | Server starts again | [x] |
| 5 | In MCP Inspector, reconnect | Connection successful | [x] |
| 6 | Run: `%mcp_restart` | Shows "Server restarted" | [x] |
| 7 | Verify Inspector still works | Tools still accessible after reconnect | [x] |

---

## Part 2: Safe Mode Tools Testing (via MCP Inspector)

### 2.1 notebook_server_status
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | In Inspector, select tool: `notebook_server_status` | Tool selected, no parameters needed | [x] |
| 2 | Click "Call Tool" with no parameters | Returns: mode="safe", server running, enabled_options list, registered_tools list | [ ] | Bug: it does not return enabled_options. 
| 3 | Verify mode is "safe" | mode field = "safe" | [x] |
| 4 | Verify registered_tools count | Should match tools shown in Inspector | [x] |

### 2.2 mcp_list_resources
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `mcp_list_resources` | Tool selected | [x] |
| 2 | Click "Call Tool" | Returns list of resources with names, URIs, descriptions | [x] |
| 3 | Verify resources include | Should see QCodes resources, possibly MeasureIt if enabled | [x] |

### 2.3 notebook_list_variables
**Setup**: In notebook, run this code first:
```python
import numpy as np
import pandas as pd

# Basic types
x = 42
my_list = [1, 2, 3]
my_dict = {"a": 1, "b": 2}
class MyClass: pass
obj = MyClass()

# Complex data types (for extended testing)
arr = np.array([[1, 2, 3], [4, 5, 6]])
df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
large_arr = np.zeros((1000, 1000))  # Large array
```

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `notebook_list_variables` | Tool selected | [x] |
| 2 | Call with no parameters | Returns list with x, my_list, my_dict, obj, arr, df, large_arr (and possibly internal vars) | [ ] | Potential Bug: it returns a validation error if type_filter is "null". But it works when it is empty. 
| 3 | Call with `type_filter`: "int" | Returns only variables of type int (x) | [x] |
| 4 | Call with `type_filter`: "list" | Returns only list type variables (my_list) | [x] |
| 5 | Call with `type_filter`: "NonExistentType" | Returns empty list or error | [x] |
| 6 | Call with `type_filter`: "ndarray" | Returns NumPy arrays (arr, large_arr) | [x] |
| 7 | Call with `type_filter`: "DataFrame" | Returns Pandas DataFrames (df) | [x] |

### 2.3.1 Complex Data Type Handling
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `notebook_get_variable_info` | Tool selected | [x] |
| 2 | Set `name`: "arr" (NumPy array) | Returns shape info, dtype, not full array content | [x] |
| 3 | Set `name`: "df" (DataFrame) | Returns columns, shape, dtype info | [x] |
| 4 | Set `name`: "large_arr" (1000x1000 array) | Returns summary info without memory explosion | [x] |
| 5 | Set `name`: "obj" (custom class) | Returns class name and repr without error | [x] |

### 2.4 notebook_get_variable_info
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `notebook_get_variable_info` | Tool selected | [x] |
| 2 | Set `name`: "x", `detailed`: false | Returns concise info: name, type (int), value repr | [x] |
| 3 | Set `name`: "x", `detailed`: true | Returns detailed info with additional metadata | [x] |
| 4 | Set `name`: "my_list", `detailed`: false | Returns list info with element count | [x] |
| 5 | Set `name`: "nonexistent_var" | Returns error: variable not found | [x] |
### 2.5 notebook_get_editing_cell
**Setup**: Click on a code cell and type some content like `print("hello")`

**Parameter Notes**:
- `fresh_ms`: Maximum age of snapshot in **milliseconds**. If cached snapshot is older, requests fresh data from frontend.
- `line_start`, `line_end`: **1-based** line numbers, **inclusive**. `line_start: 1, line_end: 1` returns only line 1.

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Click on a cell in notebook, type: `print("hello world")` | Cell has content | [x] |
| 2 | Select tool: `notebook_get_editing_cell` | Tool selected | [x] |
| 3 | Call with `detailed`: false | Returns: cell_type, cell_index, cell_content="print(\"hello world\")" | [x] |
| 4 | Call with `detailed`: true | Returns additional metadata: cursor_position, line info, fresh_threshold_ms | [x] |
| 5 | Set `fresh_ms`: 100 (require snapshot <100ms old) | Returns with `is_stale` field: true if older, false if fresh | [x] |
| 6 | Set `fresh_ms`: 10000 (10 second tolerance) | Should return `is_stale: false` for recently typed cell | [x] |
| 7 | Set `line_start`: 1, `line_end`: 1 | Returns only first line of cell (1-based, inclusive) | [ ] |
| 8 | Click on an empty cell | Empty cell selected | [x] |
| 9 | Call tool again | Returns empty content or minimal info | [x] |
| 10 | Click on markdown cell, type: `# Header` | Markdown cell selected | [x] |
| 11 | Call tool | Returns cell_type="markdown", content="# Header" | [x] |

### 2.6 notebook_get_editing_cell_output
**Setup**: Execute a cell with output first

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | In notebook, run cell: `print("test output")` | Cell executes, shows output | [x] |
| 2 | Select tool: `notebook_get_editing_cell_output` | Tool selected | [x] |
| 3 | Call with `detailed`: false | Returns output with "test output" in text | [] | Bug: detailed does not work as expected here. It still gives all the information regardless of detailed true/false.
| 4 | Call with `detailed`: true | Returns full output with status, outputs array, has_output, has_error fields | [x] |
| 5 | Run cell with error: `1/0` | Cell shows ZeroDivisionError | [x] |
| 6 | Call tool | Returns error info with traceback, has_error=true | [x] |
| 7 | Run cell with no output: `x = 1` | Cell executes, no visible output | [x] |
| 8 | Call tool | Returns empty or minimal output | [ ] | Bug: {
  "status": "error",
  "message": "Cell raised an exception",
  "outputs": null,
  "has_output": false,
  "has_error": true
} It should not have has_error true when there is no error. It seems correlated with the previous error cell. If I run a successful output cell again, it works fine.

### 2.7 notebook_get_notebook_cells
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Ensure notebook has 5+ executed cells | Multiple cells exist | [x] |
| 2 | Select tool: `notebook_get_notebook_cells` | Tool selected | [x] |
| 3 | Call with `num_cells`: 3 | Returns last 3 cells with input/output | [x] |
| 4 | Call with `num_cells`: 10, `include_output`: true | Returns up to 10 cells with outputs | [x] |
| 5 | Call with `num_cells`: 2, `include_output`: false | Returns 2 cells without output field | [x] |
| 6 | Call with `detailed`: true | Returns full metadata for each cell | [x] |

### 2.8 notebook_move_cursor
**Parameter Notes**:
- `target`: Can be "above", "below", "bottom", or an **execution count** as string (e.g., "5" for cell `[5]`)
- Numeric targets refer to the **execution count** (the `In[#]:` number), NOT visual position
- Cells that haven't been executed don't have execution counts

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Ensure notebook has 5+ executed cells | Multiple executed cells exist | [x] |
| 2 | Note execution counts (e.g., `[1]`, `[3]`, `[5]`) | Execution counts: _18_, _14__, _17_ | [x] |
| 3 | Click on any cell | Cell is active | [x] |
| 4 | Select tool: `notebook_move_cursor` | Tool selected | [x] |
| 5 | Set `target`: "above" | Returns success, cursor moves up one cell | [x] |
| 6 | Verify in notebook | Previous cell is now active | [x] |
| 7 | Set `target`: "below" | Returns success, cursor moves down one cell | [x] |
| 8 | Set `target`: "bottom" | Returns success, cursor moves to last cell (by file order) | [x] |
| 9 | Set `target`: "<exec_count>" (e.g., "5") | Returns success, cursor moves to cell `[5]` | [x] |
| 10 | Set `target`: "999" (non-existent count) | Returns error: cell not found | [ ] | Bug: this gives a success response even though the cell does not exist. No cursor movement happens.

### 2.9 qcodes_instrument_info
**Prerequisite**: Have a QCodes station with instruments loaded

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | In notebook, set up QCodes station with instrument | Station loaded | [x] |
| 2 | Select tool: `qcodes_instrument_info` | Tool selected | [x] |
| 3 | Call with no parameters | Returns list of all instruments with overview | [x] | Expected: it returns error. When return *, it returns all instruments. But when no parameters, it gives error.
| 4 | Set `name`: "<instrument_name>", `detailed`: false | Returns concise info for that instrument | [x] | 
| 5 | Set `name`: "<instrument_name>", `detailed`: true | Returns full parameter list with types, values | [x] |
| 6 | Set `with_values`: true | Returns current parameter values | [x] | 
| 7 | Set `name`: "nonexistent_instrument" | Returns error: instrument not found | [x] |

### 2.10 qcodes_get_parameter_values
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `qcodes_get_parameter_values` | Tool selected | [x] |
| 2 | Set `queries`: `[{"instrument": "<name>", "parameter": "<param>"}]` (valid JSON) | Returns parameter value | [x] |
| 3 | Test batch query: `[{"instrument": "<name>", "parameter": "<param1>"}, {"instrument": "<name>", "parameter": "<param2>"}]` | Returns multiple values | [x] |
| 4 | Set `detailed`: true | Returns additional metadata per parameter | [x] |
| 5 | Query non-existent parameter | Returns error for that query | [x] |
| 6 | Test invalid JSON format | Returns JSON parse error | [x] |

---

## Part 3: Mode Switching & Unsafe Mode

### 3.1 Switch to Unsafe Mode
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_unsafe` | Shows warning about unsafe mode, ⚠️ icon | [x] |
| 2 | Run: `%mcp_status` | Shows mode: unsafe (pending restart) | [x] |
| 3 | Run: `%mcp_restart` | Server restarts with unsafe mode | [x] |
| 4 | In MCP Inspector, reconnect | Connection successful | [x] |
| 5 | Verify unsafe tools NOW appear | Should see: notebook_update_editing_cell, notebook_execute_cell, notebook_add_cell, notebook_delete_cell, notebook_delete_cells, notebook_apply_patch | [x] |

### 3.2 notebook_update_editing_cell (Requires Consent)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | In notebook, create cell with: `old content` | Cell has content | [x] |
| 2 | Select tool: `notebook_update_editing_cell` | Tool selected | [x] |
| 3 | Set `content`: "new content from MCP" | Parameters set | [x] |
| 4 | Click "Call Tool" | **CONSENT DIALOG appears in JupyterLab** | [x] |
| 5 | Observe consent dialog | Shows old content vs new content, Approve/Deny buttons | [x] |
| 6 | Click "Deny" | Tool returns: consent denied, cell unchanged | [x] |
| 7 | Call tool again, click "Approve" | Tool returns success, cell content updated | [x] |
| 8 | Verify in notebook | Cell now shows "new content from MCP" | [x] |

### 3.3 notebook_execute_cell (Requires Consent)
**Parameter Notes**:
- `timeout`: Maximum execution time in **seconds** (float). Default is typically 30-60s.

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | In notebook, create cell: `print("executed by MCP")` | Cell ready | [x] |
| 2 | Select tool: `notebook_execute_cell` | Tool selected | [x] |
| 3 | Click "Call Tool" | **CONSENT DIALOG appears** | [x] |
| 4 | Click "Approve" | Cell executes, shows output | [x] |
| 5 | Tool returns | Returns execution result, output, execution_count | [] | Critical Bug: there is no output included when detailed is false. It should include output always. For print, it gives no output, and no input. It seems like it did not use the active_cell_bridge properly. 
| 6 | Test with error cell: `raise ValueError("test")` | Consent dialog appears | [x] |
| 7 | Approve and execute | Returns with has_error=true, error details | [] | Critical Bug: when detailed is false, it gives null error_type and error_message. It should always include error info when there is an error. The difference in detailed true and false suggests critical implementation issues.
| 8 | Test timeout: set `timeout`: 1.0 (1 second), run `import time; time.sleep(10)` | Returns timeout error after ~1 second | [x] |

### 3.4 notebook_add_cell
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Note current cell count | Count: _____ | [x] |
| 2 | Select tool: `notebook_add_cell` | Tool selected | [x] |
| 3 | Set `cell_type`: "code", `position`: "below", `content`: "# new cell" | Parameters set | [x] |
| 4 | Click "Call Tool" | Returns success | [x] |
| 5 | Verify in notebook | New code cell appears below current with "# new cell" | [x] |
| 6 | Set `cell_type`: "markdown", `position`: "above", `content`: "# Markdown Header" | Parameters set | [x] |
| 7 | Click "Call Tool" | Returns success | [x] |
| 8 | Verify in notebook | Markdown cell appears above with "# Markdown Header" | [] |
Critical Bug: it adds the cell but it does not set the content properly. The new cell is empty instead of having the specified content.
| 9 | Test invalid `cell_type`: "invalid" | Returns error | [x] |
| 10 | Test invalid `position`: "sideways" | Returns error | [] |
Crytical Bug: When detailed is false, the error message is not passed. It should be passed. 

### 3.5 notebook_delete_cell (Requires Consent)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create a test cell with content: `DELETE ME` | Cell exists | [x] |
| 2 | Click on the cell to select it | Cell is active | [x] |
| 3 | Select tool: `notebook_delete_cell` | Tool selected | [x] |
| 4 | Click "Call Tool" | **CONSENT DIALOG appears** | [x] |
| 5 | Observe dialog | Shows cell content being deleted | [x] |
| 6 | Click "Deny" | Cell remains, tool returns denied | [x] |
| 7 | Call again, click "Approve" | Cell is deleted | [ ] |
Very critial bug: delete cell will delete recent 2-5 cells instead of the selected one. This is a major issue that needs to be fixed urgently. Not that delete_cells works fine, but (by design) it only delete those with cell_numbers(runned cells). The current editing cell delete (this tool) is broken. 
| 8 | Verify in notebook | Cell no longer exists | [x] |

### 3.6 notebook_delete_cells
**Parameter Notes**:
- `cell_numbers`: Array of **execution counts** (the `[#]:` number shown in cell), NOT visual indices
- Execution count is the number shown in `In [#]:` prefix of each cell after execution

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create and execute 3 test cells, note their `[#]:` execution counts | Execution counts: ___, ___, ___ | [x] |
| 2 | Select tool: `notebook_delete_cells` | Tool selected | [x] |
| 3 | Set `cell_numbers`: [<exec_count_1>, <exec_count_2>] (as JSON array of integers) | Parameters set | [x] |
| 4 | Click "Call Tool" | Returns success for each | [x] |
| 5 | Verify in notebook | Two cells deleted, one remains | [x] |
| 6 | Test with invalid execution count: [99999] | Returns error or not found | [x] |

### 3.7 notebook_apply_patch (Requires Consent)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cell with: `x = 1\ny = 2\nz = 3` | Cell has multi-line content | [x] |
| 2 | Select tool: `notebook_apply_patch` | Tool selected | [x] |
| 3 | Set `old_text`: "y = 2", `new_text`: "y = 200" | Parameters set | [x] |
| 4 | Click "Call Tool" | **CONSENT DIALOG appears** | [x] |
| 5 | Click "Approve" | Patch applied | [x] |
Critical Bug: The tool will randomly apply 2-3 times. It should only apply once. It retuls y = 2000000 instead of y = 200. This needs to be fixed.
| 6 | Verify in notebook | Cell now shows `x = 1\ny = 200\nz = 3` | [ ] |
| 7 | Test with non-matching old_text: "not found text" | Returns error: text not found | [ ] |

---

## Part 4: Dangerous Mode & Dynamic Tools

### 4.1 Switch to Dangerous Mode
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_dangerous` | Shows multiple ☠️ warnings about auto-approval | [x] |
| 2 | Run: `%mcp_restart` | Server restarts in dangerous mode | [x] |
| 3 | Run: `%mcp_status` | Shows mode: dangerous | [x] |

### 4.2 Verify Consent Bypass
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cell with content: `test` | Cell exists | [x] |
| 2 | Call `notebook_update_editing_cell` with `content`: "bypassed" | **NO consent dialog appears** | [x] |
| 3 | Tool returns immediately | Success, no user interaction needed | [x] |
| 4 | Verify in notebook | Cell updated without consent prompt | [x] |
---

## Part 5: Optional Features

### 5.1 MeasureIt Tools (if MeasureIt installed)
**Prerequisite**: MeasureIt package installed, sweep running

#### Enable MeasureIt
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_option add measureit` | Option enabled | [x] |
| 2 | Run: `%mcp_restart` | Server restarts | [x] |
| 3 | Verify in Inspector | Tools appear: measureit_get_status, measureit_wait_for_sweep, measureit_wait_for_all_sweeps | [x] |

#### measureit_get_status
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | With NO sweep running | Returns empty or "no sweeps" status | [ ] |
| 2 | Start a sweep in notebook | Sweep starts | [ ] |
| 3 | Call tool again | Returns running sweep info | [ ] |
bug: it should have a detailed option just like other tools to get more info.
Behavior: if detailed option is false, it only gives active, and sweeps name. 
If the option is true, it give full info as now. 

#### measureit_wait_for_sweep
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Start a short sweep, note variable name | Sweep: __s_0D___ | [x] |
| 2 | Set `variable_name`: "<sweep_var>" | Parameter set | [x] |
| 3 | Call tool | Blocks until sweep completes, returns completion | [x] |
bug: it should have a detailed option just like other tools to get more info.
Behavior: if detailed option is false, it only gives sweep's state
If the option is true, it give full info as now. 

#### measureit_wait_for_all_sweeps
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Start multiple sweeps | Sweeps running | [x] |
| 2 | Call tool | Blocks until ALL sweeps complete | [x] |
bug: it should have a detailed option just like other tools to get more info.
Behavior: if detailed option is false, it only gives sweep's state
If the option is true, it give full info as now. 

### 5.2 Database Tools (if QCodes database exists)

#### Enable Database
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_option add database` | Option enabled | [x] |
| 2 | Run: `%mcp_restart` | Server restarts | [x] |
| 3 | Verify in Inspector | Tools appear: database_list_experiments, database_get_dataset_info, database_get_database_stats, database_list_available | [x] |

#### database_list_available
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `database_list_available` | Tool selected | [x] |
| 2 | Call tool | Returns list of database files with metadata | [x] |
bug: it should have a detailed option just like other tools to get more info.
Behavior: if detailed option is false, it only gives databases names and paths
If the option is true, it give full info as now. 

#### database_list_experiments
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `database_list_experiments` | Tool selected | [x] |
| 2 | Call with no parameters (uses default DB) | Returns experiments list | [x] |
| 3 | Set `database_path`: "<path_to_db>" | Specific DB path | [x] |
| 4 | Call tool | Returns experiments from that DB | [x] |
| 5 | Set `detailed`: true | Returns additional metadata | [x] |

#### database_get_dataset_info
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Note a dataset ID from list_experiments | ID: _____ | [x] |
| 2 | Select tool: `database_get_dataset_info` | Tool selected | [x] |
| 3 | Set `id`: <dataset_id> | Parameter set | [x] |
| 4 | Call tool | Returns dataset info, parameters, metadata | [x] |
| 5 | Set `code_suggestion`: true | Returns example code to load dataset | [x] |
| 6 | Test invalid ID: 999999 | Returns error: dataset not found | [x] |

#### database_get_database_stats
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Select tool: `database_get_database_stats` | Tool selected | [x] |
| 2 | Call tool | Returns: file size, experiment count, dataset count, last modified | [x] |

---

## Part 6: Frontend Widget Testing (JupyterLab Toolbar)

### 6.1 Toolbar Widget Visibility
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Open a new notebook | Notebook opens | [x] |
| 2 | Load extension: `%load_ext instrmcp.extensions` | Extension loads | [x] |
| 3 | Observe notebook toolbar | MCP toolbar widget appears (usually right side) | [x] |
| 4 | Widget shows | Status indicator, mode icon, control buttons | [x] |

### 6.2 Status Indicator
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Before starting server | Status shows "Stopped" or red indicator | [x] |
| 2 | Click "Start" button or run `%mcp_start` | Status changes to "Running" or green | [x] |
| 3 | Stop server: `%mcp_close` | Status changes back to "Stopped" | [x] |

### 6.3 Mode Selector (Dropdown)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Stop server if running | Server stopped | [x] |
| 2 | Click mode dropdown in toolbar | Dropdown opens showing: Safe, Unsafe, Dangerous | [x] |
| 3 | Select "Safe" | 🛡️ icon shown, mode set to safe | [x] |
| 4 | Select "Unsafe" | ⚠️ icon shown, mode set to unsafe | [x] |
| 5 | Select "Dangerous" | ☠️ icon shown, mode set to dangerous | [x] |
| 6 | Start server | Server starts in selected mode | [x] |
| 7 | Try to change mode while running | Dropdown should be **disabled** or show warning | [x] |

### 6.4 Server Control Buttons
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | With server stopped | "Start" enabled, "Stop" disabled, "Restart" disabled | [x] |
| 2 | Click "Start" | Server starts, buttons update | [x] |
| 3 | With server running | "Start" disabled, "Stop" enabled, "Restart" enabled | [x] |
| 4 | Click "Stop" | Server stops, buttons update | [x] |
| 5 | Start server, click "Restart" | Server restarts (brief stop/start) | [x] |

### 6.5 Options Panel
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Stop server | Server stopped | [ ] |
| 2 | Open options panel (expand or click options) | Panel shows available options | [ ] |
| 3 | Verify options shown | measureit, database, dynamictool toggles | [ ] |
| 4 | Toggle "measureit" ON | Toggle switches to ON state | [ ] |
| 5 | Toggle "database" ON | Toggle switches to ON state | [ ] |
| 6 | Verify dynamictool shows mode requirement | Should indicate "requires dangerous mode" | [ ] |
| 7 | Set mode to Safe, try toggle dynamictool | Should be disabled or show warning | [ ] |
| 8 | Set mode to Dangerous, toggle dynamictool | Should enable successfully | [ ] |
| 9 | Start server | Server starts with enabled options | [ ] |
| 10 | Verify via `%mcp_status` | Options shown as enabled | [ ] |
| 11 | Try to toggle options while running | Toggles should be **disabled** | [ ] |

### 6.6 Port/Host Display
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Start server | Server running | [ x] |
| 2 | Observe toolbar | Should display host:port (e.g., localhost:3000) | [x] |
| 3 | Note displayed port matches `%mcp_status` | Ports match | [x] |

### 6.7 Kernel Restart Handling
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Start MCP server | Server running | [x] |
| 2 | Restart kernel (Kernel menu > Restart) | Kernel restarts | [x] |
| 3 | Observe toolbar widget | Should detect kernel restart | [x] |
| 4 | Widget state | Should show "Stopped" or prompt to reload extension | [x] |
| 5 | Run `%load_ext instrmcp.extensions` again | Extension reloads | [x] |
| 6 | Toolbar should reinitialize | Widget functional again | [x] |

---

## Part 7: Consent Dialog Testing (Unsafe Mode)

### 7.1 Consent Dialog Appearance
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Switch to unsafe mode, restart server | Unsafe mode active | [x] |
| 2 | Call `notebook_update_editing_cell` | Consent dialog appears | [x] |
| 3 | Observe dialog content | Shows: operation type, old content, new content | [x] |
| 4 | Verify buttons | "Approve" and "Deny" buttons present | [x] |
| 5 | Verify dialog is modal | Cannot interact with notebook while dialog open | [x] |

### 7.2 Consent Deny Flow
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Trigger consent dialog (any unsafe operation) | Dialog appears | [x] |
| 2 | Click "Deny" | Dialog closes | [x] |
| 3 | Check tool response | Returns consent_denied or similar error | [x] |
| 4 | Verify no change occurred | Notebook state unchanged | [x] |

### 7.3 Consent Approve Flow
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Trigger consent dialog | Dialog appears | [x] |
| 2 | Click "Approve" | Dialog closes | [x] |
| 3 | Check tool response | Returns success | [x] |
| 4 | Verify change occurred | Operation completed | [x] |

### 7.4 Consent Timeout (if applicable)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Trigger consent dialog | Dialog appears | [x] |
| 2 | Wait without clicking (check if timeout exists) | May timeout or wait indefinitely | [x] |
| 3 | Document behavior | Timeout: ___ seconds OR infinite wait | [x] |

### 7.5 Dangerous Mode Bypass Verification
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Switch to dangerous mode, restart | Dangerous mode active | [x] |
| 2 | Call any unsafe operation | **NO dialog appears** | [x] |
| 3 | Operation completes immediately | Consent auto-approved | [x] |