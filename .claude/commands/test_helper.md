---
description: Interactive MCP server testing helper for tools and resources
allowed-tools: Read, Grep, Glob, AskUserQuestion, TodoWrite
argument-hint: [category]
---

# MCP Server Interactive Test Helper

You are helping the user interactively test the InstrMCP server. You are presumably already connected to a user-launched instrmcp session, and in unsafe mode.

## Context

- Server metadata: @instrmcp/config/metadata_baseline.yaml
- The user is running the MCP server in **unsafe mode** with consent dialogs
- Test notebook: "TestNotebook.ipynb" is open in JupyterLab
- You need to interact with instrmcp, and print the tool result to screen for the user to be able to verify it.

## Test Categories

The user can specify a category to test: `$ARGUMENTS`

Available categories:
- `all` - Test everything systematically
- `core` - Test mcp_list_resources, mcp_get_resource
- `notebook` - Test notebook_* tools (safe and unsafe)
- `qcodes` - Test qcodes_* tools
- `measureit` - Test measureit_* tools
- `database` - Test database_* tools
- `resources` - Test all resource templates

If no category specified, test all.

## Testing Workflow

For each tool/resource category, follow this workflow:

### 1. Description Review
First, read the tool description from metadata_baseline.yaml and ask:

```
Use AskUserQuestion to ask:
"For [tool_name]: Is this description clear and accurate?"
Options:
- "Yes, clear and accurate"
- "Needs improvement" (ask for details)
- "Skip this tool"
```

### 2. Tool Execution Test
If the description is approved, attempt to call the tool with sensible defaults:

- For read-only tools: Execute directly and report results
- For unsafe tools: Warn the user that consent dialog will appear, then execute
- For tools requiring specific state (e.g., running sweep): Ask user to set up the state first
- For testing some of the tools, you may need to ask the user to run some code, or you use MCP to run code. 

### 3. Result Verification
After execution, ask the user to verify:

```
Use AskUserQuestion to ask:
"Did [tool_name] behave as expected?"
Options:
- "Yes, working correctly"
- "Bug found" (document the issue)
- "Unexpected behavior" (document details)
```

### 4. Bug Documentation
If any issues found, document them clearly:
- Tool name
- Expected behavior
- Actual behavior
- Error messages (if any)
- Reproduction steps

## Tool Test Order

### Core MCP Tools
1. `mcp_list_resources` - List all available resources
2. `mcp_get_resource` - Fetch a specific resource (test with measureit_sweep1d_template)

### Notebook Safe Tools
3. `notebook_server_status` - Check server connectivity
4. `notebook_read_active_cell` - Read current cell
5. `notebook_read_active_cell_output` - Read cell output
6. `notebook_read_content` - Read multiple cells
7. `notebook_list_variables` - List namespace variables
8. `notebook_read_variable` - Read specific variable (if any exist)
9. `notebook_move_cursor` - Move to different cell

### QCodes Tools
10. `qcodes_instrument_info` - Get instrument info (use "*" to list all)
11. `qcodes_get_parameter_values` - Get parameter values
12. `qcodes_get_parameter_info` - Get parameter metadata

### MeasureIt Tools (if enabled)
13. `measureit_get_status` - Check sweep status
14. `measureit_wait_for_sweep` - Wait for sweep (needs running sweep)
15. `measureit_kill_sweep` - Kill sweep (needs running sweep)

### Database Tools (if enabled)
16. `database_list_all_available_db` - List databases
17. `database_list_experiments` - List experiments
18. `database_get_database_stats` - Get database stats
19. `database_get_dataset_info` - Get dataset info

### Notebook Unsafe Tools (requires consent)
20. `notebook_add_cell` - Add new cell
21. `notebook_update_editing_cell` - Update cell content
22. `notebook_apply_patch` - Patch cell content
23. `notebook_execute_active_cell` - Execute cell
24. `notebook_delete_cell` - Delete cell

### Resource Templates
25. Test fetching each resource template via mcp_get_resource

## Progress Tracking

Use TodoWrite to track testing progress. Create todos for each category and mark them complete as you go.

## Summary Report

After testing, provide a summary:
- Total tools tested
- Tools working correctly
- Tools with issues (list each)
- Missing or unclear descriptions
- Suggestions for improvement

## Important Notes

- Always use `AskUserQuestion` to interact with the user for test results
- For unsafe tools, warn the user before calling (consent dialog will appear)
- If a tool fails, capture the error message for the bug report
- Some tools require specific state (e.g., instruments connected, sweep running)
- The user can skip any test by selecting "Skip"

Begin by confirming with the user which category to test, then proceed systematically.
