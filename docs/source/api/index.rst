API Reference
=============

This section contains the API documentation for InstrMCP modules.

.. toctree::
   :maxdepth: 2

   servers
   tools
   extensions
   cli

Module Overview
---------------

InstrMCP is organized into several main modules:

Servers
~~~~~~~

The server modules implement MCP servers for different use cases:

- ``instrmcp.servers.jupyter_qcodes``: Main Jupyter+QCodes MCP server
- ``instrmcp.servers.qcodes``: Standalone QCodes station server

See :doc:`servers` for detailed API documentation.

Tools
~~~~~

The tools module provides utilities and helper functions:

- ``instrmcp.tools.stdio_proxy``: STDIO↔HTTP proxy for MCP clients

See :doc:`tools` for detailed API documentation.

Extensions
~~~~~~~~~~

Extensions add optional functionality:

- ``instrmcp.extensions.database``: Database integration
- ``instrmcp.extensions.MeasureIt``: MeasureIt template library
- ``instrmcp.extensions.jupyterlab``: JupyterLab extension

See :doc:`extensions` for detailed API documentation.

CLI
~~~

Command-line interface for server management:

- ``instrmcp.cli``: Main CLI entry point

See :doc:`cli` for detailed API documentation.

Quick Links
-----------

Commonly Used Classes and Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Server Classes**:

- :py:class:`instrmcp.servers.jupyter_qcodes.mcp_server.JupyterQCodesMCPServer`
- :py:class:`instrmcp.tools.stdio_proxy.HttpMCPProxy`

**Tool Functions**:

- :py:func:`instrmcp.servers.jupyter_qcodes.tools.QCodesReadOnlyTools.get_parameter_values`
- :py:func:`instrmcp.servers.jupyter_qcodes.tools.QCodesReadOnlyTools.list_variables`

**Registrars**:

- :py:class:`instrmcp.servers.jupyter_qcodes.registrars.QCodesToolRegistrar`
- :py:class:`instrmcp.servers.jupyter_qcodes.registrars.NotebookToolRegistrar`

**Extension Functions**:

- :py:func:`instrmcp.extensions.database.query_tools.list_experiments`
- :py:func:`instrmcp.extensions.MeasureIt.measureit_templates.get_sweep1d_template`