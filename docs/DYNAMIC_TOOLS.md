# Dynamic Tools User Guide

**Version:** 2.0.0
**Status:** Production Ready

## Table of Contents

1. [Overview](#overview)
2. [How LLMs Can Create Tools](#how-llms-can-create-tools)
3. [Capability Labels](#capability-labels)
4. [Security Model](#security-model)
5. [Tool Specification](#tool-specification)
6. [Meta-Tools Reference](#meta-tools-reference)
7. [Best Practices](#best-practices)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Dynamic tools enable Large Language Models (LLMs) to create custom MCP tools at runtime within instrMCP. This allows AI assistants to:

- **Extend functionality** - Create new capabilities on-demand
- **Automate workflows** - Build tools for repetitive tasks
- **Analyze data** - Create custom analysis functions
- **Access notebook state** - Tools can read variables from the Jupyter kernel

### Key Features

- **6 Meta-Tools**: register, update, revoke, list, inspect, registry_stats
- **User Consent**: All tool registrations require user approval via JupyterLab dialog
- **Persistent Registry**: Tools saved to `~/.instrmcp/registry/` and reloaded on server start
- **Audit Trail**: All operations logged to `~/.instrmcp/audit/tool_audit.log`
- **Freeform Capabilities**: Tag tools with descriptive labels for discovery
- **Optional JSON Correction**: Auto-fix malformed JSON via MCP sampling (opt-in)

### Quick Start

See [DYNAMIC_TOOLS_QUICKSTART.md](DYNAMIC_TOOLS_QUICKSTART.md) for a 5-minute getting started guide.

---

## How LLMs Can Create Tools

### Basic Workflow

1. **LLM decides** a new tool is needed
2. **LLM calls** `dynamic_register_tool` with tool specification
3. **Backend validates** the spec and requests user consent
4. **User approves** via JupyterLab consent dialog (shows source code)
5. **Tool is registered** and immediately available for use
6. **LLM invokes** the new tool to accomplish the task

### Minimal Registration

Only 2 fields are required:

```python
dynamic_register_tool(
    name="simple_multiplier",
    source_code="def simple_multiplier(x):\n    return x * 10"
)
```

### Complete Registration

Provide full metadata for better documentation:

```python
dynamic_register_tool(
    name="analyze_data",
    version="1.0.0",
    description="Analyze array data and return statistical summary",
    author="claude_assistant",
    capabilities=["cap:numpy.stats", "data-processing"],
    parameters=[
        {
            "name": "data",
            "type": "array",
            "description": "Input data array",
            "required": True
        }
    ],
    returns={
        "type": "object",
        "description": "Statistical summary with mean, std, min, max"
    },
    source_code="""
import numpy as np

def analyze_data(data):
    \"\"\"Calculate basic statistics for data array.\"\"\"
    arr = np.array(data)
    return {
        'mean': float(np.mean(arr)),
        'std': float(np.std(arr)),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'count': len(arr)
    }
""",
    examples=[
        "analyze_data([1, 2, 3, 4, 5])",
        "analyze_data(measurement_results)"
    ],
    tags=["statistics", "numpy", "analysis"]
)
```

---

## Capability Labels

### What Are Capabilities?

Capabilities are **freeform documentation labels** that describe what a tool does or needs. In v2.0.0, they are **NOT enforced** - they're purely for:

- **Discovery**: Filter tools by capability (`dynamic_list_tools(capability="cap:numpy")`)
- **Transparency**: Show users what libraries/features a tool uses
- **Documentation**: Help LLMs understand tool dependencies

### Capability Format (Suggested)

While any non-empty string is valid, we suggest this format:

```
cap:library.feature
```

**Examples:**
- `cap:numpy.array` - Uses NumPy arrays
- `cap:scipy.optimize` - Uses SciPy optimization
- `cap:qcodes.read` - Reads QCodes instrument parameters
- `cap:qcodes.write` - Writes to QCodes instruments
- `cap:matplotlib.plot` - Creates plots with Matplotlib
- `cap:custom.analysis` - Custom analysis capability

### Freeform Labels

You can also use simple descriptive labels:

```python
capabilities=["data-processing", "instrument-control", "visualization"]
```

### Future (v3.0.0)

Capability **enforcement** is planned for v3.0.0:
- Taxonomy of standard capabilities
- Runtime validation
- Mode-based restrictions (safe mode blocks write capabilities)

For now, capabilities are labels only - use them to describe your tools clearly.

---

## Security Model

### Consent-Based Security

Dynamic tools use a **user consent model** rather than sandboxing:

1. **User Review**: All source code shown in consent dialog before approval
2. **Informed Decision**: User sees capabilities, author, and code
3. **Always Allow**: Users can grant permanent permission to trusted authors
4. **Audit Trail**: All approvals logged for review

### What Users See

When you register a tool, the consent dialog shows:

```
┌─────────────────────────────────────────┐
│  Tool Registration Request              │
├─────────────────────────────────────────┤
│  Name: analyze_data                     │
│  Author: claude_assistant               │
│  Version: 1.0.0                         │
│                                         │
│  Capabilities:                          │
│  • cap:numpy.stats                      │
│  • data-processing                      │
│                                         │
│  Source Code:                           │
│  ┌────────────────────────────────┐    │
│  │ import numpy as np             │    │
│  │                                │    │
│  │ def analyze_data(data):        │    │
│  │     arr = np.array(data)       │    │
│  │     return {                   │    │
│  │         'mean': float(...),    │    │
│  │         ...                    │    │
│  │     }                          │    │
│  └────────────────────────────────┘    │
│                                         │
│  ☐ Always allow tools from this author │
│                                         │
│  [Allow]  [Decline]                     │
└───────────────────────────────┘
```

### Session-Only Permissions

By default, "always allow" permissions are **session-only**:
- Stored in memory during server lifetime
- **Cleared on server restart**
- User must re-approve after restart

This ensures fresh consent for each session while allowing convenience during active work.

### Bypass Mode (Testing Only)

For automated testing, set environment variable:

```bash
export INSTRMCP_CONSENT_BYPASS=1
instrmcp jupyter --unsafe --port 3000
```

**WARNING**: This auto-approves ALL tool registrations. Use only in trusted environments.

---

## Tool Specification

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Tool name (snake_case, max 64 chars) |
| `source_code` | string | Python function source code (max 10KB) |

### Optional Fields (with defaults)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | string | `"1.0.0"` | Semantic version |
| `description` | string | Auto-generated | Tool description (10-500 chars) |
| `author` | string | `"unknown"` | Author identifier |
| `capabilities` | array | `[]` | Capability labels |
| `parameters` | array | `[]` | Parameter specifications |
| `returns` | object | Auto-generated | Return type specification |
| `examples` | array | `None` | Usage examples |
| `tags` | array | `None` | Searchable tags |

### Parameter Specification

Each parameter in the `parameters` array:

```python
{
    "name": "param_name",        # Required: snake_case
    "type": "string",            # Required: string|number|boolean|array|object
    "description": "...",        # Required: parameter description
    "required": True,            # Optional: default False
    "default": "value",          # Optional: default value
    "enum": ["a", "b", "c"]      # Optional: allowed values
}
```

### Returns Specification

```python
{
    "type": "object",            # Type of return value
    "description": "..."         # What the tool returns
}
```

### Source Code Requirements

- Must be valid Python syntax
- Function name must match tool name
- Maximum 10KB (10,000 characters)
- Can import standard libraries and installed packages
- Has access to Jupyter kernel namespace

---

## Meta-Tools Reference

### `dynamic_register_tool`

Register a new dynamic tool.

**Parameters:**
- `name` (required): Tool name
- `source_code` (required): Python function code
- `version`, `description`, `author`, `capabilities`, `parameters`, `returns`, `examples`, `tags` (optional)

**Returns:**
```json
{
    "status": "success",
    "message": "Tool 'my_tool' registered successfully",
    "tool_name": "my_tool"
}
```

**Errors:**
- Validation error if spec is invalid
- Conflict error if tool name exists
- Consent denied if user declines

---

### `dynamic_update_tool`

Update an existing tool (requires consent).

**Parameters:**
- `name` (required): Existing tool name
- `version` (required): New version number
- Other fields (optional): Updated values

**Returns:**
```json
{
    "status": "success",
    "message": "Tool 'my_tool' updated successfully",
    "tool_name": "my_tool"
}
```

---

### `dynamic_revoke_tool`

Delete a tool from registry (no consent required).

**Parameters:**
- `name` (required): Tool name to delete
- `reason` (optional): Reason for revocation

**Returns:**
```json
{
    "status": "success",
    "message": "Tool 'my_tool' revoked successfully",
    "tool_name": "my_tool"
}
```

---

### `dynamic_list_tools`

List all registered tools with optional filtering.

**Parameters:**
- `tag` (optional): Filter by tag
- `capability` (optional): Filter by capability
- `author` (optional): Filter by author

**Returns:**
```json
{
    "tools": [
        {
            "name": "my_tool",
            "version": "1.0.0",
            "description": "...",
            "author": "claude",
            "capabilities": ["cap:numpy"],
            "tags": ["analysis"],
            "created_at": "2025-10-01T12:00:00Z",
            "updated_at": "2025-10-01T12:00:00Z"
        }
    ],
    "count": 1
}
```

---

### `dynamic_inspect_tool`

Get full details of a specific tool.

**Parameters:**
- `name` (required): Tool name

**Returns:**
```json
{
    "name": "my_tool",
    "version": "1.0.0",
    "description": "...",
    "author": "claude",
    "created_at": "2025-10-01T12:00:00Z",
    "updated_at": "2025-10-01T12:00:00Z",
    "capabilities": ["cap:numpy"],
    "parameters": [...],
    "returns": {...},
    "source_code": "def my_tool(...):\n    ...",
    "examples": [...],
    "tags": [...]
}
```

---

### `dynamic_registry_stats`

Get registry statistics.

**Returns:**
```json
{
    "total_tools": 5,
    "by_author": {
        "claude": 3,
        "user": 2
    },
    "by_capability": {
        "cap:numpy": 2,
        "cap:qcodes.read": 1
    },
    "by_tag": {
        "analysis": 3,
        "automation": 2
    }
}
```

---

## Best Practices

### 1. Naming Convention

✅ **Good:**
```
analyze_resonator_data
get_instrument_status
plot_measurement_results
```

❌ **Bad:**
```
analyzeData  # camelCase not allowed
my-tool      # hyphens not allowed
Tool1        # capitals not allowed
```

### 2. Clear Descriptions

✅ **Good:**
```python
description="Calculate Q-factor from resonator frequency sweep data using Lorentzian fit"
```

❌ **Bad:**
```python
description="does stuff"  # Too vague, under 10 chars
```

### 3. Specify Parameters

If your function has arguments, **always specify parameters**:

✅ **Good:**
```python
source_code="def analyze(data, threshold):\n    ...",
parameters=[
    {"name": "data", "type": "array", "description": "Input data", "required": True},
    {"name": "threshold", "type": "number", "description": "Detection threshold", "required": False, "default": 0.5}
]
```

❌ **Bad:**
```python
source_code="def analyze(data, threshold):\n    ...",
parameters=[]  # Missing parameter specs!
```

### 4. Use Capabilities for Discovery

Tag tools with descriptive capabilities:

```python
capabilities=[
    "cap:numpy.array",      # Uses NumPy
    "cap:scipy.optimize",   # Uses SciPy optimization
    "data-processing",      # General category
    "resonator-analysis"    # Domain-specific
]
```

### 5. Access Jupyter Namespace

Tools can access variables from the Jupyter kernel:

```python
source_code="""
def use_global_config():
    # Access variable 'config' from Jupyter notebook
    return config['setting']
"""
```

### 6. Error Handling

Include error handling in your tools:

```python
source_code="""
def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except Exception as e:
        return {"error": str(e)}
"""
```

### 7. Version Updates

When updating tools, increment the version:

```python
dynamic_update_tool(
    name="my_tool",
    version="1.1.0",  # Increment from 1.0.0
    source_code="..."  # Updated code
)
```

### 8. Document with Examples

Provide usage examples:

```python
examples=[
    "analyze_data([1, 2, 3, 4, 5])",
    "analyze_data(measurement_results)",
    "analyze_data(sweep_data, threshold=0.8)"
]
```

---

## Examples

### Example 1: Simple Calculator

```python
dynamic_register_tool(
    name="calculate_mean",
    description="Calculate arithmetic mean of a list of numbers",
    capabilities=["cap:python.builtin"],
    parameters=[{
        "name": "numbers",
        "type": "array",
        "description": "List of numbers",
        "required": True
    }],
    returns={
        "type": "number",
        "description": "Arithmetic mean"
    },
    source_code="""
def calculate_mean(numbers):
    return sum(numbers) / len(numbers)
"""
)
```

### Example 2: NumPy Analysis

```python
dynamic_register_tool(
    name="find_peaks",
    description="Find peaks in signal data using NumPy",
    author="analysis_bot",
    capabilities=["cap:numpy.array", "signal-processing"],
    parameters=[
        {
            "name": "signal",
            "type": "array",
            "description": "Signal data array",
            "required": True
        },
        {
            "name": "threshold",
            "type": "number",
            "description": "Minimum peak height",
            "required": False,
            "default": 0.5
        }
    ],
    returns={
        "type": "object",
        "description": "Peak indices and values"
    },
    source_code="""
import numpy as np

def find_peaks(signal, threshold=0.5):
    arr = np.array(signal)
    peaks = []
    for i in range(1, len(arr)-1):
        if arr[i] > arr[i-1] and arr[i] > arr[i+1] and arr[i] > threshold:
            peaks.append({"index": i, "value": float(arr[i])})
    return {"peaks": peaks, "count": len(peaks)}
""",
    examples=[
        "find_peaks([0, 1, 0, 2, 0, 3, 0])",
        "find_peaks(signal_data, threshold=1.0)"
    ],
    tags=["signal", "analysis", "peaks"]
)
```

### Example 3: Accessing Jupyter Variables

```python
dynamic_register_tool(
    name="analyze_current_dataset",
    description="Analyze the dataset currently loaded in Jupyter notebook",
    capabilities=["cap:numpy.stats", "notebook-integration"],
    source_code="""
import numpy as np

def analyze_current_dataset():
    # Access 'dataset' variable from Jupyter kernel
    if 'dataset' not in globals():
        return {"error": "No dataset found in notebook"}
    
    data = np.array(dataset)
    return {
        "mean": float(np.mean(data)),
        "std": float(np.std(data)),
        "shape": list(data.shape)
    }
"""
)
```

### Example 4: QCodes Integration

```python
dynamic_register_tool(
    name="quick_iv_sweep",
    description="Perform I-V sweep using QCodes instruments",
    author="qcodes_helper",
    capabilities=["cap:qcodes.read", "cap:qcodes.write", "measurement"],
    parameters=[
        {
            "name": "start_voltage",
            "type": "number",
            "description": "Start voltage in V",
            "required": True
        },
        {
            "name": "stop_voltage",
            "type": "number",
            "description": "Stop voltage in V",
            "required": True
        },
        {
            "name": "num_points",
            "type": "number",
            "description": "Number of measurement points",
            "required": False,
            "default": 50
        }
    ],
    returns={
        "type": "object",
        "description": "Measurement results with voltages and currents"
    },
    source_code="""
import numpy as np

def quick_iv_sweep(start_voltage, stop_voltage, num_points=50):
    # Access QCodes station from Jupyter kernel
    voltages = np.linspace(start_voltage, stop_voltage, num_points)
    currents = []
    
    for v in voltages:
        dac.voltage(v)  # Set voltage
        time.sleep(0.01)  # Wait for settling
        i = dmm.current()  # Read current
        currents.append(i)
    
    return {
        "voltages": voltages.tolist(),
        "currents": currents,
        "num_points": len(voltages)
    }
""",
    tags=["qcodes", "measurement", "iv-sweep"]
)
```

---

## Troubleshooting

### Tool Registration Fails

**Error: "Invalid tool name"**
- Tool names must be snake_case (lowercase with underscores)
- Start with letter or underscore
- Max 64 characters

**Error: "Tool already exists"**
- Use `dynamic_update_tool` to modify existing tools
- Or `dynamic_revoke_tool` first, then re-register

**Error: "Source code has syntax error"**
- Check Python syntax carefully
- Function name must match tool name
- Test code in Jupyter cell first

### Consent Dialog Doesn't Appear

1. Check JupyterLab extension is installed:
   ```bash
   jupyter labextension list | grep mcp
   ```

2. Check server is in unsafe mode:
   ```bash
   instrmcp jupyter --unsafe --port 3000
   ```

3. Check browser console for errors (F12)

### Tool Execution Fails

**Error: "Name 'X' is not defined"**
- Import required libraries in source code
- Or ensure variable exists in Jupyter kernel

**Error: "Tool not found"**
- Check tool is registered: `dynamic_list_tools()`
- Server may need restart after registration

### "Always Allow" Not Working

- "Always allow" is session-only by default
- Cleared on server restart
- Check checkbox is selected in consent dialog

---

## Additional Resources

- [DYNAMIC_TOOLS_QUICKSTART.md](DYNAMIC_TOOLS_QUICKSTART.md) - Quick start guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - General troubleshooting
- [GitHub Issues](https://github.com/caidish/instrMCP/issues) - Report bugs

---

**Version:** 2.0.0  
**Last Updated:** 2025-10-01  
**Status:** Production Ready
