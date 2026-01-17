# InstrMCP: Instrumentation Control MCP Server

[![PyPI version](https://img.shields.io/pypi/v/instrmcp.svg)](https://pypi.org/project/instrmcp/)
[![instrmcp](https://labextensions.dev/api/badge/instrmcp?metric=downloads&leftColor=%23555&rightColor=%23F37620&style=flat)](https://labextensions.dev/extensions/instrmcp)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://github.com/anthropics/mcp)
[![Documentation Status](https://readthedocs.org/projects/instrmcp/badge/?version=latest)](https://instrmcp.readthedocs.io/en/latest/?badge=latest)
[![Tests](https://github.com/caidish/instrMCP/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/caidish/instrMCP/actions/workflows/tests.yml)
[![Lint](https://github.com/caidish/instrMCP/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/caidish/instrMCP/actions/workflows/lint.yml)

MCP server suite for quantum device physics laboratory's instrumentation control, enabling Large Language Models to interact directly with physics instruments and measurement systems through QCodes and JupyterLab.

https://github.com/user-attachments/assets/e7d0a441-36b2-4fec-9c54-1427310b7698


## Features

- **Full QCodes Integration**: Built-in support for all QCodes instrument drivers
- **Database Integration**: Read-only access to QCodes databases with intelligent code generation
- **MeasureIt Templates**: Comprehensive measurement pattern library and code generation
- **JupyterLab Native**: Seamless integration with JupyterLab
- **Dynamic Tool Creation**: Create custom MCP tools at runtime using LLM-powered tool registration
- **Safe mode**: Read-only mode with optional unsafe execution
- **CLI**: Easy server management with `instrmcp` command
- **MCP**: Standard Model Context Protocol for LLM integration
- The MCP has been tested to work with Claude Desktop, Claude Code, and Codex CLI
## Quick Start

### Installation

**From PyPI (Recommended):**

```bash
pip install instrmcp
```

**That's it!** QCodes, JupyterLab, and all dependencies are automatically installed. The JupyterLab extension is automatically enabled (no Node.js or rebuild required).

**From Source (For Development):**

```bash
git clone https://github.com/caidish/instrMCP.git
cd instrMCP
pip install -e .

# Run setup to enable JupyterLab extension (only needed for editable install)
instrmcp-setup

# Set required environment variable for development
# For macOS/Linux:
export instrMCP_PATH="$(pwd)"
echo 'export instrMCP_PATH="'$(pwd)'"' >> ~/.zshrc  # or ~/.bashrc
source ~/.zshrc

# For Windows (PowerShell):
$env:instrMCP_PATH = (Get-Location).Path
[System.Environment]::SetEnvironmentVariable('instrMCP_PATH', (Get-Location).Path, 'User')
```

### Extension: MeasureIt

MeasureIt provides comprehensive measurement pattern templates for common physics experiments.

**Installation:**
```bash
pip install qmeasure
```

**Important Notes:**
- Import as `measureit` (not `qmeasure`): `import measureit`
- Python 3.8+ required
- For source installation or advanced configuration, see the [MeasureIt GitHub repository](https://github.com/nanophys/MeasureIt)

**Enable in InstrMCP:**
```python
# In Jupyter notebook
%mcp_option add measureit
%mcp_restart
```

### Usage

#### Loading InstrMCP in Jupyter

```bash
# Start JupyterLab
jupyter lab
```

In a Jupyter notebook cell:

```python
# Load InstrMCP extension
%load_ext instrmcp.extensions

# Start MCP server
%mcp_start

# Check status
%mcp_status

# Enable unsafe mode (code execution)
%mcp_unsafe

# Enable optional features (restart required)
%mcp_option add measureit database
%mcp_restart
```

#### CLI Utilities

```bash
instrmcp config    # Show configuration paths
instrmcp version   # Show version
instrmcp --help    # Show all commands
```

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture, package structure, MCP tools and resources
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Development Guide](docs/DEVELOPMENT.md)** - Development setup, testing, code quality, contributing
  - Includes **Threading Architecture & Qt Integration** - How IPython kernel, Qt event loop, and MCP server thread interact; what cross-thread communication approaches work and don't work with MeasureIt

## Configuration

View current configuration:

```bash
instrmcp config
```

## Claude Desktop Integration

InstrMCP provides seamless integration with Claude Desktop for AI-assisted laboratory instrumentation control.

### Quick Setup (2 Steps)

1. **Run Automated Setup**:
```bash
cd /path/to/your/instrMCP
./claudedesktopsetting/setup_claude.sh
```

2. **Restart Claude Desktop** completely and test with: *"What MCP tools are available?"*

**Manual Setup Alternative:**
```bash
# 1. Copy and edit configuration
cp claudedesktopsetting/claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json

# 2. Edit the copied file - replace placeholders with actual paths:
#    /path/to/your/python3 → $(which python3)
#    /path/to/your/instrMCP → $(pwd)
```

See [`claudedesktopsetting/README.md`](claudedesktopsetting/README.md) for detailed setup instructions and troubleshooting.

## Claude Code Integration

Claude Code supports local MCP servers via STDIO. Use the provided launcher to connect:

```bash
# Add instrMCP as MCP Server
claude mcp add instrMCP --env instrMCP_PATH=$instrMCP_PATH \
  --env PYTHONPATH=$instrMCP_PATH \
  -- $instrMCP_PATH/venv/bin/python \
  $instrMCP_PATH/claudedesktopsetting/claude_launcher.py

# Verify connection
/mcp
```

**Prerequisites:**
- Ensure `instrMCP_PATH` environment variable is set
- Have a Jupyter server running with the instrMCP extension loaded
- MCP server started in Jupyter with `%mcp_start`

## Codex CLI Integration

Codex expects MCP servers over STDIO. Use the Codex launcher to proxy STDIO calls to your HTTP MCP server.

**Configuration:**
- command: `python`
- args: `["/path/to/your/instrMCP/codexsetting/codex_launcher.py"]`
- env:
  - `JUPYTER_MCP_HOST=127.0.0.1`
  - `JUPYTER_MCP_PORT=8123`

## V2.0.0 Features (Current Release)

### 1. Resource Discovery Tool
The `mcp_list_resources()` tool helps LLMs discover and effectively use MCP resources:

**Features:**
- **Comprehensive Resource Listing**: All available MCP resources with URIs, descriptions, and use cases
- **Context-Aware**: Only shows resources based on enabled options (core, MeasureIt, database)
- **Resources vs Tools Guidance**: Educates LLMs on when to use read-only resources vs active tools
- **Common Patterns**: Examples like "Check available_instruments → Use qcodes_instrument_info"
- **First-Use Recommendation**: Use this tool FIRST to discover what context is available

**Example Response:**
```json
{
  "total_resources": 8,
  "resources": [
    {
      "uri": "resource://available_instruments",
      "name": "Available Instruments",
      "use_when": "Need to know what instruments exist BEFORE calling qcodes_instrument_info",
      "example": "Check this first to see instrument names..."
    }
  ],
  "guidance": {
    "resources_vs_tools": {
      "resources": "Provide READ-ONLY reference data, templates, and documentation",
      "tools": "Perform ACTIVE operations like reading live values, executing code"
    },
    "when_to_use_resources": [
      "Before using tools - check available_instruments first",
      "For code templates - get MeasureIt examples",
      "For configuration - check database_config"
    ]
  }
}
```

### 2. Consent System for Cell Modifications
Cell modification tools now require user consent in unsafe mode:

**Tools requiring consent:**
- `notebook_update_editing_cell` - Shows old/new content comparison before replacing entire cell
- `notebook_apply_patch` - Shows visual diff dialog with exact changes

**Features:**
- **Visual Diff Display**: Red deletions, green additions, context lines
- **Pattern Warning**: Prominent alert if old_text not found in cell
- **Change Statistics**: Shows chars removed/added and delta
- **Consent Workflow**: "Decline" | "Allow" | "Always Allow" buttons
- **Battle-Tested Diffing**: Uses industry-standard `diff` library (v8.0.2) from GitHub/GitLab

**Example:** When LLM calls `notebook_apply_patch(old_text="x = 10", new_text="x = 20")`, user sees:
```diff
- x = 10  ← Red background with strikethrough
+ x = 20  ← Green background
```

### 3. Line Range Parameters for Context Management
Control LLM context window consumption with line range selection:

**Features:**
- **line_start** / **line_end** parameters (default: lines 1-100)
- **Automatic Bounds Clamping**: Invalid ranges safely handled
- **Truncation Metadata**: Returns `total_lines`, `truncated` flag
- **Context Window Savings**: Prevents large cells from consuming excessive tokens

**Example:**
```python
# Get only first 50 lines of a large cell
get_editing_cell(line_start=1, line_end=50)

# Get lines 100-200 for focused analysis
get_editing_cell(line_start=100, line_end=200)
```

### 4. Dynamic Tool Creation
Create custom MCP tools at runtime using LLM-powered tool registration:

```python
# In Jupyter with instrMCP loaded in unsafe mode
# LLM can create tools dynamically using meta-tools:
dynamic_register_tool(
    name="analyze_data",
    source_code="def analyze_data(x): return x * 2",
    capabilities=["cap:numpy", "cap:custom.analysis"],  # Freeform labels
    parameters=[{"name": "x", "type": "number", "description": "Input", "required": true}]
)
```

**Features:**
- **6 Meta-Tools**: `register`, `update`, `revoke`, `list`, `inspect`, `registry_stats`
- **Consent UI**: User approval required for tool registration/updates (shows full source code)
- **Freeform Capability Labels**: Tag tools with descriptive capabilities for discovery
- **Persistent Registry**: Tools saved to `~/.instrmcp/registry/` and reloaded on server start
- **Audit Trail**: All tool operations logged to `~/.instrmcp/audit/tool_audit.log`
- **Auto JSON Correction**: Optional LLM-powered JSON error fixing (opt-in via `%mcp_option auto_correct_json`)

**Capability Labels** (v2.0.0):
Capabilities are freeform documentation labels - NOT enforced security boundaries. Use any descriptive string:
- Suggested format: `cap:library.action` (e.g., `cap:numpy.array`, `cap:qcodes.read`)
- Used for discovery, filtering, and transparency in consent UI
- No validation - flexibility for LLMs to describe tool dependencies
- Future: Enforcement layer planned for v3.0.0

See [Dynamic Tools Quickstart](docs/DYNAMIC_TOOLS_QUICKSTART.md) for details.

### Testing & Quality
- **464 tests** (463 passed, 1 skipped)
- **Zero linter errors** across all modules
- **Code formatted** with black
- **CI/CD passing** on all workflows

## V3.0.0 Roadmap

- **Capability Enforcement**: Security boundaries based on capability taxonomy
- Support RedPitaya
- Support Raspberry Pi for outdated instruments
- Integrating lab wiki knowledge base for safety rails
- More LLM integration examples

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

We welcome contributions! See our [Development Guide](docs/DEVELOPMENT.md) for details on:
- Setting up development environment
- Running tests
- Code quality standards
- Contribution guidelines

## Links

- [Documentation](https://instrmcp.readthedocs.io)
- [Issues](https://github.com/caidish/instrMCP/issues)
- [QCodes](https://qcodes.github.io/Qcodes/)
- [Model Context Protocol](https://github.com/anthropics/mcp)
