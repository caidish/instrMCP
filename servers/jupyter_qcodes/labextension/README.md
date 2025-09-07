# MCP Active Cell Bridge Extension

A JupyterLab extension that captures the currently editing cell content and sends it to the kernel via comm protocol for consumption by MCP (Model Context Protocol) servers.

## Features

- Tracks the currently active/editing cell in JupyterLab
- Sends cell content updates to kernel via Jupyter comm protocol
- Debounced updates (2-second delay) to prevent excessive communication during typing
- Integrates with MCP servers to provide `get_editing_cell` tool functionality

## Installation

### Prerequisites

- Python 3.10+
- Node.js (for building the extension)
- JupyterLab 4.2+ (required for compatibility)

### Step 1: Set up Python Environment

First, create and activate a virtual environment, then install the required packages:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core project dependencies
pip install -e .

# Install QCodes extras (for full functionality)
pip install -e ".[qcodes]"

# Install JupyterLab (if not already installed)
pip install jupyterlab
```

### Step 2: Compile and Install JupyterLab Extension

Navigate to the labextension directory and build the extension:

```bash
cd servers/jupyter_qcodes/labextension

# Clean any existing build artifacts
rm -rf node_modules package-lock.json yarn.lock .yarn lib tsconfig.tsbuildinfo

# Install JavaScript dependencies
jlpm install

# Build the TypeScript library
jlpm run build:lib

# Build the JupyterLab extension
jlpm run build:labextension

# Install the extension
jupyter labextension install .
```

### Step 3: Verify Installation

Check that the extension is properly installed:

```bash
jupyter labextension list
```

You should see `mcp-active-cell-bridge v0.1.0 [enabled] [OK]` in the output.

### Quick Development Install

For development, you can use:

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
- **TypeScript compilation fails**: The project includes a `tsconfig.json` file with proper configuration. If compilation fails, ensure you have TypeScript dependencies installed via `jlpm install`
- **Build artifacts conflicts**: If you encounter build issues, clean all artifacts and reinstall: `rm -rf node_modules yarn.lock .yarn lib && jlpm install`
- **Version compatibility**: This extension requires JupyterLab 4.2+. Check your version with `jupyter --version`

## Development

### Prerequisites

- Node.js
- JupyterLab 4.2+
- Python 3.7+

### Build

```bash
# Install dependencies
jlpm install

# Build TypeScript library
jlpm run build:lib

# Build JupyterLab extension
jlpm run build:labextension
# OR alternatively: jupyter labextension build .

# Install extension
jupyter labextension install .
```

### Configuration Files

The project includes necessary configuration files:

- `tsconfig.json`: TypeScript compilation configuration
- `package.json`: NPM package and build script definitions
- `.yarnrc.yml`: Yarn configuration to disable PnP mode for JupyterLab compatibility

### Debug

Open browser Developer Tools in JupyterLab and look for console messages:

- `"MCP Active Cell Bridge extension activated"`
- `"MCP Active Cell Bridge: Sent snapshot (X chars)"`
- `"MCP Active Cell Bridge: Tracking new active cell"`

## License

MIT License