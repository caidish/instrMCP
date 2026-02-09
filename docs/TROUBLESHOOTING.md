# Troubleshooting

This guide helps resolve common issues with InstrMCP installation, configuration, and usage.

## Installation Issues

### Error: "Module not found" or import errors

**Symptoms:**
- `ImportError: No module named 'instrmcp'`
- Import errors when trying to use InstrMCP

**Solutions:**
```bash
# Verify installation
pip show instrmcp

# Check version
instrmcp version

# Verify in Python
python -c "import instrmcp; print('OK')"

# If issues persist, reinstall
pip uninstall instrmcp -y
pip install -e .
```

### Error: "JupyterLab extension not found"

**Symptoms:**
- Magic commands not available
- Active cell bridge not working
- Extension not listed in JupyterLab

**Solutions:**
```bash
# Check extensions
jupyter labextension list

# Should show: mcp-active-cell-bridge v0.1.0 enabled OK

# If missing, rebuild JupyterLab
jupyter lab clean --all
jupyter lab build

# Restart JupyterLab completely (not just kernel)
```

## Magic Commands Not Working

### Error: "Magic command not found"

**Symptoms:**
- `%mcp_start` returns "UsageError: Line magic function `%mcp_start` not found"
- Magic commands not recognized

**Solutions:**
```bash
# Method 1: Run automated setup (recommended)
instrmcp-setup

# Method 2: Manual load in notebook
%load_ext instrmcp.extensions

# Verify extension loaded
%mcp_status

# If still not working, restart Jupyter kernel
# Kernel → Restart Kernel
```

### Extension loads but tools not available

**Symptoms:**
- `%mcp_status` shows "Server not running"
- Tools not available in Claude Desktop/Code

**Solutions:**
```python
# Start the MCP server
%mcp_start

# Verify server is running
%mcp_status

# Check port is not in use
# Default port: 8123
```

## Configuration Issues

### Error: "Configuration file not found"

**Symptoms:**
- Warnings about missing configuration
- Default settings not working

**Note:** Configuration is automatic - no setup required!

**Solutions:**
```bash
# Check configuration paths
instrmcp config

# Verify environment variable (if needed)
echo $instrMCP_PATH

# If not set and needed:
export instrMCP_PATH="$(pwd)"
echo 'export instrMCP_PATH="'$(pwd)'"' >> ~/.zshrc
source ~/.zshrc
```

### Error: "Instrument not found"

**Symptoms:**
- Claude reports "Instrument X not found"
- Empty instrument list

**Solutions:**
```python
# In Jupyter notebook, check available instruments
from qcodes import Station
station = Station.default
print(station.components)

# Verify instrument is enabled in your station config
instruments:
  mock_dac:
    driver: qcodes.instrument_drivers.mock.MockDAC
    name: mock_dac_1
    enable: true  # Must be true

# Reload station after config changes
```

## Claude Desktop Integration Issues

### Error: "spawn python ENOENT"

**Symptoms:**
- Claude Desktop doesn't show MCP tools
- Connection errors in Claude Desktop logs

**Solutions:**
```bash
# Find Python path
which python3
# Example output: /Users/username/anaconda3/bin/python3

# Update Claude config with FULL path
# Edit: ~/Library/Application Support/Claude/claude_desktop_config.json
# Change "command": "python" to "command": "/full/path/to/python3"

# Restart Claude Desktop completely
```

### Claude Desktop shows no MCP tools

**Symptoms:**
- Ask "What MCP tools are available?" → No tools listed
- MCP server not connecting

**Solutions:**
```bash
# 1. Verify config file exists
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# 2. Check all paths are absolute (no ~, no $HOME)
# - command: FULL path to python3
# - args: FULL path to claude_launcher.py
# - env variables: FULL paths

# 3. Restart Claude Desktop COMPLETELY
# - Quit application (Cmd+Q)
# - Start Claude Desktop again

# 4. Check Python executable is accessible
/full/path/to/python3 --version

# 5. Test launcher manually
/full/path/to/python3 /full/path/to/claude_launcher.py
```

### "Standalone mode" message

**Symptoms:**
- Claude reports server running in "standalone mode"
- No access to Jupyter notebook variables

**Cause:** Jupyter not running or MCP server not started in Jupyter

**Solutions:**
```bash
# 1. Start Jupyter
jupyter lab

# 2. In a notebook cell, load extension
%load_ext instrmcp.extensions

# 3. Start MCP server
%mcp_start

# 4. Verify server running
%mcp_status

# 5. Test with Claude Desktop
# Ask: "What notebook variables are available?"
```

### Import errors in launcher

**Symptoms:**
- `ModuleNotFoundError: No module named 'instrmcp'`
- Launcher fails to start

**Solutions:**
```bash
# Ensure InstrMCP is installed
pip install -e /path/to/instrMCP

# Check PYTHONPATH in Claude config
# ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "env": {
    "PYTHONPATH": "/full/path/to/instrMCP",
    "instrMCP_PATH": "/full/path/to/instrMCP"
  }
}

# Test import manually
python3 -c "import sys; sys.path.append('/full/path/to/instrMCP'); import instrmcp; print('OK')"
```

### Setup script help

**Symptoms:**
- Manual configuration is confusing
- Want automated setup

**Solutions:**
```bash
# Re-run automated setup
cd /path/to/instrMCP
./agentsetting/claudedesktopsetting/setup_claude.sh

# Verify generated config
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Check paths are correct
# - command: Should match $(which python3)
# - args: Should match $(pwd)/agentsetting/claudedesktopsetting/claude_launcher.py
# - env: Should match $(pwd)

# Restart Claude Desktop
```

See [`agentsetting/claudedesktopsetting/README.md`](../agentsetting/claudedesktopsetting/README.md) for detailed Claude Desktop setup instructions.

## Claude Code Integration Issues

### MCP server not connecting

**Symptoms:**
- `/mcp` shows no instrMCP server
- Connection timeout errors

**Solutions:**
```bash
# Check MCP server is configured
claude mcp list

# If missing, add instrMCP
claude mcp add instrMCP --env instrMCP_PATH=$instrMCP_PATH \
  --env PYTHONPATH=$instrMCP_PATH \
  -- $instrMCP_PATH/venv/bin/python \
  $instrMCP_PATH/agentsetting/claudedesktopsetting/claude_launcher.py

# Restart MCP server
claude mcp restart instrMCP

# Verify connection
/mcp
```

### Tools not available in Claude Code

**Symptoms:**
- MCP server listed but no tools shown
- Tools return errors

**Solutions:**
```bash
# 1. Ensure Jupyter is running
jupyter lab

# 2. Start MCP server in Jupyter
%load_ext instrmcp.extensions
%mcp_start

# 3. Verify server running
%mcp_status

# 4. Test in Claude Code
# Ask: "List all MCP tools available"
```

## Codex CLI Integration Issues

### Server not connecting

**Symptoms:**
- Codex doesn't recognize instrMCP
- Connection errors

**Solutions:**
```bash
# Check Codex configuration
# Verify launcher path is correct
# Verify environment variables set:
# - JUPYTER_MCP_HOST=127.0.0.1
# - JUPYTER_MCP_PORT=8123

# Test launcher manually
python /path/to/instrMCP/agentsetting/codexsetting/codex_launcher.py
```

## Clean Installation (Fresh Start)

If you need to completely uninstall and reinstall InstrMCP:

```bash
# 1. Uninstall instrmcp
pip uninstall instrmcp -y

# 2. Clean JupyterLab build cache
jupyter lab clean --all

# 3. Verify extension is removed
jupyter labextension list | grep mcp
# Should return nothing

# 4. (Optional) Create fresh conda environment
conda deactivate
conda env remove -n instrMCPdev
conda create -n instrMCPdev python=3.11 -y
conda activate instrMCPdev

# 5. Install JupyterLab and dependencies
pip install jupyterlab ipython qcodes

# 6. Reinstall instrmcp
cd /path/to/instrMCP
pip install -e .

# 7. Run setup
instrmcp-setup

# 8. Verify installation
jupyter labextension list | grep mcp-active-cell-bridge
# Should show: mcp-active-cell-bridge v0.1.0 enabled OK

# 9. Start fresh Jupyter session
jupyter lab
```

## Common Error Messages

### "Port already in use"

**Error:** `OSError: [Errno 48] Address already in use`

**Solutions:**
```bash
# Find process using port 8123
lsof -i :8123

# Kill the process
kill -9 <PID>

# Or use different port
%mcp_start --port 8124
```

### "QCodes station not initialized"

**Error:** `RuntimeError: No QCodes station found`

**Solutions:**
```python
# Initialize station manually in notebook
from qcodes import Station
station = Station()
station.set_default()

# Or load from config
station = Station(config_file='path/to/station.yaml')
station.set_default()
```

### "IPython not available"

**Error:** `ImportError: IPython is required`

**Solutions:**
```bash
# Install IPython
pip install ipython

# Or reinstall with all dependencies
pip install -e .[dev]
```

### "FastMCP version mismatch"

**Error:** `ModuleNotFoundError: No module named 'fastmcp'`

**Solutions:**
```bash
# Install FastMCP
pip install fastmcp>=0.1.0

# Or reinstall with all dependencies
pip install -e .
```

## Getting Help

If issues persist:

1. Check logs:
   ```bash
   # Jupyter logs
   jupyter lab --log-level=DEBUG

   # Claude Desktop logs
   # ~/Library/Logs/Claude/
   ```

2. Verify environment:
   ```bash
   instrmcp config
   python --version  # Should be 3.10+
   jupyter --version
   ```

3. Report issue:
   - GitHub Issues: https://github.com/caidish/instrMCP/issues
   - Include: Python version, OS, error messages, logs
   - Minimal reproducible example if possible

4. Check documentation:
   - Main README: [README.md](../README.md)
   - Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
   - Development: [DEVELOPMENT.md](DEVELOPMENT.md)
