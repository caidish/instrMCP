CLI
===

Command-line interface for InstrMCP utilities.

Main CLI Module
---------------

.. automodule:: instrmcp.cli
   :members:
   :undoc-members:
   :show-inheritance:

Commands
--------

The ``instrmcp`` command provides the following subcommands:

version
~~~~~~~

Show InstrMCP version information.

.. code-block:: bash

   instrmcp version

**Output**:

.. code-block:: text

   InstrMCP version 2.2.0

config
~~~~~~

Show configuration information including installation path and optional extensions.

.. code-block:: bash

   instrmcp config

**Output**:

.. code-block:: text

   InstrMCP Configuration:
   Version: 2.2.0
   Package path: /path/to/instrmcp

   Optional Extensions:
     ✅ measureit: 1.0.0

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

   %load_ext instrmcp.extensions
   %mcp_start

2. **Connect Claude Desktop** using launcher:

.. code-block:: bash

   python agentsetting/claudedesktopsetting/claude_launcher.py

metadata tokens
~~~~~~~~~~~~~~~

Count tokens used by tool/resource metadata descriptions. Useful for optimizing context budget.
By default uses the Anthropic API for exact counts, with automatic fallback to tiktoken.

.. code-block:: bash

   instrmcp metadata tokens                    # API (auto-fallback to tiktoken)
   instrmcp metadata tokens --offline          # Force tiktoken offline estimation
   instrmcp metadata tokens --source merged    # Include user overrides
   instrmcp metadata tokens --format json      # JSON output

The standalone script is also available: ``python tools/token_count.py``

Development Workflow
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install in development mode
   pip install -e .[dev]

   # Check version
   instrmcp version

   # View configuration
   instrmcp config
