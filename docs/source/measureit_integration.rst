MeasureIt Integration
=====================

InstrMCP provides optional integration with MeasureIt, offering measurement templates and pattern libraries for code generation.

Overview
--------

The MeasureIt integration is an optional feature that provides:

- Comprehensive measurement pattern templates
- Code examples for common sweep types
- Best practices and common patterns
- Real-time sweep status monitoring

Enable with:

.. code-block:: python

   %mcp_option measureit
   %mcp_restart

MeasureIt Tools
---------------

get_measureit_status
~~~~~~~~~~~~~~~~~~~~

Check if any MeasureIt sweep is currently running.

**Parameters**: None

**Returns**: JSON with:

- Running status (boolean)
- Sweep type (if running)
- Current progress
- Estimated completion

**Example via Claude**:

"Is a measurement currently running?"

MeasureIt Resources
-------------------

The integration provides several MCP resources with code templates:

measureit_sweep0d_template
~~~~~~~~~~~~~~~~~~~~~~~~~~

Time-based monitoring patterns (Sweep0D):

- Continuous monitoring
- Time-series data collection
- Fixed-interval sampling
- Real-time plotting

**Example template**:

.. code-block:: python

   from MeasureIt import Sweep0D

   sweep = Sweep0D(dmm.voltage, delay=1.0)
   sweep.follow_param(dmm.current)
   sweep.follow_param(temperature.value)

   data = sweep.run(max_time=3600)  # 1 hour

**Use case**: Monitoring temperature drift, tracking lock-in signals

measureit_sweep1d_template
~~~~~~~~~~~~~~~~~~~~~~~~~~

Single parameter sweep patterns (Sweep1D):

- Linear sweeps
- Voltage/gate sweeps
- Frequency scans
- Current sweeps

**Example template**:

.. code-block:: python

   from MeasureIt import Sweep1D

   sweep = Sweep1D(
       gate.voltage,
       np.linspace(-1, 1, 201),
       inter_delay=0.01
   )
   sweep.follow_param(dmm.current)
   sweep.follow_param(lockin.X)

   data = sweep.ramp(save=True, plot=True)

**Use case**: IV curves, transfer characteristics, spectroscopy

measureit_sweep2d_template
~~~~~~~~~~~~~~~~~~~~~~~~~~

2D parameter mapping patterns (Sweep2D):

- Gate maps
- Stability diagrams
- Color plots
- Heatmaps

**Example template**:

.. code-block:: python

   from MeasureIt import Sweep2D

   sweep = Sweep2D(
       gate1.voltage, np.linspace(-2, 2, 101),
       gate2.voltage, np.linspace(-2, 2, 101),
       inter_delay=0.01
   )
   sweep.follow_param(dmm.current)

   data = sweep.ramp(save=True, plot=True)

**Use case**: Charge stability diagrams, 2D maps

measureit_simulsweep_template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simultaneous parameter sweep patterns:

- Multiple parameters swept together
- Coordinated motion
- Synchronous measurements

**Example template**:

.. code-block:: python

   from MeasureIt import SimulSweep

   sweep = SimulSweep(
       [gate1.voltage, gate2.voltage],
       [np.linspace(-1, 1, 101), np.linspace(0, 2, 101)],
       inter_delay=0.01
   )
   sweep.follow_param(dmm.current)

   data = sweep.ramp(save=True, plot=True)

**Use case**: Balanced gate sweeps, ratio measurements

measureit_sweepqueue_template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sequential measurement workflow patterns:

- Multiple sweep sequence
- Automated measurement series
- Parameter space exploration
- Overnight measurements

**Example template**:

.. code-block:: python

   from MeasureIt import SweepQueue, Sweep1D

   queue = SweepQueue()

   # Add multiple sweeps
   for temp in [4.2, 10, 20, 30]:
       temperature.target(temp)
       temperature.wait_until_stable()

       sweep = Sweep1D(
           gate.voltage,
           np.linspace(-1, 1, 201),
           inter_delay=0.01
       )
       sweep.follow_param(dmm.current)

       queue.add(sweep, name=f"IV_T{temp}K")

   queue.run()

**Use case**: Temperature series, multi-sample measurements

measureit_common_patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~

Best practices and common patterns:

- Error handling
- Data saving conventions
- Plot configurations
- Post-processing
- File organization

measureit_code_examples
~~~~~~~~~~~~~~~~~~~~~~~

Complete collection of all MeasureIt patterns in structured format:

- All sweep types
- Full working examples
- Parameter explanations
- Common use cases

Code Generation
---------------

Claude uses these templates to generate measurement code:

Pattern-Based Generation
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   User: "Generate code to do an IV curve from -1V to 1V"

   Claude: [Accesses measureit_sweep1d_template resource]
   Claude: "Here's the code for your IV curve:
           ```python
           from MeasureIt import Sweep1D
           import numpy as np

           sweep = Sweep1D(
               source.voltage,
               np.linspace(-1, 1, 201),
               inter_delay=0.01
           )
           sweep.follow_param(dmm.current)

           data = sweep.ramp(save=True, plot=True)
           ```"

Context-Aware Suggestions
~~~~~~~~~~~~~~~~~~~~~~~~~

Claude considers:

- Available instruments in notebook
- Previous measurement patterns
- Common sweep parameters
- Best practices

Example:

.. code-block:: text

   User: "I want to measure a charge stability diagram"

   Claude: [Knows this is 2D sweep]
   Claude: [Accesses measureit_sweep2d_template]
   Claude: [Checks for available gate instruments]
   Claude: "Based on your gates (left_gate and right_gate), here's a
           stability diagram measurement: ..."

Sweep Configuration
-------------------

Common Parameters
~~~~~~~~~~~~~~~~~

**Sweep1D**:

- ``setpoint_parameter``: Parameter to sweep
- ``setpoint_values``: Array of values (use ``np.linspace``)
- ``inter_delay``: Delay between points (seconds)
- ``bidirectional``: Sweep both directions
- ``continual``: Continuous sweeping

**Sweep2D**:

- Two setpoint parameters
- Two setpoint value arrays
- ``fast_axis``: Which parameter is inner loop
- ``inter_delay``: Delay between points

**Sweep0D**:

- ``follow_param``: Parameter to monitor
- ``delay``: Time between measurements
- ``max_time``: Duration (seconds)

Data Management
~~~~~~~~~~~~~~~

Automatic saving:

.. code-block:: python

   sweep.ramp(save=True, plot=True)

Custom save location:

.. code-block:: python

   sweep.set_database(db_path="/path/to/database.db")
   data = sweep.ramp(save=True)

Real-time Plotting
~~~~~~~~~~~~~~~~~~

Enable live plots:

.. code-block:: python

   sweep.ramp(plot=True)

Custom plot configuration:

.. code-block:: python

   sweep.plot_config = {
       'xlabel': 'Gate Voltage (V)',
       'ylabel': 'Current (nA)',
       'title': 'IV Curve'
   }

Status Monitoring
-----------------

Check Running Sweeps
~~~~~~~~~~~~~~~~~~~~

Via Claude:

.. code-block:: text

   User: "Is a measurement running?"

   Claude: [Calls get_measureit_status()]
   Claude: "Yes, Sweep1D is running: 45% complete (90/200 points), ETA 2:30"

Via Python:

.. code-block:: python

   from instrmcp.extensions.MeasureIt import get_sweep_status

   status = get_sweep_status()
   print(f"Running: {status['is_running']}")
   print(f"Progress: {status['progress']}%")

Best Practices
--------------

Delays and Settling
~~~~~~~~~~~~~~~~~~~

Always allow sufficient settling time:

.. code-block:: python

   sweep = Sweep1D(
       gate.voltage,
       np.linspace(-1, 1, 201),
       inter_delay=0.05  # 50ms between points
   )

For slow instruments (e.g., temperature):

.. code-block:: python

   sweep = Sweep0D(temperature.value, delay=10.0)  # 10s between readings

Data Organization
~~~~~~~~~~~~~~~~~

Use descriptive names:

.. code-block:: python

   sweep.metadata = {
       'sample': 'DeviceA',
       'cooldown': 'CD123',
       'purpose': 'Initial characterization'
   }

Error Handling
~~~~~~~~~~~~~~

Wrap sweeps in try/except:

.. code-block:: python

   try:
       data = sweep.ramp(save=True, plot=True)
   except KeyboardInterrupt:
       print("Sweep interrupted, data saved")
       raise
   except Exception as e:
       print(f"Sweep failed: {e}")
       # Emergency stop procedures
       gate.voltage(0)

Safety Limits
~~~~~~~~~~~~~

Set instrument limits:

.. code-block:: python

   # Set voltage limit
   source.voltage.step = 0.01  # Max 10mV steps
   source.voltage.inter_delay = 0.1  # Wait between steps

   # Compliance
   source.current.limit(1e-6)  # 1µA compliance

Integration with Database
--------------------------

MeasureIt measurements automatically save to QCodes database:

.. code-block:: python

   # Data saved with metadata
   data = sweep.ramp(save=True)

   # Access dataset ID
   print(f"Dataset ID: {data.run_id}")

Query later via database integration:

.. code-block:: text

   User: "Show me the measurement I just ran"

   Claude: [Calls list_experiments()]
   Claude: [Finds most recent]
   Claude: "Dataset #247: 'Sweep1D_gate_voltage' from 2 minutes ago"

Customization
-------------

Custom Sweep Templates
~~~~~~~~~~~~~~~~~~~~~~

Add your own templates in:

``instrmcp/extensions/MeasureIt/measureit_templates.py``

Example:

.. code-block:: python

   CUSTOM_TEMPLATE = '''
   # My Custom Measurement Pattern
   from MeasureIt import Sweep1D

   def my_custom_measurement(device):
       sweep = Sweep1D(
           device.gate,
           np.linspace(-2, 2, 401),
           inter_delay=0.02
       )
       sweep.follow_param(device.current)
       sweep.follow_param(device.voltage)

       return sweep.ramp(save=True, plot=True)
   '''

Register as resource:

.. code-block:: python

   @mcp.resource("measureit_custom_template")
   async def custom_template() -> List[TextContent]:
       return [TextContent(type="text", text=CUSTOM_TEMPLATE)]

Troubleshooting
---------------

MeasureIt Not Found
~~~~~~~~~~~~~~~~~~~

If MeasureIt is not installed:

.. code-block:: bash

   pip install measureit  # or appropriate installation method

Verify import:

.. code-block:: python

   import MeasureIt
   print(MeasureIt.__version__)

Templates Not Loading
~~~~~~~~~~~~~~~~~~~~~

If templates don't appear:

1. Verify MeasureIt option is enabled: ``%mcp_option``
2. Restart server: ``%mcp_restart``
3. Check resource availability via Claude: "What MeasureIt templates are available?"

Status Tool Not Working
~~~~~~~~~~~~~~~~~~~~~~~

If status tool fails:

1. Ensure measurement is running
2. Check MeasureIt version compatibility
3. Verify status checking mechanism in your MeasureIt version

Advanced Usage
--------------

Nested Sweeps
~~~~~~~~~~~~~

Combine sweep types:

.. code-block:: python

   from MeasureIt import Sweep1D, Sweep2D

   # Outer: Temperature
   for temp in [4, 10, 20]:
       temperature.target(temp)
       temperature.wait_stable()

       # Inner: 2D gate sweep
       sweep = Sweep2D(
           gate1.voltage, np.linspace(-2, 2, 51),
           gate2.voltage, np.linspace(-2, 2, 51)
       )
       sweep.follow_param(current)
       sweep.ramp(save=True)

Conditional Measurements
~~~~~~~~~~~~~~~~~~~~~~~~

Stop sweep based on condition:

.. code-block:: python

   def stop_condition(data):
       current = data['current'][-1]
       return abs(current) > 1e-6  # Stop if >1µA

   sweep.add_break_condition(stop_condition)
   data = sweep.ramp(save=True)

Parallel Measurements
~~~~~~~~~~~~~~~~~~~~~

Multiple instruments simultaneously:

.. code-block:: python

   sweep.follow_param(lockin1.X)
   sweep.follow_param(lockin2.X)
   sweep.follow_param(dmm.voltage)
   sweep.follow_param(dmm.current)

   data = sweep.ramp(save=True)

Further Reading
---------------

- MeasureIt documentation
- QCodes measurement tutorial
- InstrMCP database integration
- Example notebooks in repository