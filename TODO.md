# Dynamic MCP Tool Creation - Implementation TODO

## 📋 Project Overview

Enable LLMs to create dynamic MCP tools at runtime with comprehensive security controls through consent UI, capability-based permissions, and sandboxed execution.

**Status**: Phase 1 Complete ✅
**Target Version**: 2.0.0
**Estimated Timeline**: one week
**Last Updated**: 2025-10-01

### ✅ Phase 1 Summary (Completed 2025-10-01)

Phase 1 implementation is complete with all core infrastructure in place:

**Files Created:**
- `instrmcp/tools/dynamic/tool_spec.py` - Tool specification system with validation
- `instrmcp/tools/dynamic/tool_registry.py` - Registry with file-based persistence
- `instrmcp/servers/jupyter_qcodes/security/audit.py` - Simple audit logging
- `instrmcp/servers/jupyter_qcodes/dynamic_registrar.py` - 6 meta-tools for LLM interaction
- `tests/unit/servers/test_dynamic_tools.py` - 28 unit tests (all passing)

**Files Modified:**
- `instrmcp/servers/jupyter_qcodes/mcp_server.py` - Integrated DynamicToolRegistrar (unsafe mode)
- `instrmcp/tools/stdio_proxy.py` - Added proxies for 6 meta-tools
- `tests/unit/test_stdio_proxy.py` - Updated tool count (19→25)

**Meta-tools Available:**
1. `dynamic_register_tool` - Register new tools with validation
2. `dynamic_update_tool` - Update existing tools
3. `dynamic_revoke_tool` - Delete tools
4. `dynamic_list_tools` - List tools with filtering
5. `dynamic_inspect_tool` - Inspect full tool specs
6. `dynamic_registry_stats` - Get registry statistics

**Test Results:** 318 tests passing (28 new + 290 existing)

**Human Testing (Phase 1 COMPLETED✅-caidish):**
1. Start JupyterLab with MCP server in unsafe mode: `instrmcp jupyter --unsafe`
2. Open MCP Inspector to verify 6 new meta-tools are available:
   - `dynamic_register_tool`
   - `dynamic_update_tool`
   - `dynamic_revoke_tool`
   - `dynamic_list_tools`
   - `dynamic_inspect_tool`
   - `dynamic_registry_stats`
3. Test `dynamic_list_tools` - should return empty list initially
4. Test `dynamic_registry_stats` - should show 0 tools
5. Verify registry directory created: `ls ~/.instrmcp/registry/`
6. Verify audit log created: `ls ~/.instrmcp/audit/tool_audit.log`

**Next:** Phase 2 will add consent UI and dynamic tool execution.

---

## 🎯 Implementation Phases

### Phase 1: Core Infrastructure ✅ COMPLETE
- [x] Design tool spec JSON schema
  - [x] Define required fields (name, version, description)
  - [x] Define capability strings taxonomy
  - [x] Define parameter schema format
- [x] Create `instrmcp/tools/dynamic/tool_spec.py`
  - [x] ToolSpec and ToolParameter dataclasses with validation
  - [x] JSON schema validator
  - [x] create_tool_spec() helper function
  - [x] Comprehensive validation (name, version, description, capabilities, parameters, source code syntax)
- [x] Implement registry storage at `~/.instrmcp/registry/`
  - [x] Create directory structure on first run
  - [x] Simple JSON file storage (one file per tool)
  - [x] In-memory cache with disk persistence
- [x] Create `instrmcp/servers/jupyter_qcodes/dynamic_registrar.py`
  - [x] DynamicToolRegistrar class
  - [x] Registry persistence layer (ToolRegistry)
  - [x] Tool loading on server start
  - [x] 6 meta-tools: register, update, revoke, list, inspect, registry_stats
- [x] Create simple logging in `instrmcp/servers/jupyter_qcodes/security/audit.py`
  - [x] Basic logging to `~/.instrmcp/audit/tool_audit.log`
  - [x] Log: registrations, updates, revocations (not every execution)
  - [x] JSON-formatted log entries with timestamps
- [x] Integration
  - [x] Integrated with mcp_server.py (unsafe mode only)
  - [x] Added stdio_proxy.py proxies for all 6 meta-tools
- [x] Unit tests (28 tests, all passing)
  - [x] ToolParameter tests
  - [x] ToolSpec tests
  - [x] Validation tests
  - [x] ToolRegistry tests (register, update, revoke, list, filtering, persistence)
  - [x] AuditLogger tests

#### Human Testing Checklist (Phase 1,done):
**Setup:**
1. Start Jupyter with MCP server: `instrmcp jupyter --unsafe --port 3000`
2. Open MCP Inspector in browser or use Claude Desktop
3. Verify 25 tools available (19 original + 6 dynamic meta-tools)

**Test Meta-Tools:**
1. **Test `dynamic_list_tools`**:
   - Call with no parameters → should return `{"status": "success", "count": 0, "tools": []}`

2. **Test `dynamic_registry_stats`**:
   - Call with no parameters → should return stats with `total_tools: 0`

3. **Test `dynamic_register_tool`** (create a simple tool):

   **Minimal version (for zero-argument functions):**
   ```
   name: "get_timestamp"
   source_code: "import time\n\ndef get_timestamp():\n    return time.time()"
   ```
   This works because the function takes no arguments.

   **For functions with arguments (PARAMETERS REQUIRED):**
   ```
   name: "test_add"
   source_code: "def test_add(a, b):\n    return a + b"
   parameters: [
     {"name": "a", "type": "number", "description": "First number", "required": true},
     {"name": "b", "type": "number", "description": "Second number", "required": true}
   ]
   ```
   **Important:** If your function has arguments, you MUST specify the parameters, otherwise FastMCP will register it as a zero-argument function and it won't work.

   **Full version (all optional fields):**
   ```
   name: "test_add"
   source_code: "def test_add(a, b):\n    return a + b"
   parameters: [
     {"name": "a", "type": "number", "description": "First number", "required": true},
     {"name": "b", "type": "number", "description": "Second number", "required": true}
   ]
   version: "1.0.0"
   description: "Add two numbers together for testing"
   author: "test_user"
   capabilities: ["cap:python.builtin"]
   returns: {"type": "number", "description": "Sum of a and b"}
   ```

   **Note:** When using MCP Inspector, JSON fields (capabilities, parameters, returns) should be entered as JSON objects/arrays, NOT as quoted strings.

   - Should return: `{"status": "success", "message": "Tool 'test_add' registered successfully", ...}`

4. **Test `dynamic_list_tools` again**:
   - Should now show 1 tool

5. **Test `dynamic_inspect_tool`**:
   - Call with `name: "test_add"`
   - Should return full tool specification

6. **Test `dynamic_update_tool`**:
   - Update version to "1.1.0" and change description
   - Should succeed

7. **Test `dynamic_revoke_tool`**:
   - Call with `name: "test_add"`
   - Should return success
   - Verify tool removed with `dynamic_list_tools`

**Verify File System:**
1. Check registry: `ls ~/.instrmcp/registry/` → should show tool JSON files during registration
2. Check audit log: `tail ~/.instrmcp/audit/tool_audit.log` → should show JSON log entries
3. Verify tool persistence: Restart server and check if tools are reloaded

### Phase 2: Consent UI and Dynamic Execution

#### Backend: Tool Execution (COMPLETED ✅)
- [x] Create `instrmcp/servers/jupyter_qcodes/dynamic_runtime.py`
  - [x] DynamicToolRuntime class
  - [x] Execute tool source code directly in Jupyter kernel context
  - [x] Basic exception handling
  - [x] Tool compilation and execution methods
  - [x] Tool unregistration support
- [x] Update `dynamic_registrar.py` for dynamic tool execution
  - [x] Register tools with FastMCP on creation
  - [x] Re-register tools on server start from registry
  - [x] Unregister tools from FastMCP on revoke (using `mcp.remove_tool()` since v2.9.1)
  - [x] Integrate DynamicToolRuntime for execution
  - [x] Fix registration order: FastMCP before registry (prevents faulty tools in registry)
  - [x] Add rollback logic for failed updates
- [x] Tests for dynamic runtime (11 tests, all passing)
  - [x] Test tool compilation
  - [x] Test tool execution with various inputs
  - [x] Test namespace access
  - [x] Test error handling
- [x] Integration tests for dynamic registrar (8 tests, all passing)
  - [x] Test `mcp.remove_tool()` is called on tool revocation
  - [x] Test exception handling when `remove_tool()` fails
  - [x] Test `remove_tool()` is called during tool updates
  - [x] Test FastMCP registration happens before registry storage
  - [x] Test registry not updated when compilation fails
  - [x] Test update rollback on registration failure
  - [x] Test tool visibility (only valid tools in list)
  - [x] Test revoked tools removed from runtime

#### Human Testing Checklist (Phase 2 - Backend Execution, COMPLETED✅-caidish):
**Setup:**
1. Start Jupyter with MCP server: `instrmcp jupyter --unsafe --port 3000`
2. Open JupyterLab and create a notebook with some variables:
   ```python
   import numpy as np
   test_array = np.array([1, 2, 3, 4, 5])
   multiplier = 10
   ```

**Test Dynamic Tool Execution:**
1. **Register a tool that uses NumPy**:
   ```json
   name: "multiply_by_two"
   version: "1.0.0"
   description: "Multiply array by two using NumPy"
   author: "test_user"
   capabilities: '["cap:python.numpy"]'
   parameters: '[{"name": "arr", "type": "array", "description": "Input array", "required": true}]'
   returns: '{"type": "array", "description": "Multiplied array"}'
   source_code: "import numpy as np\n\ndef multiply_by_two(arr):\n    return (np.array(arr) * 2).tolist()"
   ```
   - Should register successfully AND be immediately callable

2. **Execute the new tool**:
   - Use MCP Inspector to call `multiply_by_two` with `arr: [1, 2, 3]`
   - Should return: `{"status": "success", "result": [2, 4, 6]}`

3. **Register tool that accesses notebook namespace**:
   ```json
   name: "use_notebook_var"
   version: "1.0.0"
   description: "Use variable from notebook namespace"
   author: "test_user"
   capabilities: '["cap:notebook.read"]'
   parameters: '[{"name": "value", "type": "number", "description": "Input value", "required": true}]'
   returns: '{"type": "number", "description": "Result"}'
   source_code: "def use_notebook_var(value):\n    return value * multiplier"
   ```
   - Execute with `value: 5` → should return `{"status": "success", "result": 50}`

4. **Test tool persistence**:
   - Restart MCP server
   - Verify registered tools are automatically reloaded
   - Call `multiply_by_two` again → should still work

5. **Test tool revocation**:
   - Revoke `multiply_by_two` using `dynamic_revoke_tool`
   - Try to call the tool → should fail (not available)
   - Verify it's removed from tool list

6. **Test tool update**:
   - Register a tool, then update it to version 2.0.0 with modified code
   - Verify the updated version executes with new behavior
   - Old compiled version should be replaced

#### Backend: Consent Integration ✅ COMPLETE
- [x] Create `ConsentManager` class in `instrmcp/servers/jupyter_qcodes/security/consent.py`
  - [x] Implement `request_consent()` method with comm channel integration
  - [x] Implement "always allow" permission storage in `~/.instrmcp/consents/always_allow.json`
  - [x] Implement bypass mode via `INSTRMCP_CONSENT_BYPASS=1` environment variable
  - [x] Add timeout handling (5 minutes)
- [x] Integrate consent into `dynamic_registrar.py`
  - [x] Send consent request before registration via comm channel `mcp:capcall`
  - [x] Wait for consent response (timeout: 5 min)
  - [x] Check "always allow" permissions before showing consent UI
  - [x] On approval: complete registration
  - [x] On decline: cleanup and return error
  - [x] Store "always allow" decisions automatically
- [x] Add consent integration to `dynamic_update_tool`
- [x] Testing (26 tests, all passing)
  - [x] Test always_allow storage and persistence
  - [x] Test bypass mode
  - [x] Test consent request workflow (approval, decline, timeout)
  - [x] Test edge cases and error handling
- [x] Update documentation (CLAUDE.md)

#### Frontend: Consent UI (JupyterLab Extension) ✅ COMPLETE
- [x] Create comm channel `mcp:capcall` in TypeScript extension
  - [x] Update `instrmcp/extensions/jupyterlab/src/index.ts`
  - [x] Add comm handler for `mcp:capcall` messages
  - [x] Message types: `consent_request`, `consent_response`
- [x] Build consent dialog using JupyterLab Dialog API
  - [x] Display tool name, description, author, version
  - [x] Display capabilities list
  - [x] Monospace source code viewer with scrolling (300px max-height)
  - [x] Action buttons: [Decline], [Allow], [Always Allow]
- [x] Implement consent workflow logic
  - [x] Handle consent_request messages from backend
  - [x] Show consent dialog with tool details
  - [x] Send consent_response back to backend with approved/always_allow flags
  - [x] Three-button system (Decline/Allow/Always Allow)
- [x] Build extension
  - [x] Add @jupyterlab/apputils dependency
  - [x] Add @lumino/widgets dependency
  - [x] Build extension: `jlpm run build`
  - [x] Reinstall package: `pip install -e . --force-reinstall --no-deps`

**Implementation Notes:**
- Used JupyterLab's `showDialog` API instead of custom React components (simpler, better integration)
- Source code displayed in styled `<pre>` tag with scrolling
- Consent comm channel (`mcp:capcall`) initialized alongside active cell comm channel
- Both registration and update operations trigger consent dialog
- **Requires human testing** - automated UI testing is complex for JupyterLab extensions

#### Human Testing Checklist (Phase 2 - Consent UI):
**REQUIRES HUMAN TESTING - This is a critical test-heavy phase**

**Setup:**
1. Start Jupyter with MCP server:
   ```bash
   instrmcp jupyter --unsafe --port 3000
   ```
2. Open JupyterLab in browser: `http://localhost:8888`
3. Load the MCP extension in a notebook cell:
   ```python
   %load_ext instrmcp.servers.jupyter_qcodes.jupyter_mcp_extension
   %mcp_start
   ```
4. Open MCP Inspector to test tool registration

**Test 1: Basic Consent Dialog (Register)**
1. In MCP Inspector, call `dynamic_register_tool` with:
   ```json
   {
     "name": "test_multiply",
     "version": "1.0.0",
     "description": "Multiply a number by two",
     "author": "test_user",
     "capabilities": ["cap:python"],
     "parameters": [{"name": "x", "type": "number", "description": "Input number", "required": true}],
     "returns": {"type": "number", "description": "Result"},
     "source_code": "def test_multiply(x):\n    return x * 2"
   }
   ```
2. **✅ VERIFY**: Consent dialog appears in JupyterLab
3. **✅ VERIFY**: Dialog shows:
   - Operation: register
   - Tool: test_multiply
   - Author: test_user
   - Version: 1.0.0
   - Description: "Multiply a number by two"
   - Capabilities: cap:python
   - Source code in monospace with scroll
4. **✅ VERIFY**: Three buttons: "Decline", "Allow", "Always Allow"
5. Click "Allow"
6. **✅ VERIFY**: Tool registers successfully (response: `{"status": "success", ...}`)
7. **✅ VERIFY**: Tool is callable via `test_multiply` with `x: 5` → returns 10

**Test 2: Always Allow**
1. Register another tool with same author:
   ```json
   {
     "name": "test_add",
     "author": "test_user",
     "source_code": "def test_add(x, y):\n    return x + y"
   }
   ```
2. Click "Always Allow" in consent dialog
3. **✅ VERIFY**: Tool registers successfully
4. Check always_allow file:
   ```bash
   cat ~/.instrmcp/consents/always_allow.json
   ```
5. **✅ VERIFY**: Contains `{"test_user": ["register"]}`
6. Register a third tool with author "test_user"
7. **✅ VERIFY**: NO dialog appears (auto-approved)
8. **✅ VERIFY**: Tool registers successfully

**Test 3: Decline**
1. Register a tool with new author "another_user"
2. Click "Decline" in consent dialog
3. **✅ VERIFY**: Registration fails with error message
4. Call `dynamic_list_tools`
5. **✅ VERIFY**: Tool is NOT in the list

**Test 4: Tool Update Consent**
1. Update existing tool `test_multiply` to version 2.0.0 via `dynamic_update_tool`
2. **✅ VERIFY**: Consent dialog appears
3. **✅ VERIFY**: Dialog shows operation="update" and old_version in details
4. Click "Allow"
5. **✅ VERIFY**: Tool updates successfully

**Test 5: Bypass Mode (Testing)**
1. Stop Jupyter server
2. Start with bypass mode:
   ```bash
   export INSTRMCP_CONSENT_BYPASS=1
   instrmcp jupyter --unsafe --port 3000
   ```
3. Register a tool with new author
4. **✅ VERIFY**: NO dialog appears
5. **✅ VERIFY**: Tool registers automatically
6. Check logs: Should see "Consent bypassed" message

**Test 6: Console Logging**
1. Open browser DevTools Console
2. Register a tool
3. **✅ VERIFY**: Console shows:
   - "MCP Consent: Comm channel opened successfully"
   - "MCP Consent: Received consent request for register of tool 'xxx' by 'yyy'"
   - "MCP Consent: Sent response - approved: true, always_allow: false"

**Test 7: Error Handling**
1. Close JupyterLab tab while consent dialog is open
2. **✅ VERIFY**: Backend times out after 5 minutes
3. **✅ VERIFY**: Tool registration fails with timeout message

**Test 8: No IPython/Comm Available**
1. In Python outside Jupyter:
   ```python
   from instrmcp.servers.jupyter_qcodes.security.consent import ConsentManager
   import asyncio
   manager = ConsentManager(ipython=None)
   result = asyncio.run(manager.request_consent("register", "test", "author", {}))
   print(result)  # Should show: {"approved": False, "reason": "No IPython instance..."}
   ```

**Post-Testing Cleanup:**
```bash
# Clear always_allow permissions
rm -f ~/.instrmcp/consents/always_allow.json

# Unset bypass mode
unset INSTRMCP_CONSENT_BYPASS
```

### Phase 3: Capability Labels Enhancement ✅ COMPLETE
**Goal**: Capabilities as freeform labels for documentation/discovery (NOT enforcement)

- [x] Remove strict pattern validation from `tool_spec.py`
  - [x] Allow any non-empty string as capability label
  - [x] Update JSON schema to remove pattern requirement
  - [x] Update comments to clarify "labels only, not enforced"
- [x] Update documentation
  - [x] Document that capabilities are freeform labels in tool_spec.py docstrings
  - [x] Suggest optional format: 'cap:library.action' (e.g., 'cap:numpy.array')
  - [x] Clarify no enforcement - just for transparency and discovery

**Design Decision**: Defer capability enforcement to v3.0.0
- Current: Freeform labels for LLM flexibility
- No context overhead from rigid taxonomy
- Useful for discovery, filtering, and transparency
- Future: Add enforcement layer in v3.0.0 without breaking existing tools

**Future: v3.0.0 Capability Enforcement (Not Now)**
- Define capability taxonomy and enforcement rules
- Mode-based restrictions (safe mode blocks write capabilities)
- Capability checking before tool execution
- Security boundaries based on capabilities

### Phase 4: Agentic Error Correction with MCP Sampling ✅ COMPLETE
**Goal**: Demonstrate MCP sampling framework by implementing safe, automatic JSON error correction

#### Implementation
- [x] Add sampling support to `dynamic_registrar.py`
  - [x] Add `Context` parameter to meta-tools (via `ctx` parameter)
  - [x] Create `_attempt_json_correction()` helper method
  - [x] Integrate correction into error handling flow
  - [x] Add retry limit (max 1 correction attempt)
- [x] Error correction logic
  - [x] Detect JSON parsing errors (JSONDecodeError)
  - [x] Call `ctx.sample()` with correction prompt
  - [x] Parse corrected JSON
  - [x] Retry registration with corrected values
  - [x] Return transparent result showing what was corrected
- [x] Safety & transparency
  - [x] Log all correction attempts to audit trail
  - [x] Return both original and corrected values in success response
  - [x] Add `auto_correct_json` option (opt-in via `%mcp_option`)
  - [x] Default: disabled (explicit errors preferred)
  - [x] Add to valid options in jupyter_mcp_extension.py
- [x] Testing (20 tests, all passing)
  - [x] Unit tests for `_attempt_json_correction()` with mock Context
  - [x] Test with malformed JSON in parameters, capabilities, returns, examples, tags
  - [x] Test retry limits (single attempt only)
  - [x] Test opt-in/opt-out behavior (default disabled)
  - [x] Mock `ctx.sample()` to avoid real LLM calls in tests
  - [x] Test correction prompt format and temperature
  - [x] Test validation of corrected JSON
  - [x] Test exception handling
  - [x] Test audit logging
  - [x] Test edge cases (empty JSON, special characters, long strings)

#### Human Testing Checklist (Phase 4):
**Setup:**
1. Start Jupyter with MCP server: `instrmcp jupyter --unsafe --port 3000`
2. Enable auto-correction: Run in notebook: `%mcp_option auto_correct_json`
3. Restart server: `%mcp_restart`

**Test Cases:**
1. **Test malformed JSON in parameters field**:
   - Register tool with broken JSON: `parameters: "[{name: test}]"` (missing quotes)
   - Should auto-correct and return: `{"status": "success_corrected", "corrected_field": "parameters", ...}`
   - Verify tool is registered correctly

2. **Test malformed JSON in capabilities field**:
   - Register tool with: `capabilities: "['cap:python.numpy']"` (wrong quotes)
   - Should auto-correct to proper JSON array
   - Verify correction in response

3. **Test disabled auto-correction (default)**:
   - Without `%mcp_option auto_correct_json`
   - Register tool with malformed JSON
   - Should return: `{"status": "error", "message": "Invalid JSON..."}`
   - No correction attempt

4. **Test correction failure**:
   - Provide severely broken JSON that LLM can't fix
   - Should fail after 1 attempt and return error

### Phase 5: Testing & Documentation
- [x] Unit tests (Phase 1 - completed)
  - [x] `tests/unit/servers/test_dynamic_tools.py` - 28 tests covering tool_spec, registry, audit
- [ ] Additional unit tests
  - [ ] Test consent workflow integration
  - [ ] Test dynamic runtime execution
  - [ ] Test "always allow" permissions
  - [ ] Test JSON auto-correction (Phase 4)
- [ ] Integration tests
  - [ ] `tests/integration/test_dynamic_tool_workflow.py`
    - [ ] Full workflow: register → consent → execute → revoke
    - [ ] Test "always allow" persistence
    - [ ] Test tool updates with diff
    - [ ] Test JSON correction workflow
- [ ] Update documentation
  - [ ] Update `README.md` with dynamic tools feature
  - [ ] Create `docs/DYNAMIC_TOOLS.md`
    - [ ] User guide for LLMs to create tools
    - [ ] Capability reference (for documentation)
    - [ ] Examples
    - [ ] Auto-correction feature documentation
  - [ ] Update `CLAUDE.md` with meta-tool descriptions and sampling feature

---

## 🔒 Security Analysis: Identified Risks & Mitigations (Simplified)

### 🔴 CRITICAL RISKS (P0)

#### 1. Arbitrary Code Execution
- **Risk**: Dynamic tools run with full Jupyter kernel access
- **Attack Vector**: Malicious LLM or compromised tool spec executing harmful code
- **Impact**: Data theft, system compromise, instrument damage
- **Mitigation**:
  - ✅ User consent UI showing full source code
  - ✅ Basic capability declaration (for transparency)
  - ✅ Mode-based restrictions (safe mode blocks write capabilities)
- **Status**: [ ] Not implemented yet

#### 2. Privilege Escalation
- **Risk**: Safe mode tools gaining unsafe privileges
- **Attack Vector**: Tool exploiting capability system to bypass mode boundaries
- **Impact**: Unauthorized instrument writes, cell modifications
- **Mitigation**:
  - ✅ Mode boundary enforcement in backend
  - ✅ Capabilities cannot exceed server's current mode
  - ✅ Re-consent required if server mode changes
  - ✅ Separate namespaces for safe/unsafe tools
  - ✅ Write capabilities blocked in safe mode
- **Status**: [ ] Not implemented yet

### 🟡 HIGH RISKS (P1)

#### 3. Resource Exhaustion (DoS)
- **Risk**: Infinite loops, memory bombs
- **Attack Vector**: Tool with malicious resource-intensive code
- **Impact**: Kernel crash, Jupyter hang
- **Mitigation**:
  - ✅ User review of source code before approval
  - ✅ Registry size limits (max 100 tools, 10MB total)
- **Status**: [ ] Not implemented yet

### 🟢 MEDIUM RISKS (P2)

#### 4. Consent UI Bypassing
- **Risk**: Executing tools without user consent
- **Attack Vector**: Direct backend API calls
- **Impact**: Unauthorized tool execution
- **Mitigation**:
  - ✅ Backend validates consent tokens
  - ✅ Consent tokens with expiration (5 min)
  - ✅ Simple audit log of approval decisions
- **Status**: [ ] Not implemented yet

#### 5. Tool Name Conflicts
- **Risk**: Overwriting system tools or other dynamic tools
- **Attack Vector**: Registering tool with existing name
- **Impact**: Breaking system functionality
- **Mitigation**:
  - ✅ Reserved namespace for system tools
  - ✅ Unique name validation
  - ✅ `dynamic:` prefix for all dynamic tools
- **Status**: [ ] Not implemented yet

---

## 📁 File Structure

```
instrmcp/
├── servers/jupyter_qcodes/
│   ├── registrars/
│   │   ├── __init__.py
│   │   ├── dynamic_tools.py          # [ ] DynamicToolRegistrar
│   │   └── ...
│   ├── security/                      # [ ] New directory
│   │   ├── __init__.py
│   │   ├── capabilities.py           # [ ] Capability definitions
│   │   └── audit.py                  # [ ] Simple audit logging
│   └── dynamic_runtime.py            # [ ] Tool execution engine
├── extensions/jupyterlab/src/
│   ├── consent/                       # [ ] New directory
│   │   ├── ConsentDialog.tsx         # [ ] React UI component
│   │   ├── DiffViewer.tsx            # [ ] Code diff display
│   │   ├── CapabilityList.tsx        # [ ] Permissions checklist
│   │   └── ResourceLimits.tsx        # [ ] Limits display
│   ├── comm/                          # [ ] New directory
│   │   └── capcall.ts                # [ ] mcp:capcall channel
│   └── index.ts                       # [ ] Update with new comm
└── tools/
    ├── __init__.py
    └── tool_spec.py                  # [ ] ToolSpec schema & validation

~/.instrmcp/
├── registry/                          # [x] Created on first use
│   ├── {tool_name}.json              # [x] Individual tool specs (one file per tool)
│   └── ...
├── consents/                          # [ ] User preferences (future)
│   └── always_allow.json             # [ ] "Always allow" decisions
└── audit/                             # [x] Audit logs
    └── tool_audit.log                # [x] Simple audit trail (registrations, updates, revocations)
```

---

## 🔧 Tool Spec Contract

### JSON Schema (Simplified - As Implemented)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "version", "description", "author", "capabilities", "parameters", "returns", "source_code"],
  "properties": {
    "name": {
      "type": "string",
      "pattern": "^[a-z_][a-z0-9_]*$",
      "minLength": 1,
      "maxLength": 64,
      "description": "Tool name (snake_case, max 64 chars)"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "Semantic version (e.g., 1.0.0)"
    },
    "description": {
      "type": "string",
      "minLength": 10,
      "maxLength": 500,
      "description": "Tool description (10-500 chars)"
    },
    "author": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100,
      "description": "Tool author identifier"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp"
    },
    "capabilities": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^cap:[a-z]+\\.[a-z]+$"
      },
      "minItems": 1,
      "description": "Required capabilities (e.g., cap:qcodes.read)"
    },
    "parameters": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type", "description"],
        "properties": {
          "name": {"type": "string", "pattern": "^[a-z_][a-z0-9_]*$"},
          "type": {"type": "string", "enum": ["string", "number", "boolean", "array", "object"]},
          "description": {"type": "string", "minLength": 1},
          "required": {"type": "boolean"},
          "default": {},
          "enum": {"type": "array"}
        }
      }
    },
    "returns": {
      "type": "object",
      "required": ["type", "description"],
      "properties": {
        "type": {"type": "string"},
        "description": {"type": "string", "minLength": 1}
      }
    },
    "source_code": {
      "type": "string",
      "minLength": 1,
      "maxLength": 10000,
      "description": "Python function source code (max 10KB)"
    },
    "examples": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Usage examples"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Searchable tags"
    }
  }
}
```

### Example Tool Spec (Simplified - As Implemented)

```json
{
  "name": "analyze_resonator",
  "version": "1.0.0",
  "description": "Analyze resonator frequency sweep data to extract Q-factor and resonant frequency",
  "author": "claude",
  "created_at": "2025-10-01T12:00:00Z",
  "updated_at": "2025-10-01T12:00:00Z",
  "capabilities": [
    "cap:numpy",
    "cap:scipy"
  ],
  "parameters": [
    {
      "name": "frequencies",
      "type": "array",
      "description": "Frequency sweep data in Hz",
      "required": true
    },
    {
      "name": "amplitudes",
      "type": "array",
      "description": "Amplitude response data",
      "required": true
    }
  ],
  "returns": {
    "type": "object",
    "description": "Analysis results with f0, Q-factor, and amplitude"
  },
  "source_code": "import numpy as np\nfrom scipy.optimize import curve_fit\n\ndef analyze_resonator(frequencies, amplitudes):\n    \"\"\"Fit Lorentzian to extract Q-factor.\"\"\"\n    def lorentzian(f, f0, Q, A):\n        return A / (1 + 4*Q**2*((f-f0)/f0)**2)\n    \n    popt, _ = curve_fit(lorentzian, frequencies, amplitudes)\n    f0, Q, A = popt\n    return {'f0': f0, 'Q': Q, 'amplitude': A}",
  "examples": [
    "analyze_resonator(frequencies=[1e9, 1.1e9, 1.2e9], amplitudes=[0.5, 1.0, 0.5])"
  ],
  "tags": ["analysis", "resonator", "qfactor"]
}
```

---

## 🔄 Invocation Flow

```
┌─────────┐
│   LLM   │
└────┬────┘
     │ 1. tool.register(toolSpec)
     ▼
┌────────────────────────────────────────────┐
│         Backend (MCP Server)               │
│  ┌──────────────────────────────────────┐  │
│  │  2. Validate schema                  │  │
│  │  3. Check name conflicts             │  │
│  │  4. Generate consent token           │  │
│  └──────────────────────────────────────┘  │
└────┬───────────────────────────────────────┘
     │ 5. Send consent_request via mcp:capcall
     ▼
┌────────────────────────────────────────────┐
│       Frontend (JupyterLab)                │
│  ┌──────────────────────────────────────┐  │
│  │  6. Show ConsentDialog               │  │
│  │     • Source code (highlighted)      │  │
│  │     • Capabilities:                  │  │
│  │       ☑ notebook.read                │  │
│  │       ☑ numpy                        │  │
│  │       ☑ scipy                        │  │
│  │     • Limits: 5s, 100MB, 10/min      │  │
│  │                                       │  │
│  │  [Allow] [Always Allow] [Decline]    │  │
│  └──────────────────────────────────────┘  │
└────┬───────────────────────────────────────┘
     │ 7. User clicks: [Allow] or [Always Allow] or [Decline]
     │ 8. Send consent_response via mcp:capcall
     ▼
┌────────────────────────────────────────────┐
│         Backend (MCP Server)               │
│  ┌──────────────────────────────────────┐  │
│  │  9. Validate consent token           │  │
│  │ 10. Check token not expired          │  │
│  │ 11. Persist to registry:             │  │
│  │     ~/.instrmcp/registry/tools/      │  │
│  │     {toolname}.json                  │  │
│  │ 12. Update manifest.json             │  │
│  │ 13. Register with FastMCP:           │  │
│  │     @mcp.tool(name="dynamic:...")    │  │
│  │ 14. Simple audit log entry           │  │
│  └──────────────────────────────────────┘  │
└────┬───────────────────────────────────────┘
     │ 15. Return success to LLM
     ▼
┌─────────┐
│   LLM   │  Tool now available for invocation
└────┬────┘
     │ 16. Invoke: analyze_resonator(freqs, amps)
     ▼
┌────────────────────────────────────────────┐
│      Dynamic Runtime (Direct Execution)    │
│  ┌──────────────────────────────────────┐  │
│  │ 17. Load tool spec from registry     │  │
│  │ 18. Check mode-based restrictions    │  │
│  │ 19. Execute in Jupyter kernel        │  │
│  │ 20. Return result                    │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

---

## 📚 API Reference

### Meta-Tools (Unsafe Mode Only)

#### `tool.register(toolSpec: dict) -> dict`
Register a new dynamic tool.

**Parameters:**
- `toolSpec`: Tool specification (see schema above)

**Returns:**
```json
{
  "success": true,
  "tool_name": "analyze_resonator",
  "message": "Tool registered successfully"
}
```

**Errors:**
- `SchemaValidationError`: Invalid tool spec format
- `NameConflictError`: Tool name already exists
- `ConsentDeniedError`: User declined consent
- `ConsentTimeoutError`: User didn't respond within 5 minutes

---

#### `tool.update(name: str, toolSpec: dict) -> dict`
Update an existing dynamic tool.

**Parameters:**
- `name`: Existing tool name
- `toolSpec`: New tool specification

**Returns:**
```json
{
  "success": true,
  "tool_name": "analyze_resonator",
  "diff": {
    "source_code_changed": true,
    "capabilities_added": ["cap:matplotlib"],
    "capabilities_removed": [],
    "resource_limits_changed": {"timeout_seconds": {"old": 5, "new": 10}}
  },
  "message": "Tool updated successfully"
}
```

**Errors:**
- `ToolNotFoundError`: Tool doesn't exist
- `ConsentDeniedError`: User declined update consent

---

#### `tool.revoke(name: str) -> dict`
Revoke a dynamic tool.

**Parameters:**
- `name`: Tool name to revoke

**Returns:**
```json
{
  "success": true,
  "tool_name": "analyze_resonator",
  "message": "Tool revoked successfully"
}
```

**Errors:**
- `ToolNotFoundError`: Tool doesn't exist
- `SystemToolError`: Cannot revoke system tools

---

#### `tool.list(filter_capability: str = None) -> dict`
List all registered dynamic tools.

**Parameters:**
- `filter_capability` (optional): Filter by capability (e.g., "cap:notebook.read")

**Returns:**
```json
{
  "tools": [
    {
      "name": "analyze_resonator",
      "version": "1.0.0",
      "description": "Analyze resonator frequency sweep data...",
      "capabilities": ["cap:notebook.read", "cap:numpy", "cap:scipy"],
      "created_at": "2025-10-01T12:00:00Z",
      "invocation_count": 42
    }
  ],
  "total": 1
}
```

---

#### `tool.inspect(name: str, show_diff: bool = False) -> dict`
Inspect a dynamic tool's details.

**Parameters:**
- `name`: Tool name to inspect
- `show_diff`: If true, show diff from previous version

**Returns:**
```json
{
  "name": "analyze_resonator",
  "version": "1.0.0",
  "description": "Analyze resonator frequency sweep data...",
  "author": "claude",
  "created_at": "2025-10-01T12:00:00Z",
  "updated_at": "2025-10-01T12:00:00Z",
  "capabilities": ["cap:notebook.read", "cap:numpy", "cap:scipy"],
  "resource_limits": {
    "timeout_seconds": 5,
    "memory_mb": 100,
    "rate_limit_per_minute": 10
  },
  "source_code": "import numpy as np...",
  "invocation_count": 42,
  "last_invoked_at": "2025-10-01T15:30:00Z",
  "approval_history": [
    {
      "version": "1.0.0",
      "approved_at": "2025-10-01T12:00:30Z",
      "decision": "allow"
    }
  ]
}
```

**Errors:**
- `ToolNotFoundError`: Tool doesn't exist

---

## 🧪 Testing Strategy

### Unit Tests (80%+ coverage)

**`tests/unit/test_tool_spec.py`**
- [ ] Valid tool spec passes validation
- [ ] Invalid schemas rejected
- [ ] Timestamp validation

**`tests/unit/test_dynamic_tools.py`**
- [ ] tool.register() with valid spec succeeds
- [ ] tool.register() with duplicate name fails
- [ ] tool.register() with invalid schema fails
- [ ] tool.update() shows correct diff
- [ ] tool.revoke() removes tool from registry
- [ ] tool.list() returns all tools
- [ ] tool.inspect() returns full details

**`tests/unit/test_capabilities.py`**
- [ ] Basic capability checking works
- [ ] Mode restrictions enforced (safe vs unsafe)
- [ ] Registry size limits enforced

### Integration Tests

**`tests/integration/test_dynamic_tool_workflow.py`**
- [ ] Full workflow: register → consent UI → execute → revoke
- [ ] "Always allow" persists across server restarts
- [ ] Tool updates trigger re-consent
- [ ] Simple audit log entries created


---

## 📖 Documentation Updates

- [ ] **README.md**: Add "Dynamic Tools" section
- [ ] **docs/DYNAMIC_TOOLS.md**: User guide
  - [ ] How LLMs can create tools
  - [ ] Capability reference (for documentation purposes)
  - [ ] Simple security model explanation
  - [ ] Example tool specs
  - [ ] Best practices
- [ ] **CLAUDE.md**: Add meta-tool descriptions
- [ ] **CHANGELOG.md**: Document v2.0.0 changes

---

## 🚀 Rollout Plan

### Phase 1: Internal Testing (Week 9)
- Deploy to development environment
- Internal security audit
- Fix critical bugs

### Phase 2: Alpha Release (Week 10)
- Feature flag: `%mcp_option dynamic_tools`
- Limited rollout to early adopters
- Collect feedback

### Phase 3: Beta Release (Week 11)
- Address feedback
- Performance optimization
- Documentation refinement

### Phase 4: Production Release (Week 12)
- Full release as v2.0.0
- Announcement
- Monitor for issues

---

## ⚠️ Open Questions

1. **Cross-Notebook Tool Sharing**: Should tools registered in one notebook be available in all notebooks?
   - Option A: Global registry (current design)
   - Option B: Per-notebook registry
   - Option C: Hybrid with explicit sharing

2. **Tool Versioning**: How to handle multiple versions of same tool?
   - Option A: Only latest version (current design)
   - Option B: Side-by-side versions (complexity)
   - Option C: Version pinning in invocations

---

## 🧪 Quick Start: Human Testing Guide

### Current Status: Phase 2 Backend Complete ✅

**What You Can Test Now:**
1. **Phase 1 Meta-Tools** - Register, update, list, inspect, revoke tools
2. **Phase 2 Execution** - Create and execute dynamic tools in Jupyter

**Quick Test (5 minutes):**

```bash
# 1. Start MCP server in unsafe mode
instrmcp jupyter --unsafe --port 3000

# 2. Open JupyterLab, create notebook with:
import numpy as np
multiplier = 10

# 3. Use MCP Inspector to register a tool:
# Tool: dynamic_register_tool
# Enter these parameters (JSON fields are objects, not strings):
name: "quick_test"
source_code: "import numpy as np\n\ndef quick_test(x):\n    return x * multiplier"
parameters: [{"name": "x", "type": "number", "description": "Input", "required": true}]
# Optional: Add these for more detail
capabilities: ["cap:python.numpy"]
returns: {"type": "number", "description": "Result"}

# NOTE: parameters field is REQUIRED if your function has arguments!

# 4. Execute the tool via MCP Inspector:
# Tool: quick_test, Parameters: {"x": 5}
# Expected: {"status": "success", "result": 50}

# 5. Verify persistence:
ls ~/.instrmcp/registry/quick_test.json
tail ~/.instrmcp/audit/tool_audit.log
```

**See detailed testing checklists in each phase section above.**

---

## 📝 Notes

- This is a major feature enabling LLM-driven tool creation
- User education critical: consent UI must be clear and informative
- Simplified security model: rely on user review and mode-based restrictions
- Backward compatibility maintained (existing tools unaffected)
- Feature can be disabled via server configuration if needed

---

**Last Updated**: 2025-10-01
**Next Review**: After Phase 2 consent UI completion
