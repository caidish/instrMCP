CLI
===

Command-line interface for InstrMCP server management.

Main CLI Module
---------------

.. automodule:: instrmcp.cli
   :members:
   :undoc-members:
   :show-inheritance:

Commands
--------

The ``instrmcp`` command provides several subcommands:

version
~~~~~~~

Show InstrMCP version information.

.. code-block:: bash

   instrmcp version

**Output**:

.. code-block:: text

   InstrMCP version 1.0.0

config
~~~~~~

Show configuration information including installation path and environment.

.. code-block:: bash

   instrmcp config

**Output**:

.. code-block:: text

   InstrMCP Configuration
   Installation path: /path/to/instrmcp
   Python: 3.11.x
   QCodes: 0.45.x

jupyter
~~~~~~~

Start the Jupyter MCP server.

.. code-block:: bash

   instrmcp jupyter [OPTIONS]

**Options**:

- ``--port PORT``: Port number (default: 8123)
- ``--host HOST``: Host address (default: 127.0.0.1)
- ``--unsafe``: Enable unsafe mode (allows code execution)
- ``--database``: Enable database integration
- ``--measureit``: Enable MeasureIt templates

**Examples**:

.. code-block:: bash

   # Start server on default port (8123)
   instrmcp jupyter

   # Start on custom port
   instrmcp jupyter --port 3000

   # Start with unsafe mode enabled
   instrmcp jupyter --port 8123 --unsafe

   # Start with all optional features
   instrmcp jupyter --database --measureit

qcodes
~~~~~~

Start standalone QCodes station server (without Jupyter).

.. code-block:: bash

   instrmcp qcodes [OPTIONS]

**Options**:

- ``--port PORT``: Port number (default: 8124)
- ``--host HOST``: Host address (default: 127.0.0.1)
- ``--station PATH``: Path to station YAML file

**Examples**:

.. code-block:: bash

   # Start with default station
   instrmcp qcodes

   # Use custom station file
   instrmcp qcodes --station /path/to/station.yaml

setup
~~~~~

Run setup utilities and configuration.

.. code-block:: bash

   instrmcp setup [OPTIONS]

**Options**:

- ``--claude-desktop``: Setup Claude Desktop integration
- ``--codex``: Setup Codex integration
- ``--all``: Setup all integrations

**Examples**:

.. code-block:: bash

   # Setup all integrations
   instrmcp setup --all

   # Setup only Claude Desktop
   instrmcp setup --claude-desktop

Setup Utilities
---------------

.. automodule:: instrmcp.setup_utils
   :members:
   :undoc-members:
   :show-inheritance:

Key Functions
~~~~~~~~~~~~~

setup_all
^^^^^^^^^

.. autofunction:: instrmcp.setup_utils.setup_all

   Run all setup procedures.

   This configures:

   - JupyterLab extension
   - Claude Desktop integration
   - Codex integration
   - Environment variables

Server CLI Modules
------------------

Jupyter QCodes CLI
~~~~~~~~~~~~~~~~~~

.. automodule:: instrmcp.servers.jupyter_qcodes.cli
   :members:
   :undoc-members:
   :show-inheritance:

Standalone Runner
~~~~~~~~~~~~~~~~~

.. automodule:: instrmcp.servers.jupyter_qcodes.run_standalone
   :members:
   :undoc-members:
   :show-inheritance:

Environment Variables
---------------------

InstrMCP respects the following environment variables:

INSTRMCP_PATH
~~~~~~~~~~~~~

Installation path for InstrMCP.

.. code-block:: bash

   export INSTRMCP_PATH=/path/to/instrmcp

Used by launcher scripts to locate InstrMCP installation.

MEASUREIT_HOME
~~~~~~~~~~~~~~

Path to MeasureIt installation (if using MeasureIt integration).

.. code-block:: bash

   export MEASUREIT_HOME=/path/to/measureit

Used to find default database location:
``$MEASUREIT_HOME/Databases/Example_database.db``

QCODES_DB_LOCATION
~~~~~~~~~~~~~~~~~~

Default QCodes database path.

.. code-block:: bash

   export QCODES_DB_LOCATION=/path/to/database.db

Or set in QCodes config:

.. code-block:: python

   import qcodes as qc
   qc.config.core.db_location = "/path/to/database.db"

Exit Codes
----------

The CLI uses standard exit codes:

- ``0``: Success
- ``1``: General error
- ``2``: Invalid usage/arguments
- ``130``: Interrupted (Ctrl+C)

Example Usage
-------------

Typical Workflow
~~~~~~~~~~~~~~~~

1. **Start server in JupyterLab**:

.. code-block:: bash

   jupyter lab

Then in notebook:

.. code-block:: python

   %load_ext instrmcp
   %mcp_start

2. **Or start standalone**:

.. code-block:: bash

   instrmcp jupyter --port 8123

3. **Connect Claude Desktop** using launcher:

.. code-block:: bash

   python claudedesktopsetting/claude_launcher.py

Development Workflow
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install in development mode
   pip install -e .[dev]

   # Run with unsafe mode for testing
   instrmcp jupyter --port 8123 --unsafe

   # Enable all features
   instrmcp jupyter --database --measureit --unsafe

   # Check version
   instrmcp version

   # View configuration
   instrmcp config