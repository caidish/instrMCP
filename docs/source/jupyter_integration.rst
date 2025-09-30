Jupyter Integration
===================

InstrMCP integrates deeply with JupyterLab to provide seamless access to notebook state and active cells.

Extension Architecture
----------------------

The integration consists of three components:

1. **IPython Extension**: Loads in kernel, provides magic commands
2. **JupyterLab Extension**: TypeScript frontend extension for cell access
3. **Comm Protocol**: Bidirectional communication channel

IPython Extension
-----------------

The IPython extension (``instrmcp.extensions``) provides:

Magic Commands
~~~~~~~~~~~~~~

Load the extension:

.. code-block:: python

   %load_ext instrmcp

Server management:

.. code-block:: python

   %mcp_start    # Start MCP server
   %mcp_stop     # Stop MCP server
   %mcp_restart  # Restart server
   %mcp_status   # Check status

Mode switching:

.. code-block:: python

   %mcp_safe     # Enable safe mode (read-only)
   %mcp_unsafe   # Enable unsafe mode (code execution)

Optional features:

.. code-block:: python

   %mcp_option              # Show current options
   %mcp_option measureit    # Enable MeasureIt templates
   %mcp_option database     # Enable database integration
   %mcp_option -measureit   # Disable MeasureIt

Auto-Loading
~~~~~~~~~~~~

To automatically load InstrMCP when JupyterLab starts:

1. Create/edit ``~/.ipython/profile_default/ipython_config.py``
2. Add:

.. code-block:: python

   c.InteractiveShellApp.extensions = ['instrmcp']

JupyterLab Extension
--------------------

The JupyterLab extension (``mcp-active-cell-bridge``) provides real-time access to:

- Active cell content
- Cell execution
- Cell manipulation
- Cursor movement

Installation
~~~~~~~~~~~~

The extension is automatically installed with InstrMCP:

.. code-block:: bash

   pip install -e .
   # Restart JupyterLab

Verify installation:

.. code-block:: bash

   jupyter labextension list

You should see ``mcp-active-cell-bridge@1.0.0 enabled``.

Communication Protocol
~~~~~~~~~~~~~~~~~~~~~~

The extension uses IPython's Comm protocol:

.. code-block:: text

   ┌─────────────┐                    ┌──────────────┐
   │   Kernel    │◄────── Comm ──────►│   Frontend   │
   │  (Python)   │                    │ (TypeScript) │
   └─────────────┘                    └──────────────┘
         │                                    │
         ├─ active_cell_bridge.py            ├─ src/index.ts
         ├─ Request: get_cell               ├─ Handler: handleGetCell
         └─ Response: cell_data              └─ JupyterLab API access

Active Cell Bridging
--------------------

How It Works
~~~~~~~~~~~~

1. **MCP tool called**: Claude requests current cell via ``get_editing_cell``
2. **Python bridge**: ``active_cell_bridge.py`` sends comm message
3. **Frontend handler**: TypeScript extension accesses JupyterLab API
4. **Response**: Cell content sent back through comm protocol
5. **MCP response**: Data returned to Claude

Supported Operations
~~~~~~~~~~~~~~~~~~~~

**Read Operations** (Safe):

- Get active cell content and metadata
- Get cell output
- List recent cells with outputs
- Get notebook variables

**Write Operations** (Unsafe):

- Update cell content
- Execute cell code
- Add new cells
- Delete cells
- Apply text patches
- Move cursor between cells

Example: Custom Tool Using Comm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's how to add a custom tool that uses the comm protocol:

.. code-block:: python

   # In active_cell_bridge.py
   def my_custom_operation(param: str) -> Dict[str, Any]:
       import uuid

       request_id = str(uuid.uuid4())

       # Send request to frontend
       for comm in _ACTIVE_COMMS:
           comm.send({
               "type": "my_custom_op",
               "param": param,
               "request_id": request_id
           })

       return {
           "success": True,
           "request_id": request_id
       }

.. code-block:: typescript

   // In src/index.ts
   const handleMyCustomOp = async (
     kernel: Kernel.IKernelConnection,
     comm: any,
     data: any
   ) => {
     const requestId = data.request_id;
     const param = data.param;

     // Access JupyterLab API
     const panel = notebooks.currentWidget;
     const notebook = panel?.content;

     // Perform operation
     // ...

     // Send response
     comm.send({
       type: 'my_custom_op_response',
       request_id: requestId,
       success: true,
       result: result
     });
   }

   // Register handler
   } else if (msgType === 'my_custom_op') {
     handleMyCustomOp(kernel, comm, data);

Notebook Variable Inspection
-----------------------------

InstrMCP provides direct access to notebook variables:

Variable Types
~~~~~~~~~~~~~~

The system recognizes:

- **QCodes instruments**: Detected via ``isinstance(obj, Instrument)``
- **NumPy arrays**: ``numpy.ndarray``
- **Pandas DataFrames**: ``pandas.DataFrame``
- **Dictionaries**: ``dict``
- **Lists**: ``list``
- **Numbers**: ``int``, ``float``

Type Filtering
~~~~~~~~~~~~~~

Filter variables by type:

.. code-block:: python

   # Via MCP tool
   list_variables(type_filter="array")
   list_variables(type_filter="instrument")
   list_variables(type_filter="dict")

Example via Claude:

"Show me all QCodes instruments in the notebook"

Variable Information
~~~~~~~~~~~~~~~~~~~~

Get detailed info about specific variables:

.. code-block:: python

   get_variable_info(name="my_array")

Returns:
- Variable type
- Shape (for arrays)
- Data type
- Size
- Preview of contents

Cell Output Capture
-------------------

InstrMCP captures cell execution outputs using IPython's caching:

Output Types
~~~~~~~~~~~~

- **Normal output**: Return value (in ``Out`` dict)
- **No output**: Cell executed but returned None
- **Error output**: Exception information
- **Running**: Cell currently executing

Example Usage
~~~~~~~~~~~~~

Check last cell output via Claude:

"What was the output of the last cell?"

Returns:
- Cell input (code)
- Cell output (if any)
- Execution count
- Status (completed/error/running)
- Error details (if error occurred)

Error Handling
~~~~~~~~~~~~~~

When a cell raises an error:

.. code-block:: python

   {
     "status": "error",
     "cell_number": 5,
     "input": "1 / 0",
     "error": {
       "type": "ZeroDivisionError",
       "message": "division by zero",
       "traceback": "..."
     }
   }

Performance Considerations
--------------------------

Caching
~~~~~~~

- Cell content cached with configurable freshness (``fresh_ms`` parameter)
- Default: 1000ms (1 second)
- Reduces frontend queries

Rate Limiting
~~~~~~~~~~~~~

- Comm messages limited to prevent flooding
- Failed comms automatically removed
- Multiple comms supported for resilience

Best Practices
~~~~~~~~~~~~~~

1. **Batch operations**: Combine multiple reads when possible
2. **Limit history**: Request only needed cells (``num_cells`` parameter)
3. **Fresh data**: Use ``fresh_ms`` when you need recent content
4. **Error handling**: Always check response ``success`` field

Troubleshooting
---------------

Extension Not Loading
~~~~~~~~~~~~~~~~~~~~~

If the JupyterLab extension doesn't load:

.. code-block:: bash

   # Check extension status
   jupyter labextension list

   # Rebuild if needed
   cd instrmcp/extensions/jupyterlab
   jlpm run build

   # Reinstall package
   pip install -e . --force-reinstall --no-deps

   # Restart JupyterLab completely
   # (stop and start, don't just refresh)

Comm Connection Issues
~~~~~~~~~~~~~~~~~~~~~~

If tools report "No active comm connections":

1. Verify JupyterLab extension is loaded
2. Restart Jupyter kernel
3. Reload the ``instrmcp`` extension: ``%reload_ext instrmcp``
4. Check browser console for errors

Magic Commands Not Working
~~~~~~~~~~~~~~~~~~~~~~~~~~

If magic commands aren't recognized:

.. code-block:: python

   # Reload extension
   %reload_ext instrmcp

   # Verify it's loaded
   %lsmagic  # Should show %mcp_* commands

Tools Returning Stale Data
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If cell content seems outdated:

- Use ``fresh_ms=0`` parameter to force refresh
- Check that JupyterLab extension is active
- Verify comm connection with ``%mcp_status``

Advanced Usage
--------------

Custom Comm Handlers
~~~~~~~~~~~~~~~~~~~~

You can add custom comm message handlers for specialized operations.

See the source code in:
- ``instrmcp/servers/jupyter_qcodes/active_cell_bridge.py``
- ``instrmcp/extensions/jupyterlab/src/index.ts``

Extension Development
~~~~~~~~~~~~~~~~~~~~~

To modify the JupyterLab extension:

1. Edit TypeScript files in ``src/``
2. Run ``jlpm run build``
3. Reinstall: ``pip install -e . --force-reinstall --no-deps``
4. Restart JupyterLab

For development with hot reload:

.. code-block:: bash

   # Terminal 1: Watch TypeScript
   cd instrmcp/extensions/jupyterlab
   jlpm run watch

   # Terminal 2: Watch extension
   jupyter labextension watch .

   # Refresh browser to see changes