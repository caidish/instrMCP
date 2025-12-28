# InstrMCP Bugs to Fix

**Generated from**: human_test_plan.md
**Date**: 2025-12-27
**Status**: Awaiting fixes

---

## Critical Bugs (High Priority)

[Fixed]
### 1. `notebook_delete_cell` - Deletes Multiple Cells Instead of Selected One 
- **Location**: Part 3.5, Step 7
- **Severity**: CRITICAL
- **Issue**: Delete cell will delete recent 2-5 cells instead of the selected one
- **Expected**: Should delete only the currently selected/active cell
- **Note**: `notebook_delete_cells` works fine (by design it only deletes those with `cell_numbers`/executed cells). The current editing cell delete is broken.

[Fixed]
### 2. `notebook_apply_patch` - Applies Multiple Times
- **Location**: Part 3.7, Step 5-6
- **Severity**: CRITICAL
- **Issue**: The tool randomly applies the patch 2-3 times
- **Example**: Setting `old_text`: "y = 2", `new_text`: "y = 200" results in `y = 2000000` instead of `y = 200`
- **Expected**: Patch should apply exactly once

[Fixed]
### 3. `notebook_add_cell` - Content Not Set Properly
- **Location**: Part 3.4, Step 8
- **Severity**: CRITICAL
- **Issue**: Adds the cell but does not set the content properly. New cell is empty instead of having the specified content
- **Expected**: New cell should contain the specified `content` parameter value

[Fixed]
### 4. `notebook_execute_cell` - Missing Output in Concise Mode
- **Location**: Part 3.3, Step 5
- **Severity**: CRITICAL
- **Issue**: No output included when `detailed` is false. For `print()` statements, it gives no output and no input
- **Expected**: Output should always be included regardless of `detailed` setting
- **Note**: Seems like it did not use the `active_cell_bridge` properly

[Fixed]
### 5. `notebook_execute_cell` - Missing Error Info in Concise Mode
- **Location**: Part 3.3, Step 7
- **Severity**: CRITICAL
- **Issue**: When `detailed` is false, error cells return null `error_type` and `error_message`
- **Expected**: Error info should always be included when there is an error, regardless of `detailed` setting

---

## Server & Lifecycle Bugs
[Fixed]
### 6. `%mcp_close` - Hangs with Active Connections
- **Location**: Part 1.4, Step 1
- **Severity**: HIGH
- **Issue**: `%mcp_close` hangs if there is an MCP server connectivity (e.g., Inspector connected)
- **Expected**: Should gracefully close connections and stop server

---

## Tool Response/Behavior Bugs

[Fixed]
### 7. `notebook_server_status` - Missing `enabled_options`
- **Location**: Part 2.1, Step 2
- **Severity**: MEDIUM
- **Issue**: Does not return `enabled_options` field
- **Expected**: Should return: mode, server running status, `enabled_options` list, `registered_tools` list

[Fixed]
### 8. `notebook_list_variables` - Validation Error with "null"
- **Location**: Part 2.3, Step 2
- **Severity**: MEDIUM
- **Issue**: Returns validation error if `type_filter` is "null". Works when it is empty
- **Expected**: Should handle "null" gracefully (treat as no filter)

[Not needed to fix]
### 9. `notebook_get_editing_cell_output` - `detailed` Parameter Ignored
- **Location**: Part 2.6, Step 3
- **Severity**: MEDIUM
- **Issue**: `detailed` does not work as expected. Returns all information regardless of detailed true/false

[Fixed]
### 10. `notebook_get_editing_cell_output` - Stale Error State
- **Location**: Part 2.6, Step 8
- **Severity**: MEDIUM
- **Issue**: After running an error cell, subsequent successful cells (like `x = 1`) still return `has_error: true`
- **Response Example**:
  ```json
  {
    "status": "error",
    "message": "Cell raised an exception",
    "outputs": null,
    "has_output": false,
    "has_error": true
  }
  ```
- **Expected**: Should reflect the actual state of the most recently executed cell
- **Note**: Running a successful output cell again clears this
- **Fix**: Implemented "Frontend-First" approach - trust frontend data over stale `sys.last_*` state

### 11. `notebook_move_cursor` - Success on Non-existent Target
- **Location**: Part 2.8, Step 10
- **Severity**: MEDIUM
- **Issue**: Setting `target`: "999" (non-existent execution count) gives a success response even though the cell does not exist. No cursor movement happens
- **Expected**: Should return an error indicating cell not found

### 12. `notebook_add_cell` - Error Message Not Passed in Concise Mode
- **Location**: Part 3.4, Step 10
- **Severity**: MEDIUM
- **Issue**: When `detailed` is false, error messages are not passed (e.g., invalid `position`: "sideways")
- **Expected**: Error messages should always be included regardless of `detailed` setting

[Not a bug]
### 13. `notebook_apply_patch` - Non-matching Text Error Not Tested
- **Location**: Part 3.7, Step 7
- **Severity**: LOW
- **Issue**: Test with non-matching `old_text` marked as not passing
- **Expected**: Should return error: "text not found"

[Not a bug]
### 14. `notebook_get_editing_cell` - Line Range Not Working
- **Location**: Part 2.5, Step 7
- **Severity**: LOW
- **Issue**: Setting `line_start`: 1, `line_end`: 1 test not passing
- **Expected**: Should return only first line of cell (1-based, inclusive)

---

## Missing Features (Consistency Improvements)

### 15. `measureit_get_status` - No `detailed` Option
- **Location**: Part 5.1
- **Severity**: LOW (Enhancement)
- **Issue**: Should have a `detailed` option like other tools
- **Proposed Behavior**:
  - `detailed: false` → Only active status and sweep names
  - `detailed: true` → Full info (current behavior)

### 16. `measureit_wait_for_sweep` - No `detailed` Option
- **Location**: Part 5.1
- **Severity**: LOW (Enhancement)
- **Issue**: Should have a `detailed` option like other tools
- **Proposed Behavior**:
  - `detailed: false` → Only sweep's state
  - `detailed: true` → Full info (current behavior)

### 17. `measureit_wait_for_all_sweeps` - No `detailed` Option
- **Location**: Part 5.1
- **Severity**: LOW (Enhancement)
- **Issue**: Should have a `detailed` option like other tools
- **Proposed Behavior**:
  - `detailed: false` → Only sweep's state
  - `detailed: true` → Full info (current behavior)

### 18. `database_list_available` - No `detailed` Option
- **Location**: Part 5.2
- **Severity**: LOW (Enhancement)
- **Issue**: Should have a `detailed` option like other tools
- **Proposed Behavior**:
  - `detailed: false` → Only database names and paths
  - `detailed: true` → Full info (current behavior)

---

## Summary

| Priority | Count | Categories |
|----------|-------|------------|
| CRITICAL | 5 | Cell operations, output handling |
| HIGH | 1 | Server lifecycle |
| MEDIUM | 7 | Tool responses, error handling |
| LOW | 3 | Edge cases |
| Enhancement | 4 | Missing `detailed` options |
| **Total** | **20** | |

---

## Fix Order Recommendation

1. **Critical bugs first** - These can cause data loss or incorrect notebook state
2. **Server lifecycle** - User experience impact
3. **Tool response bugs** - Incorrect information returned
4. **Enhancements** - Consistency improvements

---

## Notes

- Frontend Options Panel (Part 6.5) was not fully tested
- Some bugs may be related (e.g., multiple `detailed` parameter issues may share root cause)
