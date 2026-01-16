Architecture
============

System Overview
---------------

InstrMCP is designed as a bridge between Large Language Models and physics laboratory instruments. The architecture consists of several key components that work together to enable seamless interaction.

.. code-block:: text

   ┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
   │ Claude Desktop/ │◄──STDIO─┤  STDIO Proxy     │◄───HTTP─┤ Jupyter MCP     │
   │ Claude Code/    │         │  (stdio_proxy.py)│         │ Server          │
   │ Codex           │         └──────────────────┘         │ (mcp_server.py) │
   └─────────────────┘                                      └─────────────────┘
                                                                      │
                                                                      ├── QCodes Tools
                                                                      ├── Notebook Tools
                                                                      ├── Database Tools
                                                                      └── MeasureIt Tools

Core Components
---------------

Jupyter MCP Server
~~~~~~~~~~~~~~~~~~

The heart of InstrMCP is the FastMCP server that runs inside JupyterLab:

- **Location**: ``instrmcp/servers/jupyter_qcodes/mcp_server.py``
- **Function**: Provides MCP tools and resources to connected clients
- **Integration**: Runs as IPython extension within Jupyter kernel
- **Protocol**: HTTP/SSE for communication

Key features:
- Safe/unsafe mode switching
- Optional feature management (database, MeasureIt)
- Real-time instrument access
- Notebook variable inspection
- Active cell manipulation

STDIO Proxy
~~~~~~~~~~~

Bridges STDIO-based MCP clients to HTTP server:

- **Location**: ``instrmcp/tools/stdio_proxy.py``
- **Function**: Converts STDIO MCP protocol to HTTP requests
- **Used by**: Claude Desktop, Claude Code, Codex
- **Protocol**: STDIO ↔ HTTP/SSE

The proxy handles:
- Initialize/initialized handshake
- Tool call forwarding
- Response streaming
- Session management

JupyterLab Extension
~~~~~~~~~~~~~~~~~~~~

TypeScript extension for active cell bridging:

- **Location**: ``instrmcp/extensions/jupyterlab/``
- **Function**: Provides real-time access to active cell
- **Protocol**: Comm protocol (IPython kernel ↔ frontend)

Capabilities:
- Get/update active cell content
- Execute cells
- Add/delete cells
- Move cursor between cells
- Patch cell content

QCodes Integration
~~~~~~~~~~~~~~~~~~

Direct instrument access layer:

- **Location**: ``instrmcp/servers/jupyter_qcodes/tools.py``
- **Function**: Read-only access to QCodes instruments
- **Features**:
  - Parameter value reading
  - Instrument discovery
  - Hierarchical parameter access
  - Rate limiting and caching

Tool Categories
---------------

Notebook Tools (Safe)
~~~~~~~~~~~~~~~~~~~~~

Read-only notebook inspection:

- ``list_variables`` - List notebook variables by type
- ``get_variable_info`` - Detailed variable information
- ``get_editing_cell`` - Current cell content
- ``get_editing_cell_output`` - Last cell output
- ``get_notebook_cells`` - Recent cell history
- ``move_cursor`` - Change active cell selection
- ``server_status`` - Server state

QCodes Tools (Safe)
~~~~~~~~~~~~~~~~~~~

Instrument interaction:

- ``instrument_info`` - Instrument details and parameters
- ``get_parameter_values`` - Read instrument parameters (batch supported)

Unsafe Tools
~~~~~~~~~~~~

Cell manipulation (requires ``%mcp_unsafe``):

- ``update_editing_cell`` - Replace cell content
- ``execute_editing_cell`` - Run cell code
- ``add_new_cell`` - Insert new cell
- ``delete_editing_cell`` - Remove cell
- ``apply_patch`` - Partial cell editing
- ``delete_cells_by_number`` - Bulk cell deletion

Database Tools (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~

QCodes database access (requires ``%mcp_option database``):

- ``list_experiments`` - List all experiments
- ``get_dataset_info`` - Dataset metadata and parameters
- ``get_database_stats`` - Database health metrics

MeasureIt Tools (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Measurement status (requires ``%mcp_option measureit``):

- ``get_measureit_status`` - Check running sweeps
- ``measureit_

Resources
---------

MCP resources provide context to LLMs:

**QCodes Resources** (Always available):

None. Use ``qcodes_instrument_info("*")`` to list instruments, then ``qcodes_instrument_info(name)`` for details.

**Jupyter Resources** (Always available):

- ``notebook_cells`` - Complete notebook contents

**Database Resources** (Optional):

None. Use ``database_list_experiments`` and ``database_get_dataset_info`` for database metadata.

**MeasureIt Resources** (Optional):

- ``measureit_sweep0d_template`` - Time-based monitoring patterns
- ``measureit_sweep1d_template`` - 1D sweep patterns
- ``measureit_sweep2d_template`` - 2D mapping patterns
- ``measureit_simulsweep_template`` - Simultaneous sweep patterns
- ``measureit_sweepqueue_template`` - Sequential workflow patterns
- ``measureit_common_patterns`` - Best practices
- ``measureit_code_examples`` - Complete pattern library

Communication Flow
------------------

1. **Client Initialization**:

   - Claude Desktop starts launcher script
   - Launcher creates STDIO proxy
   - Proxy connects to HTTP server at ``http://127.0.0.1:8123``

2. **MCP Handshake**:

   - Client sends ``initialize`` request
   - Server responds with capabilities and tool list
   - Client sends ``initialized`` notification

3. **Tool Invocation**:

   - Client sends ``tools/call`` request
   - Proxy forwards to HTTP server
   - Server executes tool in Jupyter kernel
   - Response returned through proxy to client

4. **Active Cell Operations**:

   - Tool requests active cell data
   - Python bridge sends comm message to frontend
   - TypeScript extension accesses JupyterLab API
   - Result sent back through comm protocol
   - Response delivered to MCP client

Safety Architecture
-------------------

**Safe Mode** (Default):

- Read-only instrument access
- No code execution
- No cell modification
- Variable inspection only

**Unsafe Mode** (Explicit opt-in):

- Code execution allowed
- Cell manipulation enabled
- Requires ``%mcp_unsafe`` magic command
- Requires server restart

**Rate Limiting**:

- Instrument reads cached (5 seconds default)
- Parameter batching supported
- Prevents instrument overload

**Error Handling**:

- All tool calls wrapped in try/except
- Errors returned as JSON responses
- No kernel crashes from tool failures

Extension Points
----------------

InstrMCP is designed to be extensible:

**Custom Tools**:

Add new tools in registrar modules:

- ``registrars/qcodes_tools.py`` - QCodes-specific tools
- ``registrars/notebook_tools.py`` - Jupyter notebook tools
- ``registrars/database_tools.py`` - Database query tools
- ``registrars/measureit_tools.py`` - MeasureIt integration

**Custom Resources**:

Add resources in ``registrars/resources.py``

**Optional Features**:

Create new optional features following the database/MeasureIt pattern:

1. Create registrar class
2. Add magic command handler
3. Implement tool/resource registration
4. Update ``%mcp_option`` command

Performance Considerations
--------------------------

- **Caching**: Instrument parameters cached to reduce read frequency
- **Batch Operations**: Multiple parameters read in single operation
- **Async Design**: Non-blocking tool execution
- **Rate Limiting**: Prevents excessive instrument queries
- **Lightweight Extension**: Minimal JupyterLab frontend overhead
