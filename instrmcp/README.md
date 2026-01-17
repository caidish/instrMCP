# instrmcp Package Structure

## File Tree

```
instrmcp/
├── __init__.py              # Package version and exports
├── cli.py                   # CLI entry point (instrmcp command)
├── setup_utils.py           # Setup utilities (instrmcp-setup command)
│
├── servers/                 # MCP server implementations
│   ├── __init__.py
│   └── jupyter_qcodes/      # Main Jupyter+QCodes MCP server
│       ├── __init__.py
│       ├── mcp_server.py           # FastMCP server core
│       ├── jupyter_mcp_extension.py # IPython magic commands (%mcp_start, etc.)
│       ├── active_cell_bridge.py   # Jupyter frontend communication
│       ├── tools.py                # Read-only QCodes tools implementation
│       ├── cache.py                # Parameter value caching
│       │
│       ├── core/                   # Always-available tools
│       │   ├── __init__.py
│       │   ├── qcodes_tools.py     # QCodes instrument tools
│       │   ├── notebook_tools.py   # Notebook variable/cell tools (safe)
│       │   ├── notebook_unsafe_tools.py   # Notebook tools (unsafe mode)
│       │   └── resources.py        # MCP resources registrar
│       │
│       ├── options/                # Optional features (%mcp_option)
│       │   ├── __init__.py
│       │   ├── measureit/          # MeasureIt integration
│       │   │   ├── __init__.py
│       │   │   ├── templates.py    # Sweep code templates
│       │   │   └── tools.py        # MeasureIt MCP tools
│       │   ├── database/           # QCoDeS database integration
│       │   │   ├── __init__.py
│       │   │   ├── resources.py    # Database MCP resources
│       │   │   ├── query_tools.py  # Database query utilities
│       │   │   ├── tools.py        # Database MCP tools
│       │   │   └── internal/       # Code suggestion helpers
│       │   │       ├── __init__.py
│       │   │       └── code_suggestion.py
│       │   └── dynamic_tool/       # Dynamic tool creation
│       │       ├── __init__.py
│       │       ├── spec.py         # Tool specification schema
│       │       ├── registry.py     # Tool registration and storage
│       │       ├── registrar.py    # Dynamic tool MCP tools
│       │       └── runtime.py      # Dynamic tool execution
│       │
│       └── security/               # Security subsystem
│           ├── __init__.py
│           ├── code_scanner.py     # Dangerous code pattern detection
│           ├── ipython_scanner.py  # IPython magic scanning
│           ├── consent.py          # User consent management
│           └── audit.py            # Security audit logging
│
├── extensions/              # Backward compatibility stubs
│   ├── __init__.py          # Extension loader for IPython
│   ├── measureit/           # DEPRECATED: Forwards to options/measureit
│   ├── database/            # DEPRECATED: Forwards to options/database
│   ├── dynamic_tool/        # DEPRECATED: Forwards to options/dynamic_tool
│   └── jupyterlab/          # JupyterLab frontend extension
│       ├── __init__.py
│       ├── setup.py
│       ├── package.json
│       ├── src/             # TypeScript source (index.ts)
│       └── mcp_active_cell_bridge/  # Built extension
│           ├── __init__.py
│           └── labextension/        # Compiled JS bundle
│
└── utils/                   # Internal utilities
    ├── __init__.py
    ├── logging_config.py    # Unified logging configuration
    ├── mcptool_logger.py    # MCP tool invocation logging
    └── stdio_proxy.py       # STDIO↔HTTP proxy for Claude Desktop
```

## Module Responsibilities

### Entry Points
| File | Entry Point | Purpose |
|------|-------------|---------|
| `cli.py` | `instrmcp` | CLI for config/version commands |
| `setup_utils.py` | `instrmcp-setup` | JupyterLab extension setup |

### Server Core (`servers/jupyter_qcodes/`)
| File | Purpose |
|------|---------|
| `mcp_server.py` | FastMCP server, tool registration orchestration |
| `jupyter_mcp_extension.py` | IPython magics (`%mcp_start`, `%mcp_unsafe`, etc.) |
| `active_cell_bridge.py` | Comm protocol with JupyterLab frontend |
| `tools.py` | Read-only instrument/notebook access |

### Core Tools (`servers/jupyter_qcodes/core/`)
| File | Tools Registered |
|------|-----------------|
| `qcodes_tools.py` | `qcodes_instrument_info`, `qcodes_get_parameter_values` |
| `notebook_tools.py` | `notebook_*` tools (variables, cells, cursor) |
| `notebook_unsafe_tools.py` | `notebook_update_editing_cell`, `notebook_execute_cell`, etc. |
| `resources.py` | MCP resources (templates, config) |

### Optional Features (`servers/jupyter_qcodes/options/`)
| Directory | Enable Command | Tools/Resources |
|-----------|---------------|-----------------|
| `measureit/` | `%mcp_option add measureit` | `measureit_*` tools, sweep templates |
| `database/` | `%mcp_option add database` | `database_*` tools, experiment queries |
| `dynamic_tool/` | `%mcp_option add dynamictool` | `dynamic_*` tools (requires dangerous mode) |

### Security (`servers/jupyter_qcodes/security/`)
| File | Purpose |
|------|---------|
| `code_scanner.py` | AST-based dangerous pattern detection |
| `consent.py` | User consent dialogs and "always allow" storage |
| `audit.py` | Security event logging |

### Internal Utilities (`utils/`)
| File | Purpose |
|------|---------|
| `logging_config.py` | Centralized logging setup |
| `mcptool_logger.py` | MCP tool call logging with timing |
| `stdio_proxy.py` | Proxy server for Claude Desktop STDIO mode |
