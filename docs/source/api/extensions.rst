Extensions
==========

This module contains optional extensions for InstrMCP.

Database Extension
------------------

Database Resources
~~~~~~~~~~~~~~~~~~

.. automodule:: instrmcp.extensions.database.db_resources
   :members:
   :undoc-members:
   :show-inheritance:

Query Tools
~~~~~~~~~~~

.. automodule:: instrmcp.extensions.database.query_tools
   :members:
   :undoc-members:
   :show-inheritance:

Key Functions
^^^^^^^^^^^^^

list_experiments
""""""""""""""""

.. autofunction:: instrmcp.extensions.database.query_tools.list_experiments

   List all experiments in a QCodes database.

   **Returns**: Array of experiment dictionaries with ID, name, sample, timestamps

get_dataset_info
""""""""""""""""

.. autofunction:: instrmcp.extensions.database.query_tools.get_dataset_info

   Get detailed information about a specific dataset.

   **Returns**: Dataset metadata, parameters, run information

get_database_stats
""""""""""""""""""

.. autofunction:: instrmcp.extensions.database.query_tools.get_database_stats

   Get aggregate statistics about the database.

   **Returns**: Total datasets, experiments, date range, size info

MeasureIt Extension
-------------------

MeasureIt Templates
~~~~~~~~~~~~~~~~~~~

.. automodule:: instrmcp.extensions.measureit.measureit_templates
   :members:
   :undoc-members:
   :show-inheritance:

Template Functions
^^^^^^^^^^^^^^^^^^

get_sweep0d_template
""""""""""""""""""""

.. autofunction:: instrmcp.extensions.measureit.measureit_templates.get_sweep0d_template

   Get template for time-based monitoring (Sweep0D).

get_sweep1d_template
""""""""""""""""""""

.. autofunction:: instrmcp.extensions.measureit.measureit_templates.get_sweep1d_template

   Get template for 1D parameter sweeps.

get_sweep2d_template
""""""""""""""""""""

.. autofunction:: instrmcp.extensions.measureit.measureit_templates.get_sweep2d_template

   Get template for 2D parameter mapping.

get_simulsweep_template
"""""""""""""""""""""""

.. autofunction:: instrmcp.extensions.measureit.measureit_templates.get_simulsweep_template

   Get template for simultaneous parameter sweeps.

get_sweepqueue_template
"""""""""""""""""""""""

.. autofunction:: instrmcp.extensions.measureit.measureit_templates.get_sweepqueue_template

   Get template for sequential measurement workflows.

get_common_patterns
"""""""""""""""""""

.. autofunction:: instrmcp.extensions.measureit.measureit_templates.get_common_patterns

   Get common MeasureIt patterns and best practices.

get_all_examples
""""""""""""""""

.. autofunction:: instrmcp.extensions.measureit.measureit_templates.get_all_examples

   Get complete collection of all MeasureIt patterns.

JupyterLab Extension
--------------------

The JupyterLab extension is implemented in TypeScript and provides:

- Active cell content bridging
- Cell execution
- Cell manipulation
- Cursor movement

**Source location**: ``instrmcp/extensions/jupyterlab/src/index.ts``

Key Components
~~~~~~~~~~~~~~

Extension Activation
^^^^^^^^^^^^^^^^^^^^

The extension is activated when JupyterLab loads and registers:

- Comm message handlers
- Cell operation handlers
- Response message handlers

Comm Protocol
^^^^^^^^^^^^^

Messages sent from Python kernel to frontend:

- ``get_cell``: Request current cell content
- ``update_cell``: Update cell content
- ``execute_cell``: Execute cell code
- ``add_cell``: Add new cell
- ``delete_cell``: Delete cell
- ``apply_patch``: Apply text patch
- ``move_cursor``: Change active cell

Response messages from frontend to kernel:

- ``cell_data``: Cell content response
- ``update_response``: Update confirmation
- ``execute_response``: Execution confirmation
- ``add_cell_response``: Addition confirmation
- ``delete_cell_response``: Deletion confirmation
- ``apply_patch_response``: Patch confirmation
- ``move_cursor_response``: Cursor movement confirmation

Building the Extension
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   cd instrmcp/extensions/jupyterlab
   jlpm run build

The build process:

1. Compiles TypeScript to JavaScript
2. Bundles with webpack
3. Copies files to labextension directory
4. Updates package.json with build metadata

See :doc:`../jupyter_integration` for more details on the extension architecture.