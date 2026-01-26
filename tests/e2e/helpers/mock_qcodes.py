"""
Mock QCodes station setup code for E2E tests.
"""

# Code to set up a mock QCodes station in the notebook
MOCK_QCODES_SETUP = '''
from qcodes import Station, Parameter
from qcodes.instrument import Instrument

class MockInstrument(Instrument):
    """Mock instrument for testing."""
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.add_parameter('voltage', unit='V', get_cmd=lambda: 1.23, set_cmd=lambda x: None)
        self.add_parameter('current', unit='A', get_cmd=lambda: 0.001, set_cmd=lambda x: None)
        self.add_parameter('frequency', unit='Hz', get_cmd=lambda: 1000, set_cmd=lambda x: None)

# Clean up any existing instances
try:
    Instrument.close_all()
except:
    pass

mock_instr = MockInstrument('mock_dmm')
station = Station()
station.add_component(mock_instr)
print("Mock QCodes station created successfully")
'''

# Code to set up test variables in the notebook
VARIABLE_TEST_SETUP = """
import numpy as np
import pandas as pd

# Simple types
x = 42
y = 3.14
my_string = "hello world"
my_bool = True

# Collections
my_list = [1, 2, 3, 4, 5]
my_dict = {"a": 1, "b": 2, "c": 3}
my_tuple = (10, 20, 30)
my_set = {1, 2, 3}

# NumPy arrays
arr = np.array([[1, 2, 3], [4, 5, 6]])
large_arr = np.zeros((100, 100))

# Pandas
df = pd.DataFrame({
    'col1': [1, 2, 3],
    'col2': ['a', 'b', 'c'],
    'col3': [1.1, 2.2, 3.3]
})

# Custom class
class MyClass:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"MyClass(value={self.value})"

obj = MyClass(42)

print("Test variables created successfully")
"""

# Standard notebook cell structure for testing
STANDARD_NOTEBOOK_CELLS = [
    {"type": "markdown", "source": "# Test Notebook Header", "execute": False},
    {"type": "code", "source": "x = 1", "execute": True},
    {"type": "markdown", "source": "## Section 1", "execute": False},
    {"type": "code", "source": "y = 2", "execute": True},
    {"type": "code", "source": "# unexecuted code cell", "execute": False},
    {"type": "markdown", "source": "## Section 2", "execute": False},
    {"type": "code", "source": "z = x + y", "execute": True},
    {"type": "code", "source": 'print("hello")', "execute": True},
]

# Security test patterns - code that should be blocked
BLOCKED_CODE_PATTERNS = [
    # Environment modification
    'os.environ["TEST"] = "value"',
    'os.environ.update({"TEST": "value"})',
    'os.putenv("TEST", "value")',
    # Dynamic execution
    'exec("print(1)")',
    'eval("1+1")',
    'compile("x=1", "<string>", "exec")',
    # Subprocess
    'os.system("ls")',
    'subprocess.run(["ls"])',
    'subprocess.Popen(["ls"])',
    # Aliased imports
    'import os as o; o.system("ls")',
    'from os import environ as e; e["TEST"] = "value"',
    'import subprocess as sp; sp.run(["ls"])',
]

# Code patterns that should be allowed
ALLOWED_CODE_PATTERNS = [
    "import numpy as np; np.array([1, 2, 3])",
    'print("hello world")',
    "1 + 2 * 3",
    'import os; os.path.join("a", "b")',
    "import os; os.getcwd()",
    "x = [i**2 for i in range(10)]",
]

# Safe mode tools that should be available
SAFE_MODE_TOOLS = [
    "mcp_list_resources",
    "mcp_get_resource",
    "notebook_server_status",
    "notebook_list_variables",
    "notebook_read_variable",
    "notebook_read_active_cell",
    "notebook_read_active_cell_output",
    "notebook_read_content",
    "notebook_move_cursor",
    "qcodes_instrument_info",
    "qcodes_get_parameter_info",
    "qcodes_get_parameter_values",
]

# Additional tools in unsafe mode
UNSAFE_MODE_TOOLS = SAFE_MODE_TOOLS + [
    "notebook_execute_active_cell",
    "notebook_add_cell",
    "notebook_delete_cell",
    "notebook_apply_patch",
]

# Optional MeasureIt tools
MEASUREIT_TOOLS = [
    "measureit_get_status",
    "measureit_wait_for_sweep",
    "measureit_kill_sweep",
]

# Optional Database tools
DATABASE_TOOLS = [
    "database_list_all_available_db",
    "database_list_experiments",
    "database_get_dataset_info",
    "database_get_database_stats",
]

# Optional Dynamic tools (requires dangerous mode)
DYNAMIC_TOOLS = [
    "dynamic_register_tool",
    "dynamic_update_tool",
    "dynamic_revoke_tool",
    "dynamic_list_tools",
    "dynamic_inspect_tool",
    "dynamic_registry_stats",
]

# Cleanup code to run before SweepQueue tests
MEASUREIT_CLEANUP = """
from qcodes.instrument import Instrument
Instrument.close_all()
for name in list(globals().keys()):
    if name.startswith(('s1', 's2', 's3', 'sweep_queue', 'instr')):
        del globals()[name]
print("Cleanup complete")
"""

# Setup code for MeasureIt SweepQueue testing with real Qt
# Note: Avoids try/except to prevent JupyterLab auto-indent issues when typing
# Uses unique instrument name based on timestamp to avoid conflicts
MEASUREIT_SWEEP_QUEUE_SETUP = """
import time
from qcodes.instrument_drivers.mock_instruments import MockParabola
from qcodes.instrument import Instrument
from measureit import Sweep1D
from measureit.tools import ensure_qt
from measureit.tools.sweep_queue import SweepQueue
ensure_qt()
Instrument.close_all()
instr = MockParabola(name=f"test_instr_{int(time.time())}")
s1 = Sweep1D(instr.x, 0, 5, 0.5, inter_delay=0.1, save_data=False)
s2 = Sweep1D(instr.x, 0, 5, 0.5, inter_delay=0.1, save_data=False)
s3 = Sweep1D(instr.x, 0, 5, 0.5, inter_delay=0.1, save_data=False)
sweep_queue = SweepQueue()
sweep_queue.append(s1, s2, s3)
print("SweepQueue setup complete")
print(f"s1.progressState.is_queued = {s1.progressState.is_queued}")
print(f"s2.progressState.is_queued = {s2.progressState.is_queued}")
print(f"s3.progressState.is_queued = {s3.progressState.is_queued}")
"""

# Code to start the sweep queue (run after MEASUREIT_SWEEP_QUEUE_SETUP)
MEASUREIT_START_QUEUE = """
sweep_queue.start()
print("SweepQueue started")
"""

# Code to check sweep queue state
MEASUREIT_CHECK_QUEUE_STATE = """
print(f"sweep_queue.state() = {sweep_queue.state()}")
print(f"sweep_queue.current_sweep = {sweep_queue.current_sweep}")
"""

# Setup code for MeasureIt SweepQueue with Sweep2D and save_data=True
# This tests a more realistic scenario with 2D sweeps that save data
MEASUREIT_SWEEP2D_QUEUE_SETUP = """
import time
from qcodes.instrument_drivers.mock_instruments import MockParabola
from qcodes.instrument import Instrument
from measureit import Sweep2D
from measureit.tools import ensure_qt
from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry
from measureit.config import get_path
ensure_qt()
Instrument.close_all()
instr = MockParabola(name=f"test_instr_{int(time.time())}")
# 3 Sweep2D with save_data=True - small sweeps for faster testing
# Sweep2D expects: in_params=[param, start, stop, step], out_params=[param, start, stop, step]
# outer: 3 points, inner: 3 points, total 9 points per sweep
s1 = Sweep2D([instr.x, 0, 2, 1], [instr.y, 0, 2, 1], inter_delay=0.05, save_data=True)
s2 = Sweep2D([instr.x, 0, 2, 1], [instr.y, 0, 2, 1], inter_delay=0.05, save_data=True)
s3 = Sweep2D([instr.x, 0, 2, 1], [instr.y, 0, 2, 1], inter_delay=0.05, save_data=True)
# Setup database entries for each sweep (save_data=True requires DatabaseEntry)
db_name = "e2e_test_sweep2d.db"
db_path = str(get_path("databases") / db_name)
exp_name = f"e2e_test_{int(time.time())}"
db_entry1 = DatabaseEntry(db_path, exp_name, "sweep2d_s1")
db_entry2 = DatabaseEntry(db_path, exp_name, "sweep2d_s2")
db_entry3 = DatabaseEntry(db_path, exp_name, "sweep2d_s3")
sweep_queue = SweepQueue()
# Each sweep needs its own database entry
sweep_queue += (db_entry1, s1)
sweep_queue += (db_entry2, s2)
sweep_queue += (db_entry3, s3)
print("Sweep2D SweepQueue setup complete")
print(f"s1.progressState.is_queued = {s1.progressState.is_queued}")
print(f"s2.progressState.is_queued = {s2.progressState.is_queued}")
print(f"s3.progressState.is_queued = {s3.progressState.is_queued}")
"""

# Code to start the sweep2D queue (run after MEASUREIT_SWEEP2D_QUEUE_SETUP)
MEASUREIT_START_SWEEP2D_QUEUE = """
sweep_queue.start()
print("Sweep2D SweepQueue started")
"""
