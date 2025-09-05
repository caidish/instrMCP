# Testing update_editing_cell Functionality

## Overview
The `update_editing_cell` tool allows programmatically updating the content of the currently editing cell in JupyterLab through the MCP protocol.

## Prerequisites
1. JupyterLab 4.2+ with the Active Cell Bridge extension installed
2. Virtual environment activated
3. Kernel extension loaded

## Testing Steps

### 1. Start JupyterLab and Create Notebook
```bash
cd /Users/caijiaqi/GitHub/instrMCP/servers/jupyter_qcodes
source /Users/caijiaqi/GitHub/instrMCP/venv/bin/activate
jupyter lab
```

### 2. Load Kernel Extension
In a notebook cell, run:
```python
%load_ext servers.jupyter_qcodes.jupyter_mcp_extension
```

You should see: "🚀 QCoDeS MCP Server starting..."

### 3. Test Basic Cell Update
In a new cell, test the MCP tool:
```python
# This should work if everything is set up correctly
result = await get_tools()['update_editing_cell']("print('Hello from MCP!')")
print(result)
```

### 4. Test with Complex Code
```python
complex_code = '''
import numpy as np
import matplotlib.pyplot as plt

# Generate sample data
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Create plot
plt.figure(figsize=(8, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.xlabel('X values')
plt.ylabel('Y values')
plt.title('Sine Wave')
plt.grid(True)
plt.show()
'''

result = await get_tools()['update_editing_cell'](complex_code)
print(result)
```

### 5. Verify Cell Content Changed
After running the update tool, check that the current cell content has been replaced with the new code.

## Expected Console Output

### Browser Console (F12)
```
MCP Active Cell Bridge extension activated
MCP Active Cell Bridge: Comm opened and ready
MCP Active Cell Bridge: Updated cell content (XXX chars)
```

### Kernel Output
```json
{
  "success": true,
  "message": "Update request sent to 1 frontend(s)",
  "content_length": 123,
  "request_id": "uuid-here",
  "active_comms": 1,
  "successful_sends": 1
}
```

## Troubleshooting

### "No active comm connections to frontend"
- Ensure JupyterLab extension is installed: `jupyter labextension list`
- Check browser console for comm errors
- Restart kernel and reload browser

### "Cell updating not available in standalone mode"
- You're using claude_launcher in standalone mode
- Switch to Jupyter proxy mode

### Extension Not Loading
- Rebuild extension: `jlpm run build:lib`
- Reinstall: `jupyter labextension install .`
- Clear browser cache and reload

## Architecture

The update flow works as follows:
1. `update_editing_cell()` MCP tool called
2. `tools.update_editing_cell()` validates input
3. `active_cell_bridge.update_active_cell()` sends comm message
4. Frontend extension receives message via `comm.onMsg`
5. `handleCellUpdate()` updates cell using `cell.model.sharedModel.setSource()`
6. Success response sent back to kernel