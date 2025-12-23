# MCP Tools Audit Report

**Date**: 2025-12-22
**Auditor**: Claude Code
**Scope**: All MCP tools in `instrmcp/servers/jupyter_qcodes/`
**Status**: Reviewed and corrected based on code verification

---

## Executive Summary

Systematic audit of MCP tools in the jupyter_qcodes server. After verification against actual code:

- **Critical**: ~~1 confirmed issue (error signal handling)~~ ✅ **FIXED** (2025-12-23)
- **High**: 3 confirmed issues (polling, staleness, rate limiting)
- **Medium**: 4 issues (security considerations, assumptions)
- **Low**: Several code quality observations

**Note**: Initial audit contained errors that were corrected after code review. See "Corrections from Initial Audit" section.

---

## 1. QCodes Read-Only Tools (`tools.py`)

### 1.1 `list_instruments()`

| Aspect | Details |
|--------|---------|
| **Function** | Lists all QCoDeS instruments in namespace with hierarchical parameter discovery |
| **Tech Routine** | Iterates namespace → discovers parameters recursively (max_depth=4) → 5s timeout protection |
| **Potential Issues** | |
| ⚠️ Medium | **Over-engineering**: Uses `asyncio.wait_for()` timeout AND depth limits - redundant double protection |
| ⚠️ Medium | **Visited set bug** (Line 273): `visited.discard(obj_id)` after processing allows same object to be visited through different paths → exponential complexity |
| ⚠️ Low | **Static whitelist**: Hardcoded channel names (ch01-ch08) won't discover custom channel patterns |

### 1.2 `instrument_info()`

| Aspect | Details |
|--------|---------|
| **Function** | Gets detailed instrument info with optional cached values |
| **Tech Routine** | Gets instrument → calls snapshot(update=False) → discovers parameters → adds cached values |
| **Potential Issues** | |
| ⚠️ Medium | **Snapshot staleness** (Line 397): Calls `snapshot(update=False)` but then adds cached values - mismatch between old snapshot and potentially fresh cache |
| ⚠️ Low | **Redundant timeout**: Same over-engineering as `list_instruments()` |

### 1.3 `get_parameter_values()`

| Aspect | Details |
|--------|---------|
| **Function** | Get parameter values with caching and rate limiting |
| **Tech Routine** | Check cache → check rate limit → fetch fresh → update cache → return |
| **Potential Issues** | |
| 🔴 High | **Silent stale fallback** (Lines 524-533): If fresh read fails, silently returns stale cache with only `"error"` field. Client may not realize data is stale |
| ⚠️ Medium | **Rate limiter bypass** (Line 490): Only checks rate limit if cached data exists. First access bypasses rate limiting entirely |
| ⚠️ Medium | **Inconsistent error handling**: Exception path returns cached data as if successful but with error field |

### 1.4 `_get_parameter()`

| Aspect | Details |
|--------|---------|
| **Function** | Gets parameter object from instrument, supporting hierarchical paths |
| **Tech Routine** | Split path by dots → navigate submodules/channels → lookup in parameters dict |
| **Potential Issues** | |
| ⚠️ Low | **Inefficient attribute scanning** (Lines 146-153): Uses `dir()` to find attributes - slow and triggers property evaluation |
| ⚠️ Low | **Missing validation** (Line 137): Direct `getattr()` doesn't check if result has `parameters` attribute |

### 1.5 `_discover_parameters_recursive()`

| Aspect | Details |
|--------|---------|
| **Function** | Recursively discovers all parameters in object hierarchy |
| **Tech Routine** | Track visited IDs → check depth limit → explore submodules → explore whitelisted channels |
| **Potential Issues** | |
| 🔴 High | **Visited set logic bug** (Line 273): `visited.discard(obj_id)` defeats cycle detection - same object can be visited multiple times through different paths |
| ⚠️ Medium | **Static whitelist** (Lines 222-245): Only predefined channel names, won't find custom submodules |
| ⚠️ Low | **Silent exception suppression** (Line 266): Continues if attribute access fails, could hide problems |

### 1.6 `list_variables()`

| Aspect | Details |
|--------|---------|
| **Function** | List variables in Jupyter namespace |
| **Tech Routine** | Iterate namespace → filter by type → return sorted list with repr |
| **Potential Issues** | |
| ⚠️ Medium | **Dangerous repr() call** (Line 635): Calling `repr()` on arbitrary objects could hang or execute code |
| ⚠️ Low | **Inconsistent truncation**: 100 chars here vs 500 in `get_variable_info()` |

### 1.7 `get_variable_info()`

| Aspect | Details |
|--------|---------|
| **Function** | Get detailed info about a variable |
| **Tech Routine** | Get from namespace → call dir() → check if QCoDeS instrument → return metadata |
| **Potential Issues** | |
| ⚠️ Medium | **Expensive dir() call** (Line 660): `dir()` on arbitrary objects is slow, may trigger code execution |
| ⚠️ Low | **No exception handling for dir()**: Could fail for exotic objects |

### 1.8 `get_editing_cell()`

| Aspect | Details |
|--------|---------|
| **Function** | Get currently editing cell content from JupyterLab frontend |
| **Tech Routine** | Request fresh snapshot from bridge if needed → slice lines based on parameters |
| **Potential Issues** | |
| ⚠️ Medium | **Race condition with frontend** (Lines 710-720): If frontend doesn't respond within timeout, returns old snapshot without indicating staleness |
| ⚠️ Low | **No validation of fresh_ms**: Could be negative or extremely large |

### 1.9 `execute_editing_cell()` ⭐ CRITICAL

| Aspect | Details |
|--------|---------|
| **Function** | Execute active cell and wait for output |
| **Tech Routine** | Capture initial count → get bridge snapshot → send execute request → poll for completion (6 checks) → detect sweeps |
| **Potential Issues** | |
| 🔴 Critical | **Stale bridge snapshot** (Line 1053): Bridge snapshot captured AFTER initial_count (Line 1051). Race condition: cell could execute before snapshot captured |
| 🔴 Critical | **Fragile execution detection**: Uses 6 different signals (error, execution_result, outputs, Out[], count advance, grace period) with unclear priority |
| 🔴 High | **IPython In[] assumption** (Lines 926-928): Assumes `In[target_count]` exists and is non-empty - fails if cell deleted or history cleared |
| ⚠️ Medium | **Arbitrary grace period** (Line 904): 200ms grace period is hardcoded heuristic, could miss slow outputs |

### 1.10 `_wait_for_execution()` ⭐ CRITICAL

| Aspect | Details |
|--------|---------|
| **Function** | Wait for cell execution to complete |
| **Tech Routine** | Poll execution_count → check sys.last_* → check Out[] → check frontend outputs → check execution count advance |
| **Potential Issues** | |
| 🔴 Critical | **Identity comparison fragility** (Line 953): Uses `is not` to detect completion, assumes execution_result object is replaced. Could fail if object reused |
| 🔴 High | **Multiple completion signals**: 6 different checks with unclear priority - which one wins? |
| ⚠️ Medium | **Frontend output request on every loop** (Line 960): Repeatedly requests outputs even if previous request pending |
| ⚠️ Medium | **Grace period logic bug** (Lines 1012-1024): If execution completed but grace period hasn't elapsed, returns "no output" - wrong |
| ⚠️ Medium | **Timeout doesn't include grace period**: 30s timeout + 0.2s grace = 30.2s actual |

### 1.11 `wait_for_all_sweeps()` / `wait_for_sweep()`

| Aspect | Details |
|--------|---------|
| **Function** | Wait for MeasureIt sweeps to complete |
| **Tech Routine** | Poll `get_measureit_status()` every 1 second until done |
| **Potential Issues** | |
| 🔴 High | **No timeout**: Could wait forever if sweep never completes |
| ⚠️ Medium | **Hardcoded 1s delay** (Line 31): Inefficient, could use exponential backoff |
| ⚠️ Medium | **Race condition** (Lines 1411-1413): Gets current sweeps, but state may change before check completes |

### 1.12 `get_measureit_status()`

| Aspect | Details |
|--------|---------|
| **Function** | Check if MeasureIt sweeps are running |
| **Tech Routine** | Scan namespace for BaseSweep instances → read progressState |
| **Potential Issues** | |
| ⚠️ Medium | **Expensive namespace scan**: Iterates all variables every call |
| ⚠️ Medium | **API assumption** (Lines 1507-1514): Assumes `progressState.state.value` exists without validation |

---

## 2. Unsafe Tool Registrar (`tools_unsafe.py`)

### 2.1 `update_editing_cell()` / `execute_editing_cell()` / etc.

| Aspect | Details |
|--------|---------|
| **Function** | MCP tool wrappers that add consent dialogs |
| **Tech Routine** | Get cell info → request consent → call underlying tool → apply concise mode |
| **Potential Issues** | |
| ⚠️ Medium | **Stale consent data** (Lines 145-146): Cell info captured before consent, but user might edit while viewing dialog |
| ⚠️ Medium | **Concise mode hides errors** (Line 201): Strips error details, could confuse clients |
| ⚠️ Low | **Timing measurement wrong** (Line 316): Measures until concise conversion, not actual execution |

---

## 3. QCodes Tool Registrar (`registrars/qcodes_tools.py`)

### 3.1 `instrument_info()` / `get_parameter_values()` tools

| Aspect | Details |
|--------|---------|
| **Function** | MCP tool wrappers with concise mode filtering |
| **Tech Routine** | Call underlying tool → parse result → apply concise filter |
| **Potential Issues** | |
| ⚠️ Medium | **JSON parsing without fallback** (Line 183): Invalid JSON causes complete failure |
| ⚠️ Low | **Concise mode drops timestamps** (Lines 194-195): Loses timing information |

---

## 4. Notebook Tool Registrar (`registrars/notebook_tools.py`)

### 4.1 `get_editing_cell_output()`

| Aspect | Details |
|--------|---------|
| **Function** | Get output of last executed cell |
| **Tech Routine** | Use IPython In/Out caches → find last cell → return output |
| **Potential Issues** | |
| 🔴 High | **In[] list assumption** (Line 359): Assumes In exists and is a list |
| ⚠️ Medium | **Single error tracking** (Line 441): Only tracks most recent error - can't know which cell raised it |
| ⚠️ Medium | **Two output sources** (Lines 390-425): Checks frontend outputs AND Out[] - precedence unclear |

### 4.2 `get_notebook_cells()`

| Aspect | Details |
|--------|---------|
| **Function** | Get recent notebook cells with outputs |
| **Tech Routine** | Use IPython In/Out → optional history_manager fallback |
| **Potential Issues** | |
| 🔴 High | **Same In[] assumptions** as above |
| ⚠️ Medium | **Error attribution problem** (Lines 559-564): Assumes latest error from latest cell, could be from earlier |
| ⚠️ Medium | **Inconsistent output detection**: Different code paths check different sources |

### 4.3 `server_status()`

| Aspect | Details |
|--------|---------|
| **Function** | Get server status and tool list |
| **Tech Routine** | Check mcp._tools attribute → return tool names |
| **Potential Issues** | |
| ⚠️ Low | **Private attribute access** (Line 763): Uses `_tools` (private), not public API |
| ⚠️ Low | **Hardcoded limit** (Line 778): Silently truncates to 20 tools |

---

## 5. Database Tool Registrar (`registrars/database_tools.py`)

### 5.1 All database tools

| Aspect | Details |
|--------|---------|
| **Function** | Query QCodes databases |
| **Tech Routine** | Call database integration module → parse JSON response |
| **Potential Issues** | |
| ⚠️ Medium | **JSON parsing without try/catch** (Lines 130, 176): Database module returns JSON string, parsing could fail |
| ⚠️ Medium | **Code generation fragility** (Lines 58-91): Generated Python code could be invalid if parameter names contain special characters |
| ⚠️ Low | **No database_path validation**: Invalid paths produce unclear errors |

---

## 6. Dynamic Tool Registrar (`dynamic_registrar.py`) ⭐ SECURITY CRITICAL

### 6.1 `dynamic_register_tool()`

| Aspect | Details |
|--------|---------|
| **Function** | Register new dynamic tool at runtime |
| **Tech Routine** | Parse JSON spec → validate → request consent → register with FastMCP and registry |
| **Potential Issues** | |
| 🔴 Critical | **LLM JSON correction is risky** (Lines 401-470): Auto-corrects malformed JSON via LLM - LLM could inject malicious code |
| 🔴 Critical | **No source code sandboxing**: Dynamic tools execute arbitrary Python in user's namespace with no resource limits |
| 🔴 High | **Circular registration** (Lines 640-645): FastMCP registered before registry. If registry fails, FastMCP has invalid tool |
| ⚠️ Medium | **Consent leaks source code** (Lines 237-243): Full source sent to consent dialog, could be huge |

### 6.2 `dynamic_update_tool()`

| Aspect | Details |
|--------|---------|
| **Function** | Update existing dynamic tool |
| **Tech Routine** | Get existing spec → merge with new fields → unregister old → register new |
| **Potential Issues** | |
| 🔴 High | **Unregister-before-test** (Lines 844-850): Unregisters old tool, then tries to register new. If registration fails, tool is gone |
| ⚠️ Medium | **No version conflict detection**: Concurrent updates could create inconsistent state |
| ⚠️ Medium | **No JSON auto-correction**: Unlike register_tool, doesn't attempt to fix malformed JSON |

### 6.3 `_register_tool_with_fastmcp()`

| Aspect | Details |
|--------|---------|
| **Function** | Register tool with FastMCP |
| **Tech Routine** | Compile spec → create dynamic wrapper → register |
| **Potential Issues** | |
| ⚠️ Medium | **Incomplete type mapping** (Lines 191-197): Only handles basic JSON types, not arrays of objects or nested structures |
| ⚠️ Medium | **No resource limits**: Dynamic tools can consume unlimited memory/CPU |
| ⚠️ Low | **Closure memory leak** (Line 274): Wrapper captures spec reference, prevents garbage collection |

---

## 7. Active Cell Bridge (`active_cell_bridge.py`)

### 7.1 `get_active_cell()`

| Aspect | Details |
|--------|---------|
| **Function** | Get most recent active cell snapshot |
| **Tech Routine** | Check cache freshness → request fresh if needed → wait for response |
| **Potential Issues** | |
| ⚠️ Medium | **Hardcoded timeout** (Line 139): 0.3s default, not configurable per-call |
| ⚠️ Medium | **Race condition** (Lines 154-186): Between cache check and fresh request, frontend might send update |
| ⚠️ Low | **Hardcoded poll interval** (Line 176): 50ms polling is inefficient |

### 7.2 `execute_active_cell()` / `update_active_cell()` / etc.

| Aspect | Details |
|--------|---------|
| **Function** | Send cell modification requests to frontend |
| **Tech Routine** | Generate UUID → send to all active comms → return immediately |
| **Potential Issues** | |
| 🔴 High | **Fire-and-forget**: Returns success before frontend confirms receipt |
| ⚠️ Medium | **Request ID not tracked**: No correlation between request and response |
| ⚠️ Medium | **Duplicate requests**: Multiple JupyterLab windows receive duplicate commands |

---

## 8. Cache Module (`cache.py`)

### 8.1 `ReadCache`

| Aspect | Details |
|--------|---------|
| **Function** | Thread-safe cache for parameter values |
| **Tech Routine** | Dict with asyncio lock |
| **Potential Issues** | |
| ⚠️ Medium | **No cache invalidation**: Cache never expires |
| ⚠️ Medium | **No size limits**: Could grow unbounded |

### 8.2 `RateLimiter`

| Aspect | Details |
|--------|---------|
| **Function** | Rate limit instrument access |
| **Tech Routine** | Track last access time → enforce min_interval |
| **Potential Issues** | |
| ⚠️ Low | **Global rate limit**: Affects all clients sharing server |
| ⚠️ Low | **Clock skew vulnerability**: Backwards clock adjustment bypasses limits |

---

## Critical Issues Summary (Verified)

| Priority | Issue | Location | Impact |
|----------|-------|----------|--------|
| ✅ ~~Critical~~ | ~~**Error signals ignored in output**~~ | `notebook_tools.py:397-442` | **FIXED** (2025-12-23): Now checks `output_type="error"` and `type="error"` in outputs array |
| 🔴 High | **Grace period spams frontend** | `tools.py:900-1020` | Polls `get_cell_outputs` every 100ms even after completion detected; fixed short grace period misses late outputs |
| 🔴 High | **Stale snapshot not marked** | `active_cell_bridge.py:60-140` | Returns old snapshot when no active comms, without staleness indicator → callers mistake stale for live |
| 🔴 High | **Rate limit bypass on first read** | `tools.py:460-540` | Rate limiting only applies when cache exists; first read always goes live, bypassing hardware minimum intervals |
| ⚠️ Medium | LLM JSON correction could inject code | `dynamic_registrar.py` | Security (requires malicious LLM) |
| ⚠️ Medium | No sandboxing for dynamic tools | `dynamic_registrar.py` | Security (user-controlled) |
| ⚠️ Medium | IPython In[] assumptions | Multiple files | Functional |
| ⚠️ Medium | Fire-and-forget bridge commands | `active_cell_bridge.py` | Reliability |

### Corrections from Initial Audit

| Original Claim | Correction |
|----------------|------------|
| `dynamic_update_tool` has no rollback | ❌ **Wrong**: Code at lines 834-868 DOES roll back by re-registering old spec if new registration fails |
| "Silent stale fallback" in `get_parameter_values` | ❌ **Overstated**: Error paths set `stale: True`, `source: "cache"`, and include error message - not silent |
| `visited.discard()` is a cycle bug | ❌ **Overstated**: Intentional design to prevent deep cycles while allowing revisit via other paths. Trade-off, not bug. May repeat work but not infinite loop |

---

## Recommendations

### Immediate Actions (Critical)
1. ~~**Fix error detection in get_editing_cell_output**: Check `outputs` array for `type: "error"` and set `has_error=True` accordingly~~ ✅ **FIXED** (2025-12-23)

### Short-term Improvements (High)
2. **Stop polling after completion**: In `_wait_for_execution`, don't call `get_cell_outputs` during grace period
3. **Mark stale snapshots**: In `get_active_cell`, add `"stale": True` flag when returning old snapshot due to no active comms
4. **Apply rate limit on first read**: Check rate limit BEFORE checking cache, not only when cache exists

### Consider (Medium)
5. **Add sandboxing for dynamic tools**: Restrict namespace access for dynamically registered tools (user-controlled risk)
6. **Simplify execution detection**: Current multi-signal approach is complex - consider single reliable signal
7. **Unify output sources**: Decide on single source of truth (frontend outputs vs IPython Out[])

### Long-term (Low)
8. **Add cache TTL and size limits**: Prevent unbounded cache growth
9. **Add frontend confirmation**: Bridge commands should wait for ACK before returning success

---

## Audit Notes

- **Last Updated**: 2025-12-23
- **Verification Status**: Reviewed and corrected after code verification
- **Corrections Made**:
  - Removed false claim about `dynamic_update_tool` lacking rollback (it does roll back)
  - Downgraded "silent stale fallback" - actually includes stale/source/error fields
  - Downgraded `visited.discard()` - intentional design trade-off, not a bug
  - Fixed inflated issue counts in executive summary
- **Fixes Applied**:
  - 2025-12-23: Fixed critical "Error signals ignored in output" bug in `notebook_tools.py:397-442` - now properly detects `output_type="error"` and `type="error"` in frontend outputs and sets `has_error=True` with error details
