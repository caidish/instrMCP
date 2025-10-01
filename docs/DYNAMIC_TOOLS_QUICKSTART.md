# Dynamic Tools Quick Start Guide

## Overview

Dynamic tools allow LLMs to create custom tools at runtime in instrMCP. This guide shows you how to test the feature using MCP Inspector.

## Prerequisites

1. Install instrMCP: `pip install -e .`
2. Start Jupyter with MCP server in unsafe mode:
   ```bash
   instrmcp jupyter --unsafe --port 3000
   ```

## Using MCP Inspector

### Step 1: Verify Meta-Tools Are Available

Open MCP Inspector and look for these 6 new tools:
- `dynamic_register_tool`
- `dynamic_update_tool`
- `dynamic_revoke_tool`
- `dynamic_list_tools`
- `dynamic_inspect_tool`
- `dynamic_registry_stats`

### Step 2: Create Your First Tool (Minimal)

Use `dynamic_register_tool` with only the required fields:

**Parameters:**
```
name: "my_first_tool"
source_code: "def my_first_tool(x):\n    return x * 2"
```

That's it! The tool will be created with defaults:
- version: `"1.0.0"`
- description: `"Dynamic tool: my_first_tool"`
- author: `"unknown"`
- capabilities: `[]` (empty - capabilities are for documentation only, not enforced)
- parameters: `[]`
- returns: `{"type": "object", "description": "Result"}`

**Expected Response:**
```json
{
  "status": "success",
  "message": "Tool 'my_first_tool' registered successfully",
  "tool_name": "my_first_tool",
  "version": "1.0.0"
}
```

### Step 3: Execute Your Tool

Now you can call `my_first_tool` directly via MCP Inspector:

**Parameters:**
```
x: 5
```

**Expected Response:**
```json
{
  "status": "success",
  "result": 10
}
```

### Step 4: Create a Tool with Full Specifications

For more control, use all optional parameters:

**Parameters:**
```
name: "analyze_data"
source_code: "def analyze_data(numbers):\n    return {'sum': sum(numbers), 'count': len(numbers), 'mean': sum(numbers)/len(numbers)}"
version: "1.0.0"
description: "Analyze a list of numbers and return statistics"
author: "data_team"
capabilities: ["cap:python.builtin"]
parameters: [{"name": "numbers", "type": "array", "description": "List of numbers to analyze", "required": true}]
returns: {"type": "object", "description": "Statistics object with sum, count, and mean"}
tags: ["statistics", "analysis"]
```

**Important:** When entering JSON fields in MCP Inspector:
- Enter JSON objects/arrays directly (not as quoted strings)
- For example: `["cap:python.builtin"]` NOT `'["cap:python.builtin"]'`

### Step 5: List All Tools

Call `dynamic_list_tools` to see all registered tools:

**Parameters:** (none)

**Expected Response:**
```json
{
  "status": "success",
  "count": 2,
  "tools": [
    {
      "name": "analyze_data",
      "version": "1.0.0",
      "description": "Analyze a list of numbers and return statistics",
      "author": "data_team",
      "created_at": "2025-10-01T12:00:00Z",
      "updated_at": "2025-10-01T12:00:00Z"
    },
    {
      "name": "my_first_tool",
      "version": "1.0.0",
      "description": "Dynamic tool: my_first_tool",
      "author": "unknown",
      "created_at": "2025-10-01T12:01:00Z",
      "updated_at": "2025-10-01T12:01:00Z"
    }
  ]
}
```

### Step 6: Inspect a Tool

Call `dynamic_inspect_tool` to see the full specification:

**Parameters:**
```
name: "my_first_tool"
```

**Expected Response:**
```json
{
  "status": "success",
  "tool": {
    "name": "my_first_tool",
    "version": "1.0.0",
    "description": "Dynamic tool: my_first_tool",
    "author": "unknown",
    "created_at": "2025-10-01T12:00:00Z",
    "updated_at": "2025-10-01T12:00:00Z",
    "capabilities": ["cap:python.builtin"],
    "parameters": [],
    "returns": {"type": "object", "description": "Result"},
    "source_code": "def my_first_tool(x):\n    return x * 2",
    "examples": [],
    "tags": []
  }
}
```

### Step 7: Update a Tool

Call `dynamic_update_tool` to modify an existing tool:

**Parameters:**
```
name: "my_first_tool"
version: "2.0.0"
description: "Updated tool that triples the input"
source_code: "def my_first_tool(x):\n    return x * 3"
```

### Step 8: Revoke a Tool

Call `dynamic_revoke_tool` to permanently delete a tool:

**Parameters:**
```
name: "my_first_tool"
reason: "No longer needed"
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Tool 'my_first_tool' revoked successfully",
  "tool_name": "my_first_tool",
  "version": "2.0.0"
}
```

## Advanced: Tools with Notebook Access

Create a tool that accesses variables from your Jupyter notebook:

**In your notebook:**
```python
multiplier = 10
import numpy as np
```

**Register tool:**
```
name: "use_notebook_var"
source_code: "def use_notebook_var(x):\n    return x * multiplier"
capabilities: ["cap:notebook.read"]
```

**Execute:**
```
x: 5
```

**Expected:** `{"status": "success", "result": 50}`

## File System

Your tools are stored at:
- Registry: `~/.instrmcp/registry/{tool_name}.json`
- Audit log: `~/.instrmcp/audit/tool_audit.log`

Tools persist across server restarts - they're automatically reloaded!

## Troubleshooting

### Error: "Invalid JSON in parameters"

**Problem:** You entered JSON as a quoted string instead of a JSON object.

**Wrong:**
```
capabilities: '["cap:python.builtin"]'
```

**Right:**
```
capabilities: ["cap:python.builtin"]
```

### Error: "Tool source code must define a function named..."

**Problem:** Your function name doesn't match the tool name.

**Wrong:**
```
name: "my_tool"
source_code: "def different_name():\n    return 42"
```

**Right:**
```
name: "my_tool"
source_code: "def my_tool():\n    return 42"
```

### Error: "Description too short"

**Problem:** Auto-generated description is fine, but if you provide one, it must be at least 10 characters.

**Solution:** Either omit description (uses default) or provide a longer one.

## Next Steps

- Explore more complex tools with NumPy, SciPy
- Create tools that process measurement data
- Build analysis pipelines with multiple tools
- Share tool specifications with your team

For more details, see [TODO.md](../TODO.md) for the full testing checklist.
