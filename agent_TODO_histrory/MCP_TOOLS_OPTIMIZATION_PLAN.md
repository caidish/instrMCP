# MCP Tools Optimization Plan

This document lists all MCP tools and their current return templates.
Review each tool and provide instructions for optimization.

---

## ✅ Completed Optimizations

### 1. Image Data Sanitization in Cell Outputs (COMPLETED)
**Files Modified:**
- `instrmcp/extensions/jupyterlab/src/index.ts`

**Changes:**
- Added `sanitizeOutputData()` function that detects image MIME types
- Image data in `execute_result` and `display_data` outputs is replaced with:
  `"[PNG image, 1.2 MB - content omitted to save tokens]"`
- Supported MIME types: `image/png`, `image/jpeg`, `image/gif`, `image/svg+xml`, `image/webp`, `image/bmp`, `image/tiff`
- Estimated file size is calculated from base64 length

### 2. `notebook_move_cursor` - Added "bottom" Target (COMPLETED)
**Files Modified:**
- `instrmcp/extensions/jupyterlab/src/index.ts` (frontend)
- `instrmcp/servers/jupyter_qcodes/active_cell_bridge.py` (backend)
- `instrmcp/servers/jupyter_qcodes/tools.py` (backend)
- `instrmcp/servers/jupyter_qcodes/registrars/notebook_tools.py` (docstring)

**New Target:**
- `"bottom"`: Moves to the last cell in the notebook (by file order, not execution count)
- Uses `cells.length - 1` to get the true last cell index

### 3. `mcp_list_resources` - Simplified Guidance (COMPLETED)
**Files Modified:**
- `instrmcp/servers/jupyter_qcodes/registrars/resources.py`

**Changes:**
- Removed verbose `resources_vs_tools` section
- Removed `important_notes` section
- Replaced `when_to_use_resources` list with simple `workflow` string
- Kept `common_patterns` list unchanged
- New guidance structure: `{"workflow": "...", "common_patterns": [...]}`

### 4. `qcodes_instrument_info` - Added Parameter Path Note (COMPLETED)
**Files Modified:**
- `instrmcp/servers/jupyter_qcodes/registrars/qcodes_tools.py`

**Changes:**
- Added Note section to docstring explaining how to get live values using `qcodes_get_parameter_values`
- Format: `"{instrument}.{parameter}"` or `"{instrument}.{channel}.{parameter}"`

### 5. `notebook_get_variable_info` - Truncate repr (COMPLETED)
**Files Modified:**
- `instrmcp/servers/jupyter_qcodes/tools.py`

**Changes:**
- repr is now truncated to 500 characters
- Truncated repr includes `"... [truncated]"` suffix
- Added `"repr_truncated": true/false` field to response

### 6. `notebook_get_editing_cell` - Added max_lines Parameter (COMPLETED)
**Files Modified:**
- `instrmcp/servers/jupyter_qcodes/tools.py`
- `instrmcp/servers/jupyter_qcodes/registrars/notebook_tools.py`

**Changes:**
- Added `max_lines: int = 200` parameter
- Smart line selection logic:
  - If `line_start` AND `line_end` provided: use exact range
  - Else if `total_lines <= max_lines`: return all lines
  - Else if `line_start` provided: return `max_lines` from `line_start`
  - Else if `line_end` provided: return `max_lines` ending at `line_end`
  - Else: return first `max_lines` lines

### 7. `notebook_execute_cell` - Added Output/MeasureIt Note (COMPLETED)
**Files Modified:**
- `instrmcp/servers/jupyter_qcodes/tools_unsafe.py`

**Changes:**
- Added Note section to docstring about:
  - Using `notebook_get_editing_cell_output` to retrieve execution results
  - Using `measureit_get_status` and `measureit_wait_for_*` for measurement sweeps

---

## 1. Core Tools

### 1.1 `mcp_list_resources`
**Purpose:** List all available MCP resources with usage guidance
**Parameters:** None
**Current Return Template:**
```json
{
  "total_resources": 10,
  "resources": [
    {
      "uri": "resource://available_instruments",
      "name": "Available Instruments",
      "description": "JSON list of QCodes instruments...",
      "use_when": "Need to know what instruments exist...",
      "example": "Check this first to see instrument names..."
    }
  ],
  "guidance": {
    "resources_vs_tools": {...}, %comment delete
    "when_to_use_resources": [...], %comment need simplification
    "common_patterns": [...], %comment good.
    "important_notes": [...], %comment delete
  }
}
```
**Issues/Notes:** Very verbose, may consume too many tokens

---

### 1.2 `mcp_get_resource`
**Purpose:** Retrieve specific MCP resource content by URI
**Parameters:** `uri: str`
**Current Return Template:** Raw resource content (varies by resource type)
**Issues/Notes:** Returns full resource content, no truncation %comment this is not an issue. 

---

## 2. QCodes Instrument Tools

### 2.1 `qcodes_instrument_info`
**Purpose:** Get detailed information about a QCodes instrument
**Parameters:** `name: str`, `with_values: bool = False`
**Current Return Template:**
```json
{
  "name": "lockin",
  "class": "SR830",
  "parameters": {
    "X": {"value": 1.23, "unit": "V"},
    "Y": {"value": 0.45, "unit": "V"}
  },
  "submodules": {...}
}
```
**On Error:**
```json
{"error": "Error message"}
```
**Issues/Notes:** Full parameter tree can be very large %comment it is fine as is, user can choose what to do with it. However, the note needs to be added that to get parameter values, one can use qcodes_get_parameter_values tool, with the usage {name}.{channel}.{parameter} or {name}.{parameter} for non-multichannel instruments.

---

### 2.2 `qcodes_get_parameter_values`
**Purpose:** Get QCodes parameter values (single or batch)
**Parameters:** `queries: str` (JSON string)
**Current Return Template:**
```json
{
  "results": [
    {
      "instrument": "lockin",
      "parameter": "X",
      "value": 1.23,
      "unit": "V",
      "fresh": true
    }
  ]
}
```
**On Error:**
```json
{"error": "Error message"}
```
**Issues/Notes:** Batch queries can return large results %comment acceptable as is.

---

## 3. Notebook Tools (Read-Only)

### 3.1 `notebook_list_variables`
**Purpose:** List variables in the Jupyter namespace
**Parameters:** `type_filter: str = None`
**Current Return Template:**
```json
{
  "variables": [
    {"name": "lockin", "type": "SR830", "size": null},
    {"name": "data", "type": "ndarray", "size": 1000}
  ],
  "count": 2
}
```
**On Error:**
```json
{"error": "Error message"}
```
**Issues/Notes:** Can list many variables %comment acceptable as is.

---

### 3.2 `notebook_get_variable_info`
**Purpose:** Get detailed information about a notebook variable
**Parameters:** `name: str`
**Current Return Template:**
```json
{
  "name": "data",
  "type": "ndarray",
  "repr": "array([1, 2, 3, ...])",
  "attributes": {...}
}
```
**On Error:**
```json
{"error": "Error message"}
```
**Issues/Notes:** repr can be very long for large objects %comment repr should be truncated to first 500 characters with an indication if truncated.

---

### 3.3 `notebook_get_editing_cell`
**Purpose:** Get the currently editing cell content
**Parameters:** `fresh_ms: int = 1000`, `line_start: int = None`, `line_end: int = None`
**Current Return Template:**
```json
{
  "text": "import numpy as np\n...",
  "cell_type": "code",
  "index": 5,
  "execution_count": 10,
  "total_lines": 25,
  "lines_returned": 25,
  "truncated": false
}
```
**On Error:**
```json
{"error": "Error message"}
```
**Issues/Notes:** Already has line limiting, good design. %comment change the maximum lines returned to 200 as default, and as a parameters. The logic is this: if line_start and line_end are provided, return those lines. Else if total lines <= max_lines (200), return all lines. Else return 200 lines started with line_start if line_start is provided, else return 200 lines ending with the line_end is line_end is provided, else return first 200 lines.

---

### 3.4 `notebook_get_editing_cell_output`
**Purpose:** Get output of the most recently executed cell
**Parameters:** None
**Current Return Template (Success):**
```json
{
  "cell_number": 10,
  "execution_count": 10,
  "input": "print('hello')",
  "status": "completed",
  "output": "hello",
  "has_output": true,
  "has_error": false
}
```
**Current Return Template (Running):**
```json
{
  "cell_number": 10,
  "execution_count": 10,
  "input": "time.sleep(10)",
  "status": "running",
  "message": "Cell is currently executing...",
  "has_output": false,
  "has_error": false,
  "output": null
}
```
**Current Return Template (Error):**
```json
{
  "cell_number": 10,
  "execution_count": 10,
  "input": "1/0",
  "status": "error",
  "message": "Cell raised an exception",
  "output": null,
  "has_output": false,
  "has_error": true,
  "error": {
    "type": "ZeroDivisionError",
    "message": "division by zero",
    "traceback": "..."
  }
}
```
**Issues/Notes:** Good structure, but traceback can be long. %comment already changed for image sanitization. 

---

### 3.5 `notebook_get_notebook_cells`
**Purpose:** Get recent notebook cells with input/output
**Parameters:** `num_cells: int = 2`, `include_output: bool = True`
**Current Return Template:**
```json
{
  "cells": [
    {
      "cell_number": 9,
      "execution_count": 9,
      "input": "x = 1",
      "has_output": false,
      "has_error": false,
      "status": "completed_no_output"
    },
    {
      "cell_number": 10,
      "execution_count": 10,
      "input": "x * 2",
      "output": "2",
      "has_output": true,
      "has_error": false
    }
  ],
  "count": 2,
  "requested": 2,
  "error_count": 0,
  "note": "Only the most recent error can be captured..."
}
```
**Issues/Notes:** Good design with num_cells limit

---

### 3.6 `notebook_move_cursor`
**Purpose:** Move cursor to a different cell
**Parameters:** `target: str` ("above", "below", or cell number)
**Current Return Template:**
```json
{
  "success": true,
  "old_index": 5,
  "new_index": 6
}
```
**On Error:**
```json
{"error": "Error message"}
```
**Issues/Notes:** Simple and clean

---

### 3.7 `notebook_server_status`
**Purpose:** Get server status and configuration
**Parameters:** None
**Current Return Template:**
```json
{
  "status": "running",
  "mode": "unsafe",
  "tools_count": 25,
  "tools": ["tool1", "tool2", "..."]  // First 20 tools
}
```
**Issues/Notes:** Limits tools to 20, good design

---

## 4. Notebook Tools (Unsafe Mode)

### 4.1 `notebook_update_editing_cell`
**Purpose:** Update the content of the currently editing cell
**Parameters:** `content: str`
**Current Return Template:**
```json
{
  "success": true,
  "message": "Cell updated"
}
```
**On Decline:**
```json
{
  "success": false,
  "error": "Update declined: User declined"
}
```
**Issues/Notes:** Clean return format

---

### 4.2 `notebook_execute_cell`
**Purpose:** Execute the currently editing cell
**Parameters:** None
**Current Return Template:**
```json
{
  "success": true,
  "message": "Cell executed"
}
```
**On Decline:**
```json
{
  "success": false,
  "error": "Execution declined: User declined"
}
```
**Issues/Notes:** Execution result needs to be fetched separately via get_editing_cell_output
%comment add a note on the tool description: Execution result needs to be fetched separately via get_editing_cell_output and if there is a scan, use measureit tools to monitor it.
---

### 4.3 `notebook_add_cell`
**Purpose:** Add a new cell to the notebook
**Parameters:** `cell_type: str = "code"`, `position: str = "below"`, `content: str = ""`
**Current Return Template:**
```json
{
  "success": true,
  "message": "Cell added"
}
```
**Issues/Notes:** No consent required currently

---

### 4.4 `notebook_delete_cell`
**Purpose:** Delete the currently editing cell
**Parameters:** None
**Current Return Template:**
```json
{
  "success": true,
  "message": "Cell deleted"
}
```
**On Decline:**
```json
{
  "success": false,
  "error": "Deletion declined: User declined"
}
```
**Issues/Notes:** Clean return format

---

### 4.5 `notebook_delete_cells`
**Purpose:** Delete multiple cells by execution count
**Parameters:** `cell_numbers: str` (JSON array)
**Current Return Template:**
```json
{
  "success": true,
  "deleted_count": 3,
  "total_requested": 3,
  "results": [
    {"cell_number": 1, "status": "deleted"},
    {"cell_number": 2, "status": "deleted"},
    {"cell_number": 5, "status": "not_found"}
  ]
}
```
**Issues/Notes:** Good detail on per-cell status

---

### 4.6 `notebook_apply_patch`
**Purpose:** Apply a patch to the current cell content
**Parameters:** `old_text: str`, `new_text: str`
**Current Return Template:**
```json
{
  "success": true,
  "message": "Patch applied"
}
```
**On Decline:**
```json
{
  "success": false,
  "error": "Patch declined: User declined"
}
```
**Issues/Notes:** Clean return format

---

## 5. MeasureIt Tools (Optional)

### 5.1 `measureit_get_status`
**Purpose:** Check if any MeasureIt sweep is running
**Parameters:** None
**Current Return Template:**
```json
{
  "running": true,
  "sweeps": [
    {
      "variable_name": "sweep1d",
      "type": "Sweep1D",
      "status": "running",
      "progress": 45
    }
  ],
  "checked_variables": ["sweep1d", "sweep2d"]
}
```
**Issues/Notes:** Good structure

---

### 5.2 `measureit_wait_for_all_sweeps`
**Purpose:** Wait until all running sweeps finish
**Parameters:** None
**Current Return Template:**
```json
{
  "waited": true,
  "sweeps_completed": ["sweep1d", "sweep2d"],
  "duration_s": 120.5
}
```
**Issues/Notes:** Good structure

---

### 5.3 `measureit_wait_for_sweep`
**Purpose:** Wait until a specific sweep finishes
**Parameters:** `variable_name: str`
**Current Return Template:**
```json
{
  "waited": true,
  "variable_name": "sweep1d",
  "duration_s": 60.2
}
```
**Issues/Notes:** Good structure

---

## 6. Database Tools (Optional)

### 6.1 `database_list_experiments`
**Purpose:** List all experiments in the database
**Parameters:** `database_path: str = None`
**Current Return Template:** Raw JSON string from db module
**Issues/Notes:** Need to verify actual format

---

### 6.2 `database_get_dataset_info`
**Purpose:** Get detailed information about a dataset
**Parameters:** `id: int`, `database_path: str = None`
**Current Return Template:** Raw JSON string from db module
**Issues/Notes:** Need to verify actual format

---

### 6.3 `database_get_database_stats`
**Purpose:** Get database statistics and health info
**Parameters:** `database_path: str = None`
**Current Return Template:** Raw JSON string from db module
**Issues/Notes:** Need to verify actual format

---

### 6.4 `database_list_available`
**Purpose:** List all available QCodes databases
**Parameters:** None
**Current Return Template:** Raw JSON string from db module
**Issues/Notes:** Need to verify actual format

---

## 7. Dynamic Tools (Unsafe Mode)

### 7.1 `dynamic_register_tool`
**Purpose:** Register a new dynamic tool at runtime
**Parameters:** `name`, `source_code`, `version`, `description`, `author`, `capabilities`, `parameters`, `returns`, `examples`, `tags`
**Current Return Template (Success):**
```json
{
  "status": "success",
  "message": "Tool 'my_tool' registered successfully",
  "tool_name": "my_tool",
  "version": "1.0.0"
}
```
**With Auto-Correction:**
```json
{
  "status": "success_corrected",
  "message": "Tool 'my_tool' registered successfully (with 1 JSON field(s) auto-corrected)",
  "tool_name": "my_tool",
  "version": "1.0.0",
  "auto_corrections": {...}
}
```
**On Error:**
```json
{"status": "error", "message": "..."}
```
**Issues/Notes:** Good structure

---

### 7.2 `dynamic_update_tool`
**Purpose:** Update an existing dynamic tool
**Parameters:** `name`, `version`, `description`, `capabilities`, `parameters`, `returns`, `source_code`, `examples`, `tags`
**Current Return Template:**
```json
{
  "status": "success",
  "message": "Tool 'my_tool' updated successfully",
  "tool_name": "my_tool",
  "old_version": "1.0.0",
  "new_version": "1.1.0"
}
```
**Issues/Notes:** Good structure

---

### 7.3 `dynamic_revoke_tool`
**Purpose:** Revoke (delete) a dynamic tool
**Parameters:** `name: str`, `reason: str = None`
**Current Return Template:**
```json
{
  "status": "success",
  "message": "Tool 'my_tool' revoked successfully",
  "tool_name": "my_tool",
  "version": "1.0.0"
}
```
**Issues/Notes:** Good structure

---

### 7.4 `dynamic_list_tools`
**Purpose:** List all registered dynamic tools
**Parameters:** `tag: str = None`, `capability: str = None`, `author: str = None`
**Current Return Template:**
```json
{
  "status": "success",
  "count": 5,
  "tools": [
    {"name": "tool1", "version": "1.0.0", "description": "..."},
    ...
  ]
}
```
**Issues/Notes:** Good structure

---

### 7.5 `dynamic_inspect_tool`
**Purpose:** Inspect a dynamic tool's complete specification
**Parameters:** `name: str`
**Current Return Template:**
```json
{
  "status": "success",
  "tool": {
    "name": "my_tool",
    "version": "1.0.0",
    "description": "...",
    "source_code": "...",
    "parameters": [...],
    "capabilities": [...],
    "author": "...",
    ...
  }
}
```
**Issues/Notes:** Returns full spec including source code

---

### 7.6 `dynamic_registry_stats`
**Purpose:** Get statistics about the dynamic tool registry
**Parameters:** None
**Current Return Template:**
```json
{
  "status": "success",
  "stats": {
    "total_tools": 5,
    "by_author": {"claude": 3, "user": 2},
    "by_capability": {"cap:qcodes.read": 4},
    "registry_path": "~/.instrmcp/tools/"
  }
}
```
**Issues/Notes:** Good structure

---

## Optimization Opportunities Summary

| Category | Issue | Priority |
|----------|-------|----------|
| **mcp_list_resources** | Very verbose guidance section | Medium |
| **qcodes_instrument_info** | Full parameter tree can be huge | High |
| **notebook_get_variable_info** | repr can be very long | Medium |
| **notebook_get_editing_cell_output** | Traceback can be long | Low |
| **Database tools** | Unknown format, need verification | Low |
| **Error handling** | Inconsistent error format across tools | Medium |

---

## Instructions Format

Please provide optimization instructions in this format:

```
## Tool: <tool_name>
### Changes:
- [ ] Change 1
- [ ] Change 2

### New Return Template:
```json
{
  // new template
}
```

### Notes:
<any additional context>
```
