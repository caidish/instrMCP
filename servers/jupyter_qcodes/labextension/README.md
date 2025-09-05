# MCP Active Cell Bridge Extension

A JupyterLab extension that captures the currently editing cell content and sends it to the kernel via comm protocol for consumption by MCP (Model Context Protocol) servers.

## Features

- Tracks the currently active/editing cell in JupyterLab
- Sends cell content updates to kernel via Jupyter comm protocol
- Debounced updates (2-second delay) to prevent excessive communication during typing
- Integrates with MCP servers to provide `get_editing_cell` tool functionality

## Installation

```bash
pip install -e .
```

Or for development:

```bash
jlpm install
jlpm run build
jupyter labextension develop . --overwrite
```

## Usage

### IMPORTANT: Kernel Extension Setup

Before using this extension, you MUST load the kernel-side comm target in your Jupyter notebook by running:

```python
%load_ext servers.jupyter_qcodes.jupyter_mcp_extension
```

This registers the `mcp:active_cell` comm target in the kernel. Without this step, the frontend extension cannot communicate with the kernel and will show "Comm not ready for sending" errors.

### How It Works

Once the kernel extension is loaded, the frontend extension automatically:

1. Tracks when you switch between cells
2. Monitors content changes in the active cell (with 2s debounce)  
3. Sends cell snapshots to the kernel via comm channel `"mcp:active_cell"`
4. Enables MCP tools to access current editing cell content via `get_editing_cell()`

## Integration

This extension works with the Jupyter QCoDeS MCP server to provide the `get_editing_cell()` tool, allowing MCP clients to access the content of the cell currently being edited in JupyterLab.

## Troubleshooting

### "Comm not ready for sending" Errors

If you see repeated "MCP Active Cell Bridge: Comm not ready for sending" errors in the browser console:

1. **Check kernel extension loading**: Make sure you've run `%load_ext servers.jupyter_qcodes.jupyter_mcp_extension` in a notebook cell
2. **Verify extension installation**: Check that the frontend extension is installed with `jupyter labextension list`
3. **Check console output**: Look for "MCP Active Cell Bridge: Comm opened and ready" messages
4. **Restart kernel**: Try restarting the Jupyter kernel and rerunning the load_ext command

### Common Issues

- **Comm closes immediately**: This indicates the kernel doesn't have the comm target registered
- **Multiple open/close cycles**: Usually caused by not awaiting async operations properly (fixed in latest version)
- **Extension not loading**: Ensure JupyterLab 4.2+ is installed and extension is properly built

## Development

### Prerequisites

- Node.js
- JupyterLab 4.2+
- Python 3.7+

### Build

```bash
jlpm install
jlpm run build:lib
jupyter labextension build .
```

### Debug

Open browser Developer Tools in JupyterLab and look for console messages:

- `"MCP Active Cell Bridge extension activated"`
- `"MCP Active Cell Bridge: Sent snapshot (X chars)"`
- `"MCP Active Cell Bridge: Tracking new active cell"`

## License

MIT License