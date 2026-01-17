Installation
============

Requirements
------------

- Python 3.8 or higher
- JupyterLab 4.0 or higher
- QCodes 0.45.0 or higher
- Git (for source installation)

Installation from Source
-------------------------

Currently, InstrMCP is available via source installation:

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/caidish/instrMCP.git
   cd instrMCP

   # Install in development mode
   pip install -e .

   # Or install with all optional dependencies
   pip install -e .[full]

The package will be automatically installed in editable mode, which is ideal for development and allows you to make changes to the code without reinstalling.

Optional Dependencies
---------------------

InstrMCP provides several optional dependency groups:

**Jupyter Integration** (included in base install):

.. code-block:: bash

   pip install -e .[jupyter]

**QCodes Support** (included in base install):

.. code-block:: bash

   pip install -e .[qcodes]

**Development Tools**:

.. code-block:: bash

   pip install -e .[dev]

**Documentation**:

.. code-block:: bash

   pip install -e .[docs]

**All Features**:

.. code-block:: bash

   pip install -e .[full]

JupyterLab Extension
--------------------

The JupyterLab extension is automatically installed when you install InstrMCP. After installation:

1. Restart JupyterLab completely
2. The ``mcp-active-cell-bridge`` extension should be active
3. Verify installation:

.. code-block:: bash

   jupyter labextension list

You should see ``mcp-active-cell-bridge`` listed among enabled extensions.

Verification
------------

To verify your installation:

.. code-block:: bash

   # Check version
   instrmcp version

   # View configuration
   instrmcp config

Then start JupyterLab and test the server:

.. code-block:: python

   # In a Jupyter notebook cell:
   %load_ext instrmcp.extensions
   %mcp_start
   %mcp_status

If everything is installed correctly, the server should start without errors.

Troubleshooting
---------------

**Extension not loading**:

If the JupyterLab extension doesn't load:

.. code-block:: bash

   # Rebuild the extension
   cd instrmcp/extensions/jupyterlab
   jlpm run build

   # Reinstall package
   pip install -e . --force-reinstall --no-deps

**Import errors**:

If you encounter import errors, ensure all dependencies are installed:

.. code-block:: bash

   pip install -e .[full]

**QCodes not found**:

Make sure QCodes is properly installed:

.. code-block:: bash

   pip install qcodes>=0.45.0

Next Steps
----------

After installation, proceed to the :doc:`quickstart` guide to learn how to use InstrMCP.