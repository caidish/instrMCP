# TODO Update: Add New Cell Manipulation Tools to MCP Server

## Overview
Implement three new cell manipulation tools to enhance the Jupyter MCP extension:
1. **`add_new_cell`** - Add a new cell at specified position
2. **`delete_editing_cell`** - Delete the currently active cell
3. **`apply_patch`** - Apply partial changes to cell content (more efficient than full replacement)

## Architecture Summary
The system uses a TypeScript↔Python bridge pattern:
- **TypeScript extension** (`index.ts`) runs in JupyterLab frontend
- **Python bridge** (`active_cell_bridge.py`) handles kernel-side communication
- **MCP server** (`mcp_server.py`) exposes tools to Claude
- **STDIO proxy** (`stdio_proxy.py`) bridges to Claude Desktop/Code

## Implementation Details

### 1. TypeScript Extension Enhancement (`instrmcp/extensions/jupyterlab/src/index.ts`)
Add three new message handlers in the comm protocol:
- `add_cell` - Insert new cell using NotebookActions API
- `delete_cell` - Delete active cell using notebook.content.deleteCells()
- `apply_patch` - Apply text replacement using simple old/new format

```typescript
// Handle add_cell request
if (data.type === 'add_cell') {
  const cellType = data.cell_type || 'code';
  const position = data.position || 'below';
  const content = data.content || '';
  // Create and insert new cell model
  // Update active cell index
  // Send response back
}

// Handle delete_cell request
if (data.type === 'delete_cell') {
  // Use NotebookActions.deleteCells()
  // Handle edge cases (last cell, only cell)
  // Send response back
}

// Handle apply_patch request
if (data.type === 'apply_patch') {
  // Get current cell content
  // Apply simple string replacement
  // Update cell model
  // Send response back
}
```

### 2. Python Backend Functions (`instrmcp/servers/jupyter_qcodes/active_cell_bridge.py`)
Add three new functions:

```python
def add_new_cell(cell_type='code', position='below', content='', timeout_s=2.0):
    """Add a new cell relative to current cell."""
    # Send request to frontend via comm
    # Wait for response
    # Return success/error status

def delete_editing_cell(timeout_s=2.0):
    """Delete the currently active cell."""
    # Send delete request to frontend
    # Handle response
    # Return status

def apply_patch(old_text, new_text, timeout_s=2.0):
    """Apply a simple text replacement patch."""
    # Get current content
    # Replace old_text with new_text
    # Update cell via comm
    # Return status
```

### 3. QCoDeS Tools Integration (`instrmcp/servers/jupyter_qcodes/tools.py`)
Add async wrappers for the new functions:

```python
async def add_new_cell(self, cell_type='code', position='below', content=''):
    """Add a new cell in the notebook."""
    # Call active_cell_bridge.add_new_cell()
    # Return formatted result

async def delete_editing_cell(self):
    """Delete the currently editing cell."""
    # Call active_cell_bridge.delete_editing_cell()
    # Return formatted result

async def apply_patch(self, old_text: str, new_text: str):
    """Apply a patch to the current cell."""
    # Call active_cell_bridge.apply_patch()
    # Return formatted result
```

### 4. MCP Server Tool Registration (`instrmcp/servers/jupyter_qcodes/mcp_server.py`)
Register the new tools (unsafe mode only):

```python
if not self.safe_mode:
    @self.mcp.tool()
    async def add_new_cell(
        cell_type: str = "code",
        position: str = "below",
        content: str = ""
    ) -> List[TextContent]:
        """Add a new cell in the notebook."""

    @self.mcp.tool()
    async def delete_editing_cell() -> List[TextContent]:
        """Delete the currently editing cell."""

    @self.mcp.tool()
    async def apply_patch(
        old_text: str,
        new_text: str
    ) -> List[TextContent]:
        """Apply a patch to the current cell content."""
```

### 5. STDIO Proxy Updates (`instrmcp/tools/stdio_proxy.py`)
Add proxy functions for Claude Desktop/Code:

```python
@mcp.tool()
async def add_new_cell(cell_type: str = "code", position: str = "below", content: str = "") -> list[TextContent]:
    result = await proxy.call("add_new_cell", cell_type=cell_type, position=position, content=content)
    return [TextContent(type="text", text=str(result))]

@mcp.tool()
async def delete_editing_cell() -> list[TextContent]:
    result = await proxy.call("delete_editing_cell")
    return [TextContent(type="text", text=str(result))]

@mcp.tool()
async def apply_patch(old_text: str, new_text: str) -> list[TextContent]:
    result = await proxy.call("apply_patch", old_text=old_text, new_text=new_text)
    return [TextContent(type="text", text=str(result))]
```

### 6. Documentation Update (`CLAUDE.md`)
Add the new tools to the documentation:
- Document in the "Unsafe Mode Tools" section
- Add usage examples
- Note that these require `%mcp_unsafe` mode

## Design Decisions

1. **Patch Format**: Use simple old/new text replacement instead of complex diff formats
   - Easy to use and understand
   - Sufficient for most use cases
   - Can handle multiple replacements in sequence

2. **Position Options**: Support "above" and "below" for cell insertion
   - Default to "below" (most intuitive)
   - Relative to current active cell

3. **Cell Types**: Support "code" and "markdown"
   - Default to "code" (most common)
   - Raw cells not supported initially

4. **Safety**: All three tools require unsafe mode
   - Consistent with `execute_editing_cell`
   - Prevents accidental cell manipulation

## Testing Strategy
1. Test cell addition in various positions
2. Test deletion of first/last/only cells
3. Test patch application with various text patterns
4. Verify proper error handling
5. Test mode switching (safe/unsafe)

## Files to Modify
- [x] `instrmcp/extensions/jupyterlab/src/index.ts` - TypeScript handlers
- [x] `instrmcp/servers/jupyter_qcodes/active_cell_bridge.py` - Python functions
- [x] `instrmcp/servers/jupyter_qcodes/tools.py` - Tool wrappers
- [x] `instrmcp/servers/jupyter_qcodes/mcp_server.py` - Tool registration
- [x] `instrmcp/tools/stdio_proxy.py` - Proxy functions
- [x] `CLAUDE.md` - Documentation update
- [x] `instrmcp/extensions/jupyterlab/package.json` - Added postbuild script

## Implementation Status

This implementation will significantly enhance the MCP server's ability to manipulate Jupyter notebook cells programmatically while maintaining consistency with the existing architecture.

## Build and Installation Notes

After modifying the TypeScript extension:

1. Run `cd instrmcp/extensions/jupyterlab && jlpm run build`
2. The postbuild script automatically copies files to `mcp_active_cell_bridge/labextension/`
3. Run `pip install -e . --force-reinstall --no-deps` to update installation
4. Restart JupyterLab completely

For new users forking the repo:

- Simply run `pip install -e .` followed by `instrmcp-setup`
- All built files are included in the repository