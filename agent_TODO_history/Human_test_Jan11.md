# Human Test: Database Code Suggestion & Auto-Execute

This document tests the updated `database_get_dataset_info` tool with:
1. Metadata-based column identification in code templates
2. Auto-execute in unsafe/dangerous mode
3. Code suggestion in safe mode

## Prerequisites

```python
%load_ext instrmcp.extensions
%mcp_option database
```

## Test Database

Using: `/Users/caijiaqi/Documents/GitHub/MeasureIt/Databases/Example_database.db`

Run IDs:
- **1**: Sweep0D
- **2**: Sweep1D
- **3**: SimulSweep
- **4-5**: SweepQueue batch
- **6-16**: Sweep2D parent (11 runs)

---

## Part 1: Safe Mode Tests (Code Suggestion)

### Setup
```python
%mcp_safe
%mcp_restart
```

### Test 1.1: Sweep0D Code Suggestion
**Action**: Call `database_get_dataset_info(id=1)`

**Expected**: Response contains `code_suggestion` field with:
- `# Measured: ['test_instrument1_parabola', 'test_instrument0_parabola']`
- Uses `ds.to_pandas_dataframe().reset_index()`
- Plotting code is commented out

**Verify**: Code runs correctly when manually copied to a cell.

---

### Test 1.2: Sweep1D Code Suggestion
**Action**: Call `database_get_dataset_info(id=2)`

**Expected**: Response contains `code_suggestion` field with:
- `# Swept: [...]` comment (may be empty if not in metadata)
- `# Measured: ['test_instrument1_parabola', 'test_instrument0_parabola']`
- Uses `ds.to_pandas_dataframe().reset_index()`

**Verify**: Code runs correctly when manually copied to a cell.

---

### Test 1.3: SimulSweep Code Suggestion
**Action**: Call `database_get_dataset_info(id=3)`

**Expected**: Response contains `code_suggestion` field with:
- `# Swept (simultaneous): ['test_instrument0_x', 'test_instrument1_x']`
- `# Measured: ['test_instrument1_parabola', 'test_instrument0_parabola']`
- Uses `ds.to_pandas_dataframe().reset_index()`

**Verify**: Code runs correctly - no KeyError.

---

### Test 1.4: SweepQueue Code Suggestion
**Action**: Call `database_get_dataset_info(id=4)`

**Expected**: Response contains `code_suggestion` field with:
- Comment about batch containing multiple runs
- `# Swept: [...]` and `# Measured: [...]` from first sweep
- Loads multiple runs into `dfs` dictionary

**Verify**: Code runs correctly when manually copied to a cell.

---

### Test 1.5: Sweep2D Parent Code Suggestion
**Action**: Call `database_get_dataset_info(id=6)`

**Expected**: Response contains `code_suggestion` field with:
- `# Inner (x, fast): test_instrument0_x`
- `# Outer (y, slow): test_instrument0_y`
- `# Measured: ['test_instrument1_parabola', 'test_instrument0_parabola']`
- Combines all 11 runs with `pd.concat()`
- Plotting code is commented out

**Verify**:
1. Code runs correctly
2. Column comments match actual DataFrame columns
3. `df.columns.tolist()` output matches the comments

---

## Part 2: Unsafe Mode Tests (Auto-Execute)

### Setup
```python
%mcp_unsafe
%mcp_restart
```

### Test 2.1: Auto-Execute Sweep0D
**Action**: Call `database_get_dataset_info(id=1)`

**Expected**:
1. A new cell is automatically added below current cell
2. Cell is automatically executed
3. Response contains `code_executed` field (NOT `code_suggestion`) with:
   - `"success": true`
   - `"message": "Code added to notebook cell and executed successfully"`
   - `"cell_content": "..."` (the generated code)
   - `"cell_output": "..."` (output from execution)
   - `"has_error": false`

**Verify**:
1. New cell exists in notebook with the code
2. Cell has been executed (has output)
3. No errors in execution

---

### Test 2.2: Auto-Execute Sweep2D Parent
**Action**: Call `database_get_dataset_info(id=6)`

**Expected**:
1. New cell added with Sweep2D parent loading code
2. Cell executed successfully
3. Response contains `code_executed` with success=true
4. Output shows columns and shape

**Verify**:
1. DataFrame is created with all 11 runs combined
2. Columns are correctly identified in comments
3. Shape is approximately (11 * points_per_line, num_columns)

---

### Test 2.3: Auto-Execute with Detailed Mode
**Action**: Call `database_get_dataset_info(id=2, detailed=True)`

**Expected**:
1. Code auto-executes as before
2. Response includes full dataset info (not concise)
3. `code_executed` field present with execution results

---

### Test 2.4: No Code Suggestion
**Action**: Call `database_get_dataset_info(id=1, code_suggestion=False)`

**Expected**:
1. No cell is added
2. No `code_executed` or `code_suggestion` field in response
3. Only dataset info is returned

---

## Part 3: Dangerous Mode Tests

### Setup
```python
%mcp_dangerous
%mcp_restart
```

### Test 3.1: Auto-Execute Without Consent Dialog
**Action**: Call `database_get_dataset_info(id=1)`

**Expected**:
1. Same behavior as unsafe mode
2. No consent dialog appears (dangerous mode bypasses consent)
3. Code is added and executed automatically

---

## Part 4: Edge Cases

### Test 4.1: Invalid Run ID
**Action**: Call `database_get_dataset_info(id=9999)`

**Expected**: Error response with appropriate message

---

### Test 4.2: Invalid Database Path
**Action**: Call `database_get_dataset_info(id=1, database_path="/nonexistent/path.db")`

**Expected**: Error response with appropriate message

---

### Test 4.3: Execution Timeout (if applicable)
**Action**: Call with a very large dataset that might timeout

**Expected**:
- If timeout: `code_executed.success = false` with timeout message
- Suggestion to check and revise code

---

## Part 5: Token Savings Verification

### Before (Old Workflow)
1. AI calls `database_get_dataset_info` → receives code_suggestion
2. AI reads code_suggestion → decides to add to cell
3. AI calls `notebook_add_cell` with the code
4. AI calls `notebook_execute_cell`
5. AI reads execution output

**Token cost**: ~5 tool calls, code appears 3 times in context

### After (New Workflow - Unsafe Mode)
1. AI calls `database_get_dataset_info` → code auto-executes, receives result

**Token cost**: 1 tool call, code appears 1 time in context

**Savings**: ~80% reduction in tokens for this workflow

---

## Checklist

### Safe Mode
- [ ] Sweep0D code suggestion correct
- [ ] Sweep1D code suggestion correct
- [ ] SimulSweep code suggestion correct (no KeyError)
- [ ] SweepQueue code suggestion correct
- [ ] Sweep2D Parent code suggestion correct
- [ ] Column comments match actual DataFrame columns
- [ ] All plotting code is commented out

### Unsafe/Dangerous Mode
- [ ] Code auto-adds to new cell
- [ ] Code auto-executes
- [ ] `code_executed` field returned (not `code_suggestion`)
- [ ] Success status correct
- [ ] Cell output captured
- [ ] No consent dialog in dangerous mode

### Error Handling
- [ ] Invalid run ID handled gracefully
- [ ] Invalid database path handled gracefully
- [ ] Execution failures reported properly

---

## Notes

- After changing modes, always run `%mcp_restart` for changes to take effect
- The auto-execute feature requires the JupyterLab extension to be active
- If execution fails, the `suggestion` field provides guidance for manual intervention
