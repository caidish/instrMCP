Database Integration
====================

InstrMCP provides read-only access to QCodes databases, enabling LLMs to query measurement history and generate code based on past experiments.

Overview
--------

The database integration is an optional feature that provides:

- Read-only access to QCodes SQLite databases
- Metadata extraction from past measurements
- Measurement pattern recognition
- Code generation from historical data

Enable with:

.. code-block:: python

   %mcp_option database
   %mcp_restart

Database Tools
--------------

list_experiments
~~~~~~~~~~~~~~~~

List all experiments in the database.

**Parameters**:

- ``database_path`` (str, optional): Path to database. Uses default if not provided.

**Returns**: Array of experiments with:

- Experiment ID
- Name
- Sample name
- Start/end timestamps
- Number of datasets

**Example via Claude**:

"Show me all experiments in the database"

get_dataset_info
~~~~~~~~~~~~~~~~

Get detailed information about a specific dataset.

**Parameters**:

- ``id`` (int): Dataset ID
- ``database_path`` (str, optional): Path to database

**Returns**: Dataset metadata including:

- Run ID and name
- Experiment association
- Start/end times
- Parameter information (dependent/independent)
- Measurement metadata
- Parent/child datasets
- GUIDs and run description

**Example via Claude**:

"Tell me about dataset 42"

get_database_stats
~~~~~~~~~~~~~~~~~~

Get aggregate statistics about the database.

**Parameters**:

- ``database_path`` (str, optional): Path to database

**Returns**: Database statistics:

- Total number of datasets
- Total number of experiments
- Date range (first/last measurement)
- Database size
- Health indicators

**Example via Claude**:

"Give me statistics about my measurement database"

Database Resources
------------------

In addition to tools, the database integration provides MCP resources:

database_config
~~~~~~~~~~~~~~~

Current database configuration:

- Database path
- Connection status
- QCodes configuration
- MeasureIt integration status

**When to use**: LLMs use this to understand database location and setup

recent_measurements
~~~~~~~~~~~~~~~~~~~

Metadata for recent measurements across all experiments:

- Last N measurements (configurable)
- Run IDs, names, timestamps
- Parameter lists
- Experiment associations

**When to use**: Understanding recent experimental activity

measurement_templates
~~~~~~~~~~~~~~~~~~~~~

Common measurement patterns extracted from historical data:

- Frequently used parameter combinations
- Common sweep configurations
- Typical measurement structures

**When to use**: Code generation based on past experiments

Default Database Location
--------------------------

The database path is determined by:

1. **Explicit path**: If provided in tool call
2. **MeasureIt integration**: ``$MeasureItHome/Databases/Example_database.db``
3. **QCodes config**: From ``qcodes.config.core.db_location``

Check current database:

.. code-block:: python

   import qcodes as qc
   print(qc.config.core.db_location)

Database Structure
------------------

QCodes uses SQLite databases with the following structure:

Key Tables
~~~~~~~~~~

- **experiments**: Experiment metadata
- **runs**: Individual measurement runs (datasets)
- **layouts**: Parameter definitions
- **dependencies**: Parameter relationships

The database schema follows QCodes conventions. See QCodes documentation for details.

Example Queries
---------------

Via Claude Interface
~~~~~~~~~~~~~~~~~~~~

**Find recent IV curves**:

.. code-block:: text

   User: "Show me all IV curve measurements from the last week"

   Claude: [Calls list_experiments()]
   Claude: [Filters by name pattern and date]
   Claude: "Found 3 IV curve datasets: #142, #156, #189"

**Analyze measurement parameters**:

.. code-block:: text

   User: "What parameters were measured in dataset 150?"

   Claude: [Calls get_dataset_info(id=150)]
   Claude: "Dataset 150 measured:
           - Independent: gate_voltage (100 points)
           - Dependent: current, conductance
           - Duration: 5.2 minutes"

**Compare experiments**:

.. code-block:: text

   User: "Compare the parameters used in experiments 'sample_A' and 'sample_B'"

   Claude: [Calls list_experiments()]
   Claude: [Gets details for relevant datasets]
   Claude: "Both experiments measured IV curves, but sample_B added temperature"

Code Generation
---------------

The database integration enables intelligent code generation:

Pattern Recognition
~~~~~~~~~~~~~~~~~~~

Claude can analyze past measurements and suggest similar code:

.. code-block:: text

   User: "Generate code to measure an IV curve like I did last week"

   Claude: [Queries recent_measurements resource]
   Claude: [Finds IV curve pattern]
   Claude: "Based on dataset #156, here's the code:
           ```python
           from qcodes import Measurement

           meas = Measurement()
           meas.register_parameter(gate.voltage)
           meas.register_parameter(dmm.current)

           with meas.run() as datasaver:
               for v in np.linspace(-1, 1, 100):
                   gate.voltage(v)
                   current = dmm.current()
                   datasaver.add_result(
                       (gate.voltage, v),
                       (dmm.current, current)
                   )
           ```"

Template Extraction
~~~~~~~~~~~~~~~~~~~

Common patterns become reusable templates:

- Parameter sweep structures
- Data saver configurations
- Measurement loops
- Post-processing steps

Safety and Limitations
----------------------

Read-Only Access
~~~~~~~~~~~~~~~~

Database integration is strictly read-only:

- No dataset modification
- No experiment deletion
- No parameter changes
- Query-only operations

This ensures measurement data integrity.

Performance Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

- Database queries are cached briefly
- Large databases may have slower queries
- Use filters to limit result size
- Statistics are computed on-demand

Privacy
~~~~~~~

The LLM can see:

- All experiment metadata
- Parameter names and values
- Measurement timestamps
- Dataset relationships

Consider this when using cloud-based LLMs with proprietary data.

Configuration
-------------

Database Path
~~~~~~~~~~~~~

Set default database in QCodes config:

.. code-block:: python

   import qcodes as qc
   qc.config.core.db_location = "/path/to/database.db"

Or provide path explicitly in tool calls:

.. code-block:: python

   list_experiments(database_path="/custom/path/experiments.db")

MeasureIt Integration
~~~~~~~~~~~~~~~~~~~~~

When MeasureIt is available, the default database is:

.. code-block:: python

   $MeasureItHome/Databases/Example_database.db

This is set automatically if MeasureIt is installed.

Resource Configuration
~~~~~~~~~~~~~~~~~~~~~~

Configure resource behavior in ``db_resources.py``:

- Number of recent measurements
- Pattern recognition threshold
- Template generation rules

Troubleshooting
---------------

"Database not found"
~~~~~~~~~~~~~~~~~~~~

If database path is incorrect:

1. Check ``qcodes.config.core.db_location``
2. Verify file exists: ``ls /path/to/database.db``
3. Use explicit path in tool calls
4. Check file permissions

"No datasets returned"
~~~~~~~~~~~~~~~~~~~~~~

If queries return empty:

1. Verify database has data: ``get_database_stats()``
2. Check experiment name filters
3. Verify date range
4. Inspect database directly:

.. code-block:: bash

   sqlite3 /path/to/database.db
   SELECT COUNT(*) FROM runs;

"Database is locked"
~~~~~~~~~~~~~~~~~~~~

If database is in use:

1. Close other QCodes sessions
2. Wait for running measurements to complete
3. Use read-only connection (automatic in InstrMCP)

Performance Issues
~~~~~~~~~~~~~~~~~~

For slow queries on large databases:

1. Add more specific filters (experiment ID, date range)
2. Limit number of results
3. Use ``get_dataset_info`` for specific datasets
4. Consider database cleanup/archiving

Advanced Usage
--------------

Custom Database Queries
~~~~~~~~~~~~~~~~~~~~~~~

For advanced queries, you can extend the database tools in:

``instrmcp/extensions/database/query_tools.py``

Example custom query:

.. code-block:: python

   def find_measurements_by_parameter(
       param_name: str,
       database_path: Optional[str] = None
   ) -> List[Dict[str, Any]]:
       """Find all measurements that include a specific parameter."""
       db_path = get_default_db_path(database_path)

       with connect(db_path) as conn:
           cursor = conn.cursor()
           cursor.execute('''
               SELECT r.run_id, r.name, r.run_timestamp
               FROM runs r
               JOIN layouts l ON r.run_id = l.run_id
               WHERE l.parameter = ?
           ''', (param_name,))

           results = cursor.fetchall()
           return [
               {
                   "run_id": row[0],
                   "name": row[1],
                   "timestamp": row[2]
               }
               for row in results
           ]

Then register as MCP tool in ``registrars/database_tools.py``.

Database Migrations
~~~~~~~~~~~~~~~~~~~

QCodes databases evolve over time. InstrMCP uses QCodes' built-in schema handling:

.. code-block:: python

   from qcodes.dataset.sqlite.database import connect

   # Connection automatically handles schema version
   with connect(db_path) as conn:
       # Query using current schema
       pass

No manual migration needed.

Best Practices
--------------

1. **Use filters**: Limit query scope with experiment names, date ranges
2. **Cache results**: Avoid repeated identical queries
3. **Read-only mindset**: Never attempt to modify database
4. **Privacy awareness**: Consider data sensitivity when using cloud LLMs
5. **Verify paths**: Always check database location is correct
6. **Monitor size**: Large databases may need archiving
7. **Test queries**: Verify queries return expected data before automation