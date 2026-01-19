# InstrMCP Cell Targeting Feature Test Plan (Jan 16, 2026)

**Version**: Cell targeting enhancement testing (new `cell_id_notebook`, `cell_execution_number` fields)
**Date**: 2026-01-16
**Tester**: ________________
**Branch**: AI_safety

---

## Overview of Changes Being Tested

This test plan verifies the new cell targeting features that enable:
1. **Position-based cell access** (`cell_id_notebook`) - works for ALL cells including markdown/unexecuted
2. **Execution-based cell access** (`cell_execution_number`) - works for executed code cells only
3. **New `index:N` navigation** - move cursor to any cell by position
4. **Two-phase cell retrieval** - lightweight structure fetch + targeted cell content fetch

### Key Field Naming Changes
| Old Field | New Field | Meaning |
|-----------|-----------|---------|
| `cell_index` | `cell_id_notebook` | Position in notebook (0-indexed), stable for session |
| `execution_count` | `cell_execution_number` | IPython's In[N] counter, only for executed cells |
| `input` | `source` | Cell content/code |
| `cell_number` | `cell_execution_number` | (in delete_cells) |

---

## Prerequisites

Before starting tests, ensure:
- [ ] JupyterLab is running with latest extension build
- [ ] instrmcp installed with latest changes (`pip install -e .`)
- [ ] MCP Inspector available (https://inspector.tools.anthropic.com)
- [ ] Conda environment `instrMCPdev` activated

### Rebuild Extension (if needed)
```bash
cd instrmcp/extensions/jupyterlab && jlpm run build
pip install -e . --force-reinstall --no-deps
# Restart JupyterLab completely
```

### Start Server
```python
%load_ext instrmcp.extensions
%mcp_start
```

---

## Part 1: Environment Setup

### 1.1 Create Test Notebook Structure
Create a notebook with this EXACT structure for consistent testing:

| Position | Type | Content | Executed? |
|----------|------|---------|-----------|
| 0 | markdown | `# Test Notebook Header` | N/A |
| 1 | code | `x = 1` | Execute → [1] |
| 2 | markdown | `## Section 1` | N/A |
| 3 | code | `y = 2` | Execute → [2] |
| 4 | code | `# unexecuted code cell` | NO |
| 5 | markdown | `## Section 2` | N/A |
| 6 | code | `z = x + y` | Execute → [3] |
| 7 | code | `print("hello")` | Execute → [4] |

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create cells as above | 8 cells total | [ ] |
| 2 | Execute cells 1, 3, 6, 7 | Execution counts [1], [2], [3], [4] | [ ] |
| 3 | Leave cell 4 unexecuted | Cell 4 has no execution count | [ ] |
| 4 | Note total: 4 markdown/raw, 4 code (3 executed, 1 unexecuted) | Structure verified | [ ] |

---

## Part 2: notebook_get_notebook_cells - New Features

### 2.1 Basic Two-Phase Retrieval
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_get_notebook_cells` with `num_cells=3` | Returns last 3 cells with NEW field names | [ ] |
| 2 | Verify `total_cells` field | Should be 8 | [ ] |
| 3 | Verify each cell has `cell_id_notebook` | 0-indexed positions present | [ ] |
| 4 | Verify each cell has `cell_type` | "code", "markdown", or "raw" | [ ] |
| 5 | Verify each cell has `cell_execution_number` | Number for executed, null for unexecuted/markdown | [ ] |
| 6 | Verify each cell has `source` (not `input`) | Cell content present | [ ] |

### 2.2 Fetch Specific Cells by Position (NEW)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_id_notebooks="[0]"` | Returns ONLY cell 0 (markdown header) | [ ] |
| 2 | Verify cell_type | Should be "markdown" | [ ] |
| 3 | Verify cell_execution_number | Should be null (markdown has no execution) | [ ] |
| 4 | Call with `cell_id_notebooks="[0, 2, 5]"` | Returns 3 cells (all markdown) | [ ] |
| 5 | Verify all returned cells are markdown | cell_type = "markdown" for all | [ ] |

### 2.3 Fetch Unexecuted Code Cell (NEW - Critical Test)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_id_notebooks="[4]"` | Returns cell 4 (unexecuted code) | [ ] |
| 2 | Verify cell_type | Should be "code" | [ ] |
| 3 | Verify cell_execution_number | Should be null (not executed) | [ ] |
| 4 | Verify source | Should contain "# unexecuted code cell" | [ ] |
| 5 | Verify status | Should be "not_executed" | [ ] |

### 2.4 Mixed Cell Types
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_id_notebooks="[1, 2, 4, 6]"` | Returns 4 cells (code, markdown, code, code) | [ ] |
| 2 | Cell at index 1 | cell_type="code", cell_execution_number=1 | [ ] |
| 3 | Cell at index 2 | cell_type="markdown", cell_execution_number=null | [ ] |
| 4 | Cell at index 4 | cell_type="code", cell_execution_number=null | [ ] |
| 5 | Cell at index 6 | cell_type="code", cell_execution_number=3 | [ ] |

### 2.5 Output Fetching for Executed Cells
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_id_notebooks="[7]"`, `include_output=true` | Returns cell 7 with outputs | [ ] |
| 2 | Verify outputs array | Contains stream output "hello\n" | [ ] |
| 3 | Call with `cell_id_notebooks="[0]"`, `include_output=true` | Returns markdown cell, no outputs array | [ ] |
| 4 | Call with `cell_id_notebooks="[4]"`, `include_output=true` | Returns unexecuted cell, status="not_executed" | [ ] |

### 2.6 Edge Cases
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `cell_id_notebooks="[100]"` | Returns empty cells array (out of bounds) | [ ] |
| 2 | Call with `cell_id_notebooks="[-1]"` | Returns empty or error | [ ] |
| 3 | Call with `cell_id_notebooks="invalid"` | Returns error about JSON format | [ ] |
| 4 | Call with `num_cells=100` (more than exist) | Returns all 8 cells | [ ] |

### 2.7 Concise vs Detailed Mode
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `detailed=false` (default) | Truncated source (100 chars), basic fields | [ ] |
| 2 | Call with `detailed=true` | Full source, all metadata | [ ] |
| 3 | Verify concise has `cell_id_notebook` | Present in concise mode | [ ] |
| 4 | Verify concise has `cell_execution_number` | Present in concise mode | [ ] |
| 5 | Verify concise has `cell_type` | Present in concise mode | [ ] |

---

## Part 3: notebook_move_cursor - New `index:N` Format

### 3.1 Navigate to Markdown Cells (NEW - Critical Test)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `target="index:0"` | Moves to markdown header (position 0) | [ ] |
| 2 | Verify active cell in JupyterLab | First cell (markdown) is selected | [ ] |
| 3 | Call with `target="index:2"` | Moves to markdown section header | [ ] |
| 4 | Verify active cell | Third cell (markdown) is selected | [ ] |

### 3.2 Navigate to Unexecuted Code Cell (NEW - Critical Test)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `target="index:4"` | Moves to unexecuted code cell | [ ] |
| 2 | Verify active cell | Cell with "# unexecuted code cell" is selected | [ ] |
| 3 | This was IMPOSSIBLE before | Old method required execution count | [ ] |

### 3.3 Compare `index:N` vs Execution Count Navigation
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `target="index:1"` | Moves to position 1 (first code cell) | [ ] |
| 2 | Call with `target="1"` (execution count) | Moves to cell [1] (same cell in this case) | [ ] |
| 3 | Call with `target="index:6"` | Moves to position 6 | [ ] |
| 4 | Call with `target="3"` (execution count) | Moves to cell [3] (same cell - position 6) | [ ] |

### 3.4 Edge Cases
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `target="index:7"` | Moves to last cell (position 7) | [ ] |
| 2 | Call with `target="index:8"` | Error: invalid index (out of bounds) | [ ] |
| 3 | Call with `target="index:-1"` | Error: invalid index | [ ] |
| 4 | Call with `target="index:abc"` | Error: invalid index format | [ ] |

### 3.5 Existing Navigation (Verify Still Works)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with `target="above"` | Moves to cell above current | [ ] |
| 2 | Call with `target="below"` | Moves to cell below current | [ ] |
| 3 | Call with `target="bottom"` | Moves to last cell | [ ] |
| 4 | Call with `target="4"` (execution count) | Moves to cell [4] | [ ] |

---

## Part 4: notebook_delete_cells - New `cell_id_notebooks` Parameter

### 4.1 Switch to Unsafe Mode
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_unsafe` | Mode changed to unsafe | [ ] |
| 2 | Run: `%mcp_restart` | Server restarts in unsafe mode | [ ] |
| 3 | Reconnect Inspector | Unsafe tools visible including notebook_delete_cells | [ ] |

### 4.2 Delete Markdown Cell by Position (NEW - Critical Test)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Add a test markdown cell at position 0 | New markdown cell exists | [ ] |
| 2 | Call with `cell_id_notebooks="[0]"` | Consent dialog appears | [ ] |
| 3 | Approve deletion | Markdown cell deleted | [ ] |
| 4 | Verify first cell is now different | Original cell 1 is now at position 0 | [ ] |
| 5 | This was IMPOSSIBLE before | Old method required execution count | [ ] |

### 4.3 Delete Unexecuted Code Cell by Position (NEW - Critical Test)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Add a new code cell with `# delete me` (don't execute) | Unexecuted cell exists | [ ] |
| 2 | Note its position (e.g., position 8) | Position recorded | [ ] |
| 3 | Call with `cell_id_notebooks="[8]"` | Consent dialog appears | [ ] |
| 4 | Approve deletion | Unexecuted cell deleted | [ ] |
| 5 | This was IMPOSSIBLE before | Old method required execution count | [ ] |

### 4.4 Delete by Execution Count (Legacy Support)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Execute a new cell to get execution count [5] | Cell [5] exists | [ ] |
| 2 | Call with `cell_execution_numbers="[5]"` | Consent dialog appears | [ ] |
| 3 | Approve deletion | Cell [5] deleted | [ ] |

### 4.5 Delete Multiple Cells by Position
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Create 3 test cells at end | 3 new cells exist | [ ] |
| 2 | Note their positions | Positions recorded | [ ] |
| 3 | Call with `cell_id_notebooks="[pos1, pos2, pos3]"` | Consent shows 3 cells | [ ] |
| 4 | Approve | All 3 cells deleted | [ ] |
| 5 | Verify deleted_count | Should be 3 | [ ] |

### 4.6 Error Cases
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call with both parameters | Error: cannot specify both | [ ] |
| 2 | Call with neither parameter | Error: must specify one | [ ] |
| 3 | Call with `cell_id_notebooks="[100]"` | Success but deleted_count=0 (out of bounds) | [ ] |
| 4 | Call with invalid JSON | Error: invalid format | [ ] |

### 4.7 Cache Invalidation (Technical Verification)
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Execute cell to create output cache | Cell [N] has cached output | [ ] |
| 2 | Delete cell by position using `cell_id_notebooks` | Cell deleted | [ ] |
| 3 | Verify response includes `invalidated_exec_counts` | Shows [N] was invalidated | [ ] |

---

## Part 5: Dangerous Mode - Consent Bypass

### 5.1 Switch to Dangerous Mode
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Run: `%mcp_dangerous` | Mode changed to dangerous | [ ] |
| 2 | Run: `%mcp_restart` | Server restarts in dangerous mode | [ ] |

### 5.2 Delete Without Consent
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Add test markdown cell | Cell exists | [ ] |
| 2 | Call `notebook_delete_cells` with `cell_id_notebooks` | No consent dialog | [ ] |
| 3 | Cell deleted immediately | Success response | [ ] |

---

## Part 6: Frontend Widget Verification

### 6.1 Toolbar Status
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Verify mode displays correctly | Shows current mode (safe/unsafe/dangerous) | [ ] |
| 2 | Verify server status | Shows Running/Stopped correctly | [ ] |

### 6.2 Cell Selection Visual Feedback
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Use `notebook_move_cursor` with `index:N` | JupyterLab highlights correct cell | [ ] |
| 2 | Verify scroll | Scrolls to selected cell if off-screen | [ ] |

---

## Part 7: Fallback Behavior (IPython Mode)

### 7.1 Test Without Frontend (Optional)
If frontend bridge is unavailable, tools should fall back to IPython history.

| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Mock frontend failure | Frontend unavailable | [ ] |
| 2 | Call `notebook_get_notebook_cells` | Returns cells from IPython history only | [ ] |
| 3 | Verify `total_cells` is null | Indicates fallback mode | [ ] |
| 4 | Verify note says "Using IPython fallback" | Fallback indicated | [ ] |

---

## Part 8: Integration Scenarios

### 8.1 Complete Workflow: Find and Delete Markdown Cell
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_get_notebook_cells` with `num_cells=20` | Get all cells with types | [ ] |
| 2 | Identify markdown cell position from `cell_id_notebook` | Position noted | [ ] |
| 3 | Call `notebook_move_cursor` with `target="index:N"` | Cursor moves to markdown | [ ] |
| 4 | Call `notebook_delete_cells` with `cell_id_notebooks="[N]"` | Markdown deleted | [ ] |

### 8.2 Complete Workflow: Navigate Notebook Structure
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Call `notebook_get_notebook_cells` to get structure | All cells listed | [ ] |
| 2 | Navigate to first markdown section | `index:0` | [ ] |
| 3 | Navigate to first code cell | `index:1` or `target="1"` | [ ] |
| 4 | Navigate to unexecuted code | `index:4` | [ ] |
| 5 | Navigate back to executed cell | `target="3"` (execution count) | [ ] |

### 8.3 AI Agent Scenario: Clean Up Empty Cells
| # | Step | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Add 3 empty code cells (unexecuted) | Cells exist | [ ] |
| 2 | Use `notebook_get_notebook_cells` to find empty cells | Identify by empty `source` | [ ] |
| 3 | Delete all empty cells using `cell_id_notebooks` | All deleted | [ ] |
| 4 | This scenario was impossible before | Required execution counts | [ ] |

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

### Critical New Features Tested
- [ ] `cell_id_notebooks` parameter in `notebook_get_notebook_cells`
- [ ] `cell_id_notebooks` parameter in `notebook_delete_cells`
- [ ] `index:N` format in `notebook_move_cursor`
- [ ] New field names: `cell_id_notebook`, `cell_execution_number`, `source`
- [ ] Access to markdown cells
- [ ] Access to unexecuted code cells
- [ ] Two-phase retrieval (structure + content)
- [ ] Cache invalidation on delete

### Backward Compatibility Verified
- [ ] `num_cells` parameter still works
- [ ] `cell_execution_numbers` parameter still works
- [ ] Execution count navigation (`target="N"`) still works
- [ ] `above`, `below`, `bottom` navigation still works

---

## Notes

_Space for tester notes:_

---

**Test Completed**: [ ] Yes / [ ] No
**Date Completed**: ________________
**Issues Found**: ________________
