Quick Start
===========

This guide will help you get started with InstrMCP in minutes.

Starting the MCP Server in JupyterLab
--------------------------------------

InstrMCP runs as an IPython extension within JupyterLab. Here's how to start it:

1. **Launch JupyterLab**:

.. code-block:: bash

   jupyter lab

2. **Load the InstrMCP extension** in a notebook cell:

.. code-block:: python

   %load_ext instrmcp

3. **Start the MCP server**:

.. code-block:: python

   %mcp_start

The server will start on port 8123 by default and provide MCP tools to connected clients.

Server Management
-----------------

**Check server status**:

.. code-block:: python

   %mcp_status

**Stop the server**:

.. code-block:: python

   %mcp_stop

**Restart the server**:

.. code-block:: python

   %mcp_restart

Safe vs Unsafe Mode
--------------------

InstrMCP operates in two modes:

**Safe Mode** (Default)
  Read-only access to instruments and notebooks. Cannot execute code or modify cells.

**Unsafe Mode**
  Full access including code execution and cell manipulation.

Switch between modes:

.. code-block:: python

   # Enable unsafe mode
   %mcp_unsafe

   # Return to safe mode
   %mcp_safe

   # Restart required for changes to take effect
   %mcp_restart

.. warning::
   Unsafe mode allows LLMs to execute arbitrary code in your notebook. Only enable when needed.

Optional Features
-----------------

InstrMCP supports optional features that can be enabled:

**MeasureIt Integration**:

.. code-block:: python

   %mcp_option measureit
   %mcp_restart

This provides measurement templates and code generation resources.

**Database Integration**:

.. code-block:: python

   %mcp_option database
   %mcp_restart

This enables read-only access to QCodes databases with query tools.

**Check current options**:

.. code-block:: python

   %mcp_option

Connecting Claude Desktop/Code
-------------------------------

After starting the MCP server in JupyterLab, connect Claude Desktop or Claude Code:

1. The server runs on ``http://127.0.0.1:8123``
2. Configure your MCP client to connect to this endpoint
3. Use the launcher scripts in ``agentsetting/claudedesktopsetting/`` or ``agentsetting/codexsetting/``

Example configuration for Claude Desktop (``claude_desktop_config.json``):

.. code-block:: json

   {
     "mcpServers": {
       "instrMCP": {
         "command": "python",
         "args": ["/path/to/instrMCP/agentsetting/claudedesktopsetting/claude_launcher.py"]
       }
     }
   }

Using QCodes Instruments
-------------------------

Once connected, Claude can interact with your QCodes instruments:

**List available instruments**:

Ask Claude: "What instruments are available?"

**Read instrument parameters**:

Ask Claude: "What is the current voltage of the DAC channel 1?"

**Get instrument information**:

Ask Claude: "Show me details about the SR830 lock-in amplifier"

Example Workflow
----------------

Here's a complete example workflow:

1. **Start JupyterLab and create a new notebook**

2. **Initialize QCodes instruments**:

.. code-block:: python

   import qcodes as qc
   from qcodes.instrument_drivers.stanford_research.SR830 import SR830

   # Create a mock instrument for testing
   lockin = SR830("lockin", "GPIB0::8::INSTR")

3. **Start InstrMCP**:

.. code-block:: python

   %load_ext instrmcp
   %mcp_start

4. **Connect Claude Desktop/Code** using the launcher script

5. **Interact with instruments through Claude**:

   - "What instruments do we have?"
   - "Read the X voltage from the lock-in"
   - "Show me all parameters of the lockin instrument"

6. **Enable database access** (optional):

.. code-block:: python

   %mcp_option database
   %mcp_restart

7. **Query measurement history through Claude**:

   - "Show me the last 5 measurements"
   - "What datasets were created today?"

Next Steps
----------

- Learn about the :doc:`architecture` of InstrMCP
- Explore available :doc:`mcp_tools`
- Read about :doc:`jupyter_integration`
- Check out :doc:`database_integration` for measurement history access