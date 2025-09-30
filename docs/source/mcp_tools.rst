MCP Tools Reference
===================

This page documents all available MCP tools provided by InstrMCP.

Notebook Tools
--------------

These tools provide safe, read-only access to Jupyter notebook state.

list_variables
~~~~~~~~~~~~~~

List variables in the Jupyter namespace.

**Parameters**:

- ``type_filter`` (str, optional): Filter by type (e.g., "array", "dict", "instrument")

**Returns**: JSON list of variables with names, types, and basic information

**Example usage via Claude**:

"Show me all array variables in the notebook"

get_variable_info
~~~~~~~~~~~~~~~~~

Get detailed information about a specific notebook variable.

**Parameters**:

- ``name`` (str): Variable name

**Returns**: JSON with variable details, shape, dtype, preview

**Example usage via Claude**:

"Tell me about the 'data' variable"

get_editing_cell
~~~~~~~~~~~~~~~~

Get the content of the currently active/editing cell in JupyterLab.

**Parameters**:

- ``fresh_ms`` (int, optional): Maximum age in milliseconds. Default 1000.

**Returns**: JSON with cell content, execution count, cell type

**Example usage via Claude**:

"What code is in the current cell?"

get_editing_cell_output
~~~~~~~~~~~~~~~~~~~~~~~

Get the output from the most recently executed cell.

**Parameters**: None

**Returns**: JSON with cell output, execution status, error information if any

**Example usage via Claude**:

"What was the output of the last cell I ran?"

get_notebook_cells
~~~~~~~~~~~~~~~~~~

Get recent notebook cells with input, output, and error information.

**Parameters**:

- ``num_cells`` (int, optional): Number of recent cells to retrieve. Default 2.
- ``include_output`` (bool, optional): Include cell outputs. Default True.

**Returns**: JSON array of cell objects with input, output, execution count

**Example usage via Claude**:

"Show me the last 5 cells with their outputs"

move_cursor
~~~~~~~~~~~

Move the cursor (change active cell) to a different cell in the notebook.

**Parameters**:

- ``target`` (str): Where to move:

  - ``"above"`` - Move to cell above current
  - ``"below"`` - Move to cell below current
  - ``"<number>"`` - Move to cell with that execution count (e.g., "5")

**Returns**: JSON with operation status, old index, new index

**Example usage via Claude**:

- "Move to the next cell"
- "Go to the previous cell"
- "Jump to cell 5"

server_status
~~~~~~~~~~~~~

Get server status and configuration.

**Parameters**: None

**Returns**: JSON with server mode, tools count, active tools list

**Example usage via Claude**:

"What mode is the MCP server in?"

QCodes Instrument Tools
------------------------

These tools provide read-only access to QCodes instruments.

instrument_info
~~~~~~~~~~~~~~~

Get detailed information about a QCodes instrument.

**Parameters**:

- ``name`` (str): Instrument name
- ``with_values`` (bool, optional): Include current parameter values. Default False.

**Returns**: JSON with instrument details, parameters, current values (if requested)

**Example usage via Claude**:

- "Show me details about the SR830 lock-in"
- "What parameters does the DAC have?"

get_parameter_values
~~~~~~~~~~~~~~~~~~~~

Read parameter values from QCodes instruments. Supports both single and batch queries.

**Parameters**:

- ``queries`` (str): Parameter query string(s)

  - Single: ``"lockin.X"``
  - Multiple (comma-separated): ``"lockin.X, lockin.Y, dac.ch01.voltage"``

**Returns**: JSON with parameter values, timestamps, units

**Example usage via Claude**:

- "What is the X voltage of the lock-in?"
- "Read dac.ch01.voltage and dac.ch02.voltage"
- "Get all lock-in readings: X, Y, R, and phase"

**Batch reading**: Multiple parameters are read in a single operation for efficiency.

Unsafe Tools
------------

These tools are only available when unsafe mode is enabled (``%mcp_unsafe``).

.. warning::
   These tools allow code execution and cell modification. Use with caution.

update_editing_cell
~~~~~~~~~~~~~~~~~~~

Update the content of the currently active cell.

**Parameters**:

- ``content`` (str): New Python code content

**Returns**: JSON with operation status

**Example usage via Claude**:

"Replace the current cell with: import numpy as np"

execute_editing_cell
~~~~~~~~~~~~~~~~~~~~

Execute the code in the currently active cell.

**Parameters**: None

**Returns**: JSON with execution status, request ID

**Example usage via Claude**:

"Run the current cell"

.. warning::
   This executes arbitrary code. Only use in unsafe mode.

add_new_cell
~~~~~~~~~~~~

Add a new cell relative to the currently active cell.

**Parameters**:

- ``cell_type`` (str, optional): "code", "markdown", or "raw". Default "code".
- ``position`` (str, optional): "above" or "below". Default "below".
- ``content`` (str, optional): Initial cell content. Default empty.

**Returns**: JSON with operation status, cell details

**Example usage via Claude**:

- "Add a new code cell below with: print('hello')"
- "Insert a markdown cell above"

delete_editing_cell
~~~~~~~~~~~~~~~~~~~

Delete the currently active cell.

**Parameters**: None

**Returns**: JSON with deletion status

**Example usage via Claude**:

"Delete the current cell"

.. warning::
   This permanently removes the cell from the notebook.

apply_patch
~~~~~~~~~~~

Apply a text replacement patch to the active cell. More efficient than replacing entire cell content.

**Parameters**:

- ``old_text`` (str): Text to find and replace
- ``new_text`` (str): Replacement text

**Returns**: JSON with patch status

**Example usage via Claude**:

"Change 'np.array' to 'np.asarray' in the current cell"

delete_cells_by_number
~~~~~~~~~~~~~~~~~~~~~~

Delete multiple cells by their execution count numbers.

**Parameters**:

- ``cell_numbers`` (str): Comma-separated execution counts (e.g., "1,2,5")

**Returns**: JSON with deletion results for each cell

**Example usage via Claude**:

"Delete cells 3, 5, and 7"

Database Tools (Optional)
--------------------------

These tools require ``%mcp_option database`` to be enabled.

list_experiments
~~~~~~~~~~~~~~~~

List all experiments in the QCodes database.

**Parameters**:

- ``database_path`` (str, optional): Path to database file. Uses default if not provided.

**Returns**: JSON array of experiments with IDs, names, sample info, timestamps

**Example usage via Claude**:

"Show me all experiments in the database"

get_dataset_info
~~~~~~~~~~~~~~~~

Get detailed information about a specific dataset.

**Parameters**:

- ``id`` (int): Dataset ID
- ``database_path`` (str, optional): Path to database file

**Returns**: JSON with dataset metadata, parameters, run info, dependent/independent variables

**Example usage via Claude**:

"Show me details about dataset 42"

get_database_stats
~~~~~~~~~~~~~~~~~~

Get database statistics and health information.

**Parameters**:

- ``database_path`` (str, optional): Path to database file

**Returns**: JSON with total datasets, experiments, date range, size info

**Example usage via Claude**:

"Give me database statistics"

MeasureIt Tools (Optional)
---------------------------

These tools require ``%mcp_option measureit`` to be enabled.

get_measureit_status
~~~~~~~~~~~~~~~~~~~~

Check if any MeasureIt sweep is currently running.

**Parameters**: None

**Returns**: JSON with running status, sweep details if active

**Example usage via Claude**:

"Is a measurement running?"

Tool Call Examples
------------------

Here are complete examples of how Claude interacts with these tools:

**Example 1: Instrument Reading**

.. code-block:: text

   User: "What is the X voltage from the lock-in amplifier?"

   Claude: [Calls instrument_info to find lock-in name]
   Claude: [Calls get_parameter_values("lockin.X")]
   Claude: "The X voltage from the lock-in is 2.345 mV."

**Example 2: Notebook Inspection**

.. code-block:: text

   User: "What arrays do I have in memory?"

   Claude: [Calls list_variables(type_filter="array")]
   Claude: "You have 3 arrays: 'data' (1000,), 'voltage' (100,), 'time' (100,)"

**Example 3: Cell Navigation**

.. code-block:: text

   User: "Move to the next cell and show me its content"

   Claude: [Calls move_cursor("below")]
   Claude: [Calls get_editing_cell()]
   Claude: "Moved to cell [5]. It contains: import matplotlib.pyplot as plt"

**Example 4: Database Query**

.. code-block:: text

   User: "What measurements did I run today?"

   Claude: [Calls list_experiments()]
   Claude: [Filters by date]
   Claude: "You ran 3 experiments today: 'IV_sweep' at 10:30, ..."

Best Practices
--------------

- **Use batch reads**: Combine multiple parameter reads into one ``get_parameter_values`` call
- **Check server status**: Verify mode before requesting unsafe operations
- **Limit cell history**: Request only needed cells with ``num_cells`` parameter
- **Fresh data**: Use ``fresh_ms`` parameter when you need recent cell content
- **Safe operations**: Prefer read-only tools when possible