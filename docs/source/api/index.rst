API Reference
=============

This section contains the API documentation for InstrMCP modules.

.. toctree::
   :maxdepth: 2

   servers
   utils
   extensions
   cli

Module Overview
---------------

InstrMCP is organized into several main modules:

Servers
~~~~~~~

The server modules implement MCP servers:

- ``instrmcp.servers.jupyter_qcodes``: Main Jupyter+QCodes MCP server

See :doc:`servers` for detailed API documentation.

Utils
~~~~~

The utils module provides internal utilities and helper functions:

- ``instrmcp.utils.stdio_proxy``: STDIO↔HTTP proxy for MCP clients

See :doc:`utils` for detailed API documentation.

Extensions
~~~~~~~~~~

Extensions add optional functionality:

- ``instrmcp.extensions.database``: Database integration
- ``instrmcp.extensions.measureit``: MeasureIt template library
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

**Tool Functions**:

- :py:func:`instrmcp.servers.jupyter_qcodes.tools.QCodesReadOnlyTools.get_parameter_values`
- :py:func:`instrmcp.servers.jupyter_qcodes.tools.QCodesReadOnlyTools.list_variables`

**Registrars**:

- :py:class:`instrmcp.servers.jupyter_qcodes.core.QCodesToolRegistrar`
- :py:class:`instrmcp.servers.jupyter_qcodes.core.NotebookToolRegistrar`

**Extension Functions**:

- :py:func:`instrmcp.extensions.database.query_tools.list_experiments`
- :py:func:`instrmcp.extensions.measureit.measureit_templates.get_sweep1d_template`