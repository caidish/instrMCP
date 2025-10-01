# Dynamic MCP Tool Creation - Implementation TODO

## 📋 Project Overview

Enable LLMs to create dynamic MCP tools at runtime with comprehensive security controls through consent UI, capability-based permissions, and sandboxed execution.

**Status**: Planning Phase
**Target Version**: 2.0.0
**Estimated Timeline**: one week
**Last Updated**: 2025-10-01

---

## 🎯 Implementation Phases

### Phase 1: Core Infrastructure 
- [ ] Design tool spec JSON schema
  - [ ] Define required fields (name, version, description, hash, signature)
  - [ ] Define capability strings taxonomy
  - [ ] Define resource limit constraints
  - [ ] Define parameter schema format
- [ ] Create `instrmcp/tools/tool_spec.py`
  - [ ] ToolSpec dataclass with validation
  - [ ] JSON schema validator
  - [ ] Hash computation (SHA-256)
  - [ ] Signature verification (HMAC-SHA256)
- [ ] Implement registry storage at `~/.instrmcp/registry/`
  - [ ] Create directory structure on first run
  - [ ] Implement atomic file writes with backup
  - [ ] Add manifest.json index management
  - [ ] Set proper file permissions (0600)
- [ ] Create `instrmcp/servers/jupyter_qcodes/registrars/dynamic_tools.py`
  - [ ] DynamicToolRegistrar class
  - [ ] Registry persistence layer
  - [ ] Tool loading on server start
- [ ] Add crypto utilities in `instrmcp/servers/jupyter_qcodes/security/crypto.py`
  - [ ] SHA-256 hashing for tool specs
  - [ ] HMAC-SHA256 signing/verification
  - [ ] Nonce generation
  - [ ] Constant-time comparison
- [ ] Create audit logging system in `instrmcp/servers/jupyter_qcodes/security/audit.py`
  - [ ] Structured logging to `~/.instrmcp/audit/tool_audit.log`
  - [ ] Log: registrations, updates, revocations, executions, denials
  - [ ] Log rotation (max 10MB per file, keep 5 files)

### Phase 2: Backend Meta-Tools
- [ ] Implement `tool.register(toolSpec)` in DynamicToolRegistrar
  - [ ] Validate toolSpec schema
  - [ ] Check name conflicts (reject if exists without update flag)
  - [ ] Compute hash and verify signature
  - [ ] Send consent request to frontend via `mcp:capcall`
  - [ ] Wait for consent response (timeout: 5 min)
  - [ ] On approval: persist to registry + register with FastMCP
  - [ ] On decline: cleanup and return error
  - [ ] Audit log entry
- [ ] Implement `tool.update(name, toolSpec)`
  - [ ] Load existing tool spec
  - [ ] Compute diff (source code, capabilities, limits)
  - [ ] Send diff in consent request
  - [ ] Require re-consent
  - [ ] Update registry atomically
  - [ ] Re-register with FastMCP
- [ ] Implement `tool.revoke(name)`
  - [ ] Remove from registry
  - [ ] Unregister from FastMCP
  - [ ] Remove "always allow" permissions if present
  - [ ] Audit log entry
- [ ] Implement `tool.list()`
  - [ ] Query registry manifest
  - [ ] Return: name, version, description, capabilities, created_at
  - [ ] Filter by capability (optional parameter)
- [ ] Implement `tool.inspect(name)`
  - [ ] Load full tool spec from registry
  - [ ] Return: full spec + approval history + invocation stats
  - [ ] Support diff mode: compare with previous version
- [ ] Register all meta-tools with FastMCP (only in unsafe mode)
- [ ] Add unit tests for each meta-tool

### Phase 3: Frontend Consent UI
- [ ] Create new comm channel `mcp:capcall` in TypeScript extension
  - [ ] Update `instrmcp/extensions/jupyterlab/src/index.ts`
  - [ ] Add comm handler for `mcp:capcall` messages
  - [ ] Message types: `consent_request`, `consent_response`
- [ ] Build React consent dialog component
  - [ ] Create `instrmcp/extensions/jupyterlab/src/consent/ConsentDialog.tsx`
    - [ ] Modal dialog using JupyterLab Dialog
    - [ ] Display tool name, description, author
    - [ ] Syntax-highlighted source code viewer (CodeMirror)
    - [ ] SHA-256 hash display with copy button
    - [ ] Action buttons: [Allow], [Always Allow], [Decline]
  - [ ] Create `instrmcp/extensions/jupyterlab/src/consent/CapabilityList.tsx`
    - [ ] Checklist of requested capabilities
    - [ ] Icons and descriptions for each capability type
    - [ ] Warning badges for dangerous capabilities
  - [ ] Create `instrmcp/extensions/jupyterlab/src/consent/DiffViewer.tsx`
    - [ ] Side-by-side diff for tool updates
    - [ ] Highlight capability changes
    - [ ] Highlight resource limit changes
  - [ ] Create `instrmcp/extensions/jupyterlab/src/consent/ResourceLimits.tsx`
    - [ ] Display: timeout, memory limit, rate limit
    - [ ] Visual indicators (progress bars, badges)
- [ ] Implement user preferences storage
  - [ ] Store "always allow" decisions in `~/.instrmcp/registry/consents/always_allow.json`
  - [ ] UI to view and revoke "always allow" permissions
- [ ] Add consent workflow logic
  - [ ] Handle consent_request messages from backend
  - [ ] Show ConsentDialog
  - [ ] Send consent_response back to backend
  - [ ] Handle timeout (5 min) with auto-decline
- [ ] Build extension with `jlpm run build`
- [ ] Test consent UI manually

### Phase 4: Security & Sandboxing
- [ ] Add RestrictedPython dependency to `pyproject.toml`
- [ ] Create `instrmcp/servers/jupyter_qcodes/security/sandbox.py`
  - [ ] RestrictedPython execution wrapper
  - [ ] Whitelist safe builtins (len, range, str, int, float, list, dict, etc.)
  - [ ] Blacklist dangerous builtins (eval, exec, __import__, open, etc.)
  - [ ] AST inspection to detect dangerous patterns
  - [ ] Custom `__builtins__` with limited functions
- [ ] Create `instrmcp/servers/jupyter_qcodes/security/capabilities.py`
  - [ ] Define capability taxonomy:
    - `cap:qcodes.read` - Read QCodes instruments
    - `cap:qcodes.write` - Write to instruments
    - `cap:notebook.read` - Read notebook variables
    - `cap:notebook.write` - Modify notebook cells
    - `cap:database.read` - Read measurement database
    - `cap:database.write` - Write to database
    - `cap:network.egress` - External network calls
    - `cap:file.read` - Read files
    - `cap:file.write` - Write files
    - `cap:numpy` - Use NumPy
    - `cap:scipy` - Use SciPy
    - `cap:matplotlib` - Use Matplotlib
  - [ ] Capability enforcement at runtime
  - [ ] Capability dependency resolution (e.g., scipy requires numpy)
  - [ ] Mode-based capability restrictions (safe mode blocks write caps)
- [ ] Create `instrmcp/servers/jupyter_qcodes/security/resource_limits.py`
  - [ ] Execution timeout enforcement (signal.alarm or threading.Timer)
  - [ ] Memory limit enforcement (resource.setrlimit on Unix)
  - [ ] Rate limiting (token bucket algorithm)
  - [ ] Invocation counter per tool
- [ ] Create `instrmcp/servers/jupyter_qcodes/dynamic_runtime.py`
  - [ ] DynamicToolRuntime class
  - [ ] Execute tool in sandbox with capabilities + limits
  - [ ] Catch and sanitize exceptions
  - [ ] Log all executions
- [ ] Integration with DynamicToolRegistrar
  - [ ] Runtime execution on tool invocation
  - [ ] Audit logging
- [ ] Add security unit tests
  - [ ] Test sandbox escapes (should fail)
  - [ ] Test capability violations (should fail)
  - [ ] Test resource limit violations (should timeout/fail)

### Phase 5: Testing & Documentation
- [ ] Unit tests
  - [ ] `tests/unit/test_tool_spec.py` - Schema validation
  - [ ] `tests/unit/test_dynamic_tools.py` - Meta-tool logic
  - [ ] `tests/unit/test_sandbox.py` - Sandbox escapes
  - [ ] `tests/unit/test_capabilities.py` - Permission checks
  - [ ] `tests/unit/test_resource_limits.py` - Limit enforcement
  - [ ] `tests/unit/test_crypto.py` - Hash/signature validation
- [ ] Integration tests
  - [ ] `tests/integration/test_dynamic_tool_workflow.py`
    - [ ] Full workflow: register → consent → execute → revoke
    - [ ] Test "always allow" persistence
    - [ ] Test tool updates with diff
- [ ] Security penetration testing
  - [ ] Attempt sandbox escapes
  - [ ] Attempt privilege escalation
  - [ ] Attempt data exfiltration
  - [ ] Attempt resource exhaustion
  - [ ] Attempt registry poisoning
- [ ] Update documentation
  - [ ] Update `README.md` with dynamic tools feature
  - [ ] Create `docs/DYNAMIC_TOOLS.md`
    - [ ] User guide for LLMs to create tools
    - [ ] Capability reference
    - [ ] Security model explanation
    - [ ] Examples
  - [ ] Update `CLAUDE.md` with meta-tool descriptions
  - [ ] Update `docs/ARCHITECTURE.md` with new components
- [ ] Add migration guide
  - [ ] No migration needed (new feature)
  - [ ] Document how to enable/disable feature

---

## 🔒 Security Analysis: Identified Loopholes & Mitigations

### 🔴 CRITICAL RISKS (P0)

#### 1. Arbitrary Code Execution
- **Risk**: Dynamic tools run in kernel context with full Python access
- **Attack Vector**: Malicious LLM or compromised tool spec executing harmful code
- **Impact**: Data theft, system compromise, instrument damage
- **Mitigation**:
  - ✅ RestrictedPython sandbox with whitelist-only builtins
  - ✅ Capability-based permissions enforced at runtime
  - ✅ AST inspection blocking dangerous patterns (`eval`, `exec`, `__import__`)
  - ✅ Separate execution context with limited globals
  - ✅ No access to `__builtins__` or `sys` modules
- **Status**: [ ] Not implemented yet

#### 2. Data Exfiltration
- **Risk**: Tools accessing sensitive notebook data, instrument settings, or database
- **Attack Vector**: Tool declaring minimal capabilities but accessing more via side channels
- **Impact**: Leakage of experimental data, proprietary information
- **Mitigation**:
  - ✅ Explicit capability declaration required (e.g., `cap:notebook.read`)
  - ✅ Variable access whitelist (tools declare needed variables)
  - ✅ Network egress capability required and logged
  - ✅ Audit trail of all data access
  - ✅ No implicit capability escalation
- **Status**: [ ] Not implemented yet

#### 3. Privilege Escalation
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

#### 4. Tool Spec Tampering
- **Risk**: Modified tool specs after user approval
- **Attack Vector**: Direct file modification of registry JSON files
- **Impact**: Executing unapproved code under approved tool name
- **Mitigation**:
  - ✅ SHA-256 hash verification before each execution
  - ✅ HMAC-SHA256 cryptographic signatures
  - ✅ Version tracking with timestamps
  - ✅ Re-consent required on any spec change (hash mismatch)
  - ✅ File permissions 0600 on registry files
- **Status**: [ ] Not implemented yet

#### 5. Registry Poisoning
- **Risk**: Malicious modification of `~/.instrmcp/registry/*.json`
- **Attack Vector**: Attacker with file system access editing registry
- **Impact**: Arbitrary code execution under trusted tool names
- **Mitigation**:
  - ✅ File permissions (0600) on registry directory and files
  - ✅ JSON schema validation on every load
  - ✅ Integrity checksums for entire registry (manifest.json)
  - ✅ Atomic writes with backup/rollback
  - ✅ Detect tampering and refuse to load corrupted registry
- **Status**: [ ] Not implemented yet

#### 6. Resource Exhaustion (DoS)
- **Risk**: Infinite loops, memory bombs, disk filling
- **Attack Vector**: Tool with malicious resource-intensive code
- **Impact**: Kernel crash, Jupyter hang, disk full
- **Mitigation**:
  - ✅ Execution timeout (default 5s, max 60s)
  - ✅ Memory limits enforced via `resource.setrlimit()`
  - ✅ Registry size limits (max 100 tools, 10MB total)
  - ✅ Tool invocation rate limiting (default 10/min)
  - ✅ Disk quota for tool storage
- **Status**: [ ] Not implemented yet

### 🟢 MEDIUM RISKS (P2)

#### 7. Consent UI Bypassing
- **Risk**: Frontend bypass or race conditions allowing unapproved execution
- **Attack Vector**: Direct backend API calls, WebSocket message injection
- **Impact**: Executing tools without user consent
- **Mitigation**:
  - ✅ Backend double-checks all consents (never trust frontend)
  - ✅ Consent tokens with expiration (5 min)
  - ✅ Audit log of all approval decisions with timestamps
  - ✅ No backend execution without valid consent token
  - ✅ One-time-use consent tokens (nonce)
- **Status**: [ ] Not implemented yet

#### 8. Replay Attacks
- **Risk**: Reusing old signed tool specs
- **Attack Vector**: Replaying previously approved tool spec with different backend state
- **Impact**: Executing outdated/vulnerable tool versions
- **Mitigation**:
  - ✅ Nonce generation per registration (UUID v4)
  - ✅ Timestamp validation (reject specs >1 hour old)
  - ✅ Version monotonicity checks (version must increase)
  - ✅ Revoked tool blacklist (never allow re-registration)
  - ✅ Consent token single-use enforcement
- **Status**: [ ] Not implemented yet

#### 9. Tool Name Conflicts
- **Risk**: Overwriting system tools or other dynamic tools
- **Attack Vector**: Registering tool with existing name
- **Impact**: Breaking system functionality, tool hijacking
- **Mitigation**:
  - ✅ Reserved namespace prefix for system tools (`system:*`, `qcodes:*`, `notebook:*`)
  - ✅ Unique name validation (reject exact conflicts)
  - ✅ Namespacing: `dynamic:toolname` prefix for all dynamic tools
  - ✅ Update-only mode for existing tools (explicit flag required)
  - ✅ Case-insensitive name comparison
- **Status**: [ ] Not implemented yet

#### 10. Side Channel Attacks
- **Risk**: Information leakage via timing, errors, exceptions
- **Attack Vector**: Analyzing tool execution time or error messages
- **Impact**: Inferring sensitive data from timing patterns
- **Mitigation**:
  - ✅ Constant-time hash comparisons (secrets.compare_digest)
  - ✅ Sanitized error messages (no internal paths, no stack traces to user)
  - ✅ Timing jitter on sensitive operations (random delay)
  - ✅ Rate limiting to prevent timing analysis
  - ✅ Generic error responses for security failures
- **Status**: [ ] Not implemented yet

#### 11. Tool Chaining Exploits
- **Risk**: Dynamic tool calling other dynamic tools recursively
- **Attack Vector**: Tool A calls Tool B calls Tool C, capability escalation
- **Impact**: Bypassing capability limits through composition
- **Mitigation**:
  - ✅ Call stack depth limit (max 3 levels)
  - ✅ Capability propagation rules (no elevation, only intersection)
  - ✅ Cross-tool invocation logging (audit trail)
  - ✅ Circular dependency detection
  - ✅ Total execution time limit across call chain
- **Status**: [ ] Not implemented yet

#### 12. Persistence Attacks
- **Risk**: "Always allow" enabling permanent backdoors
- **Attack Vector**: Getting user to click "Always Allow" once
- **Impact**: Long-term unauthorized access
- **Mitigation**:
  - ✅ Periodic re-consent (30 days for critical capabilities)
  - ✅ Revocation UI (`tool.revoke_permissions(name)`)
  - ✅ Capability expiration timestamps
  - ✅ Audit dashboard for reviewing "always allow" grants
  - ✅ Warning on "Always Allow" for dangerous capabilities
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
│   │   ├── sandbox.py                # [ ] RestrictedPython wrapper
│   │   ├── capabilities.py           # [ ] Permission system
│   │   ├── crypto.py                 # [ ] Hash/sign utilities
│   │   ├── resource_limits.py        # [ ] CPU/mem enforcement
│   │   └── audit.py                  # [ ] Audit logging
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
├── registry/                          # [ ] Create on first run
│   ├── manifest.json                 # [ ] Tool registry index
│   ├── tools/                         # [ ] Tool specs
│   │   ├── {tool_name_hash}.json    # [ ] Individual tool specs
│   │   └── ...
│   └── consents/                      # [ ] User preferences
│       └── always_allow.json         # [ ] "Always allow" decisions
└── audit/                             # [ ] Audit logs
    └── tool_audit.log                # [ ] Security audit trail
```

---

## 🔧 Tool Spec Contract

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "version", "description", "author", "capabilities", "resource_limits", "source_code"],
  "properties": {
    "name": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9_]{2,63}$",
      "description": "Tool name (lowercase, alphanumeric + underscore, 3-64 chars)"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "Semantic version (e.g., 1.0.0)"
    },
    "description": {
      "type": "string",
      "maxLength": 500,
      "description": "Human-readable description"
    },
    "author": {
      "type": "string",
      "maxLength": 100,
      "description": "Tool author (usually 'claude')"
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
    "hash": {
      "type": "string",
      "pattern": "^sha256:[a-f0-9]{64}$",
      "description": "SHA-256 hash of source_code"
    },
    "signature": {
      "type": "string",
      "pattern": "^hmac-sha256:[a-f0-9]{64}$",
      "description": "HMAC-SHA256 signature"
    },
    "nonce": {
      "type": "string",
      "description": "Unique identifier (UUID v4)"
    },
    "capabilities": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^cap:[a-z]+\\.[a-z]+$"
      },
      "description": "Required capabilities (e.g., 'cap:notebook.read')"
    },
    "resource_limits": {
      "type": "object",
      "properties": {
        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 60},
        "memory_mb": {"type": "integer", "minimum": 10, "maximum": 500},
        "rate_limit_per_minute": {"type": "integer", "minimum": 1, "maximum": 100}
      },
      "required": ["timeout_seconds", "memory_mb", "rate_limit_per_minute"]
    },
    "parameters": {
      "type": "object",
      "description": "Parameter schema (JSON Schema format)"
    },
    "source_code": {
      "type": "string",
      "maxLength": 50000,
      "description": "Python function source code"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "consent_token": {"type": "string"},
        "consent_expires_at": {"type": "string", "format": "date-time"}
      }
    }
  }
}
```

### Example Tool Spec

```json
{
  "name": "analyze_resonator",
  "version": "1.0.0",
  "description": "Analyze resonator frequency sweep data to extract Q-factor and resonant frequency",
  "author": "claude",
  "created_at": "2025-10-01T12:00:00Z",
  "updated_at": "2025-10-01T12:00:00Z",
  "hash": "sha256:1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890",
  "signature": "hmac-sha256:fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
  "nonce": "550e8400-e29b-41d4-a716-446655440000",

  "capabilities": [
    "cap:notebook.read",
    "cap:numpy",
    "cap:scipy"
  ],

  "resource_limits": {
    "timeout_seconds": 5,
    "memory_mb": 100,
    "rate_limit_per_minute": 10
  },

  "parameters": {
    "type": "object",
    "properties": {
      "frequencies": {
        "type": "array",
        "items": {"type": "number"},
        "description": "Frequency sweep data (Hz)"
      },
      "amplitudes": {
        "type": "array",
        "items": {"type": "number"},
        "description": "Amplitude response data"
      }
    },
    "required": ["frequencies", "amplitudes"]
  },

  "source_code": "import numpy as np\nfrom scipy.optimize import curve_fit\n\ndef analyze_resonator(frequencies, amplitudes):\n    \"\"\"Fit Lorentzian to extract Q-factor.\"\"\"\n    def lorentzian(f, f0, Q, A):\n        return A / (1 + 4*Q**2*((f-f0)/f0)**2)\n    \n    popt, _ = curve_fit(lorentzian, frequencies, amplitudes)\n    f0, Q, A = popt\n    return {'f0': f0, 'Q': Q, 'amplitude': A}",

  "metadata": {
    "consent_token": "temp-1a2b3c4d-5e6f-7890-abcd-ef1234567890",
    "consent_expires_at": "2025-10-01T12:05:00Z"
  }
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
│  │  4. Compute hash (SHA-256)           │  │
│  │  5. Generate consent token           │  │
│  └──────────────────────────────────────┘  │
└────┬───────────────────────────────────────┘
     │ 6. Send consent_request via mcp:capcall
     ▼
┌────────────────────────────────────────────┐
│       Frontend (JupyterLab)                │
│  ┌──────────────────────────────────────┐  │
│  │  7. Show ConsentDialog               │  │
│  │     • Source code (highlighted)      │  │
│  │     • Hash: sha256:1a2b3c...         │  │
│  │     • Capabilities:                  │  │
│  │       ☑ notebook.read                │  │
│  │       ☑ numpy                        │  │
│  │       ☑ scipy                        │  │
│  │     • Limits: 5s, 100MB, 10/min      │  │
│  │                                       │  │
│  │  [Allow] [Always Allow] [Decline]    │  │
│  └──────────────────────────────────────┘  │
└────┬───────────────────────────────────────┘
     │ 8. User clicks: [Allow] or [Always Allow] or [Decline]
     │ 9. Send consent_response via mcp:capcall
     ▼
┌────────────────────────────────────────────┐
│         Backend (MCP Server)               │
│  ┌──────────────────────────────────────┐  │
│  │ 10. Validate consent token           │  │
│  │ 11. Check token not expired          │  │
│  │ 12. Persist to registry:             │  │
│  │     ~/.instrmcp/registry/tools/      │  │
│  │     {hash}.json                      │  │
│  │ 13. Update manifest.json             │  │
│  │ 14. Register with FastMCP:           │  │
│  │     @mcp.tool(name="dynamic:...")    │  │
│  │ 15. Audit log entry                  │  │
│  └──────────────────────────────────────┘  │
└────┬───────────────────────────────────────┘
     │ 16. Return success to LLM
     ▼
┌─────────┐
│   LLM   │  Tool now available for invocation
└────┬────┘
     │ 17. Invoke: analyze_resonator(freqs, amps)
     ▼
┌────────────────────────────────────────────┐
│    Dynamic Runtime (Sandboxed Execution)   │
│  ┌──────────────────────────────────────┐  │
│  │ 18. Load tool spec from registry     │  │
│  │ 19. Verify hash (detect tampering)   │  │
│  │ 20. Check capabilities               │  │
│  │ 21. Apply resource limits            │  │
│  │ 22. Execute in RestrictedPython:     │  │
│  │     • Limited builtins               │  │
│  │     • Capability-controlled globals  │  │
│  │     • Timeout enforcement            │  │
│  │ 23. Return result                    │  │
│  │ 24. Audit log entry                  │  │
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
  "hash": "sha256:1a2b3c...",
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
  "old_hash": "sha256:1a2b3c...",
  "new_hash": "sha256:fedcba...",
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
  "hash": "sha256:1a2b3c...",
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
- [ ] Hash computation correct (SHA-256)
- [ ] Signature verification correct (HMAC-SHA256)
- [ ] Nonce uniqueness
- [ ] Timestamp validation (reject old specs)

**`tests/unit/test_dynamic_tools.py`**
- [ ] tool.register() with valid spec succeeds
- [ ] tool.register() with duplicate name fails
- [ ] tool.register() with invalid schema fails
- [ ] tool.update() shows correct diff
- [ ] tool.revoke() removes tool from registry
- [ ] tool.list() returns all tools
- [ ] tool.inspect() returns full details

**`tests/unit/test_sandbox.py`**
- [ ] Restricted builtins only accessible
- [ ] eval() blocked
- [ ] exec() blocked
- [ ] __import__() blocked
- [ ] open() blocked
- [ ] os module blocked
- [ ] sys module blocked
- [ ] Dangerous AST patterns detected

**`tests/unit/test_capabilities.py`**
- [ ] Capability enforcement works
- [ ] Missing capability blocks execution
- [ ] Mode restrictions enforced (safe vs unsafe)
- [ ] Capability dependency resolution
- [ ] No implicit escalation

**`tests/unit/test_resource_limits.py`**
- [ ] Timeout enforced (infinite loop killed)
- [ ] Memory limit enforced (memory bomb prevented)
- [ ] Rate limiting works (reject after threshold)
- [ ] Registry size limits enforced

**`tests/unit/test_crypto.py`**
- [ ] Hash computation deterministic
- [ ] Signature verification correct
- [ ] Constant-time comparison (timing attack resistant)
- [ ] Nonce collision probability negligible

### Integration Tests

**`tests/integration/test_dynamic_tool_workflow.py`**
- [ ] Full workflow: register → consent UI → execute → revoke
- [ ] "Always allow" persists across server restarts
- [ ] Tool updates trigger re-consent
- [ ] Hash mismatch detected and rejected
- [ ] Registry corruption detected
- [ ] Audit log entries created

### Security Penetration Testing

**`tests/security/test_penetration.py`**
- [ ] Attempt sandbox escape via `__builtins__` manipulation
- [ ] Attempt privilege escalation via capability bypass
- [ ] Attempt data exfiltration via side channel
- [ ] Attempt resource exhaustion (CPU, memory, disk)
- [ ] Attempt registry poisoning via file manipulation
- [ ] Attempt replay attack with old spec
- [ ] Attempt consent bypass via direct API call

---

## 📖 Documentation Updates

- [ ] **README.md**: Add "Dynamic Tools" section
- [ ] **docs/DYNAMIC_TOOLS.md**: Comprehensive guide
  - [ ] User guide for LLMs
  - [ ] Capability reference table
  - [ ] Security model explanation
  - [ ] Example tool specs
  - [ ] Best practices
- [ ] **CLAUDE.md**: Add meta-tool descriptions
- [ ] **docs/ARCHITECTURE.md**: Update with new components
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

1. **Signature Key Management**: Where to store HMAC secret key?
   - Option A: User-specific key in `~/.instrmcp/secret.key`
   - Option B: System-wide key (less secure)
   - Option C: Per-tool key derivation

2. **Cross-Notebook Tool Sharing**: Should tools registered in one notebook be available in all notebooks?
   - Option A: Global registry (current design)
   - Option B: Per-notebook registry
   - Option C: Hybrid with explicit sharing

3. **Tool Versioning**: How to handle multiple versions of same tool?
   - Option A: Only latest version (current design)
   - Option B: Side-by-side versions (complexity)
   - Option C: Version pinning in invocations

4. **Network Capability Granularity**: Should `cap:network.egress` be more fine-grained?
   - Option A: Single capability (simpler)
   - Option B: Per-domain whitelist (more secure)
   - Option C: Per-protocol (HTTP, WebSocket, etc.)

5. **Capability Inheritance**: Should tools be able to grant capabilities to called tools?
   - Option A: No inheritance (current design)
   - Option B: Explicit delegation
   - Option C: Automatic subset

---

## 📝 Notes

- This is a major feature requiring careful security review at each phase
- User education critical: consent UI must be clear and informative
- Performance impact should be minimal (sandbox overhead <10ms)
- Backward compatibility maintained (existing tools unaffected)
- Feature can be disabled via server configuration if needed

---

**Last Updated**: 2025-10-01
**Next Review**: After Phase 1 completion
