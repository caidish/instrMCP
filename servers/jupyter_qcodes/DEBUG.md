# Debug Guide for JupyterLab MCP Extension

## Quick Debug Checklist

### 1. Verify Extension Installation
```bash
jupyter labextension list | grep mcp-active-cell-bridge
# Should show: mcp-active-cell-bridge (enabled, local)
```

### 2. Check IPython Extension Load
In Jupyter notebook:
```python
%load_ext servers.jupyter_qcodes.jupyter_mcp_extension
# Should show: 🚀 QCoDeS MCP Server starting...
```

### 3. Browser Console Debugging
Open Developer Tools in JupyterLab (F12) and check Console tab for:

**Expected Messages:**
- `"MCP Active Cell Bridge extension activated"` - Extension loaded successfully
- `"MCP Active Cell Bridge: Comm opened with kernel"` - Communication established with kernel
- `"MCP Active Cell Bridge: Sent snapshot (X chars)"` - Cell content sent (fires on cell change + 2s after typing)
- `"MCP Active Cell Bridge: Tracking new active cell"` - New cell selected

**Error Messages to Watch For:**
- `"MCP Active Cell Bridge: Failed to create comm"` - Kernel communication failed
- `"MCP Active Cell Bridge: Failed to send snapshot"` - Message sending failed

### 4. Test MCP Tools
Through your MCP client, test:

```json
{
  "method": "tools/call",
  "params": {
    "name": "get_editing_cell"
  }
}
```

**Expected Response Structure:**
```json
{
  "cell_content": "print('hello')",
  "cell_id": "abc123",
  "cell_index": 0,
  "cell_type": "code", 
  "notebook_path": "Untitled.ipynb",
  "captured": true,
  "age_ms": 150,
  "source": "jupyterlab_frontend"
}
```

### 5. Common Issues

#### No Cell Content Captured
- Check browser console for comm errors
- Verify both extensions are loaded (IPython + JupyterLab)
- Try switching between cells to trigger capture

#### Stale Data
- Use `fresh_ms` parameter: `get_editing_cell(fresh_ms=500)`
- Check if frontend is sending updates (console messages)

#### Build/Install Issues
- Clean rebuild: `rm -rf node_modules lib && jlpm install && jlpm run build:lib`
- Version mismatch: Ensure JupyterLab 4.2+ compatibility

### 6. Version Information
```bash
# Check versions
jupyter --version
jupyter labextension list
pip list | grep jupyterlab
```

### 7. Communication Flow
1. **Frontend** (JupyterLab extension) tracks cell changes
2. **Comm Protocol** sends cell data to kernel every 2 seconds
3. **Kernel** (IPython extension) receives and stores latest snapshot
4. **MCP Tool** (`get_editing_cell`) returns stored snapshot

### 8. Manual Comm Testing
In notebook, test kernel-side comm:
```python
# Check if comm target is registered
import IPython
ip = IPython.get_ipython()
if hasattr(ip, 'kernel'):
    targets = ip.kernel.comm_manager.targets
    print("Registered comm targets:", list(targets.keys()))
    print("MCP comm registered:", "mcp:active_cell" in targets)
```