# Test Plan: Simplified `notebook_execute_cell` Output Retrieval

**Date:** January 11, 2026
**Changes:** Simplified `_wait_for_execution()` and `execute_editing_cell()` in `tools.py`
**Branch:** AI_safety

---

## Summary of Changes

The output retrieval logic in `notebook_execute_cell` was simplified:
1. `_wait_for_execution()` now only waits for completion/errors (removed complex output polling)
2. `execute_editing_cell()` now uses `active_cell_bridge.get_active_cell_output()` to fetch output after execution completes
3. This aligns output retrieval with `notebook_get_editing_cell_output` (same shared logic)

---

## Test Categories

### 1. Unit Tests (Automated)

```bash
# Run existing execution wait tests
pytest tests/unit/servers/test_execution_wait.py -v

# Run database tools tests (uses execute_editing_cell)
pytest tests/unit/servers/test_database_tools.py -v

# Run all unit tests
pytest tests/unit/ -v
```

**Expected:** Some tests may fail because they mock `_get_cell_output` which is no longer called by `_wait_for_execution`. These tests need updating.

---

### 2. Integration Tests (Manual - Jupyter Notebook)

#### Setup
```python
%load_ext instrmcp.extensions
%mcp_unsafe
%mcp_start
```

#### Test 2.1: Basic Execution with Output
```python
# Cell content:
print("Hello World")
42 + 8
```
**Expected Result:**
- `status: "completed"`
- `has_output: True`
- `outputs` array contains stream output ("Hello World") and execute_result (50)

#### Test 2.2: Silent Execution (No Output)
```python
# Cell content:
x = 10
y = 20
```
**Expected Result:**
- `status: "completed"`
- `has_output: False`
- No outputs array or empty

#### Test 2.3: Error Handling - Syntax Error
```python
# Cell content:
def broken(
```
**Expected Result:**
- `status: "error"`
- `has_error: True`
- `error_type: "SyntaxError"`
- `error_message` contains syntax error details

#### Test 2.4: Error Handling - Runtime Error
```python
# Cell content:
1 / 0
```
**Expected Result:**
- `status: "error"`
- `has_error: True`
- `error_type: "ZeroDivisionError"`
- `traceback` contains full traceback

#### Test 2.5: Long-Running Cell
```python
# Cell content:
import time
time.sleep(5)
print("Done sleeping")
```
**Expected Result:**
- Waits for execution to complete (~5 seconds)
- `status: "completed"`
- `has_output: True`
- Output contains "Done sleeping"

#### Test 2.6: Timeout Handling
```python
# Cell content (with timeout=2):
import time
time.sleep(10)
```
**Call with:** `notebook_execute_cell(timeout=2)`

**Expected Result:**
- `status: "timeout"`
- `has_error: False`
- `has_output: False`
- `message` mentions timeout

---

### 3. Database Integration Tests (Manual)

#### Test 3.1: Auto-Execute Code Suggestion
```python
# First, ensure database tools are enabled:
%mcp_option database

# Then call:
database_get_dataset_info(id=1, code_suggestion=True)
```

**Expected Result:**
- Code is added to a new cell
- Code is executed
- `code_executed` field contains:
  - `success: True`
  - `cell_output` contains the dataset info

#### Test 3.2: Auto-Execute with Error
```python
# Use a non-existent database or invalid ID
database_get_dataset_info(id=999999, code_suggestion=True)
```

**Expected Result:**
- Code is added
- Execution shows error (dataset not found)
- `code_executed` field contains error details

---

### 4. Edge Case Tests

#### Test 4.1: Multiple Rapid Executions
Execute 3 cells rapidly in succession and verify each returns correct output.

#### Test 4.2: Cell with Display Output
```python
from IPython.display import display, HTML
display(HTML("<b>Bold text</b>"))
```
**Expected:** `outputs` contains display_data with HTML content

#### Test 4.3: Cell with Matplotlib Plot
```python
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [1, 4, 9])
plt.show()
```
**Expected:** `outputs` contains image data

#### Test 4.4: MeasureIt Sweep Detection
```python
# Assuming sweep1d is configured:
sweep1d.start()
```
**Expected:**
- `sweep_detected: True`
- `sweep_names: ["sweep1d"]`
- `suggestion` contains wait instruction

---

### 5. Backward Compatibility Tests

#### Test 5.1: Verify Output Structure
Compare output structure with previous implementation:

| Field | Must Be Present | Notes |
|-------|-----------------|-------|
| `success` | Yes | Signal success |
| `executed` | Yes | Execution attempted |
| `status` | Yes | completed/error/timeout |
| `execution_count` | Yes | Cell number |
| `has_output` | Yes | Output present flag |
| `has_error` | Yes | Error flag |
| `outputs` | When has_output=True | Frontend outputs |
| `output` | Fallback only | From Out cache |
| `error_type` | When has_error=True | Error class name |
| `error_message` | When has_error=True | Error description |
| `traceback` | When has_error=True | Full traceback |

#### Test 5.2: Concise Mode
```python
notebook_execute_cell(detailed=False)
```
Verify concise mode still works via `_to_concise_execute_cell()` in tools_unsafe.py.

---

### 6. Performance Tests

#### Test 6.1: Output Fetch Timing
Measure time between execution completion and output availability.
- **Old implementation:** Grace period + polling (~0.5-1s after completion)
- **New implementation:** Direct fetch (~0.1-0.3s after completion)

#### Test 6.2: No Unnecessary Polling
Verify that during execution wait, no output polling occurs (removed Check 3 & 4).

---

## Known Limitations

1. **Active Cell Output:** Output is fetched from the currently active cell, not by execution count. If cursor moves during execution, output may be incorrect.

2. **Removed Grace Period:** The 0.5s grace period for output propagation was removed. Most outputs should still be captured via `get_active_cell_output`, but very late outputs might be missed.

3. **Dead Code:** `_get_cell_output()` and `_process_frontend_output()` are no longer called by `_wait_for_execution()` but remain in codebase for test compatibility.

---

## Test Execution Checklist

- [ ] Run automated unit tests
- [ ] Fix any failing tests due to removed mocks
- [ ] Run manual integration tests 2.1-2.6
- [ ] Run database integration tests 3.1-3.2
- [ ] Run edge case tests 4.1-4.4
- [ ] Verify backward compatibility (Test 5.1-5.2)
- [ ] Optional: Performance comparison (Test 6.1-6.2)

---

## Rollback Plan

If critical issues are found:
```bash
git checkout instrmcp/servers/jupyter_qcodes/tools.py
```

Or revert specific changes:
```bash
git diff HEAD~1 instrmcp/servers/jupyter_qcodes/tools.py | git apply -R
```
