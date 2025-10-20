"""
Pytest configuration and shared fixtures for InstrMCP tests.

This module provides common fixtures used across all tests, including
mock QCodes instruments, mock IPython kernels, and temporary directories.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mock_ipython_namespace():
    """Create a mock IPython user namespace with common test variables."""
    return {
        "test_var": 42,
        "test_array": [1, 2, 3, 4, 5],
        "test_dict": {"key1": "value1", "key2": "value2"},
        "test_string": "Hello, InstrMCP!",
    }


@pytest.fixture
def mock_ipython(mock_ipython_namespace):
    """Create a mock IPython instance for testing."""
    ipython = MagicMock()
    ipython.user_ns = mock_ipython_namespace
    ipython.events = MagicMock()
    ipython.events.register = MagicMock()

    # Mock execution info for cell capture
    ipython.execution_count = 1

    return ipython


@pytest.fixture
def mock_qcodes_instrument():
    """Create a mock QCodes instrument for testing."""
    from unittest.mock import MagicMock

    instrument = MagicMock()
    instrument.name = "mock_instrument"
    instrument.parameters = {}

    # Mock parameter
    param = MagicMock()
    param.name = "test_parameter"
    param.get = MagicMock(return_value=3.14)
    param.set = MagicMock()
    param.unit = "V"
    param.get_latest = MagicMock(return_value=3.14)

    instrument.parameters["test_parameter"] = param
    instrument.test_parameter = param

    return instrument


@pytest.fixture
def mock_qcodes_station(mock_qcodes_instrument):
    """Create a mock QCodes station for testing."""
    station = MagicMock()
    station.components = {"mock_instrument": mock_qcodes_instrument}
    station.snapshot = MagicMock(
        return_value={
            "instruments": {
                "mock_instrument": {
                    "parameters": {"test_parameter": {"value": 3.14, "unit": "V"}}
                }
            }
        }
    )
    return station


@pytest.fixture
def sample_cell_content():
    """Sample Jupyter notebook cell content for testing."""
    return """# Test cell
import numpy as np
data = np.array([1, 2, 3, 4, 5])
print(f"Data mean: {data.mean()}")
"""


@pytest.fixture
def sample_notebook_cells():
    """Sample notebook cells with metadata."""
    return [
        {
            "cell_type": "code",
            "execution_count": 1,
            "source": "import qcodes as qc\nimport numpy as np",
            "outputs": [],
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "source": "# Initialize mock DAC\nmock_dac = qc.instrument.MockDAC('mock_dac')",
            "outputs": [{"output_type": "stream", "text": "Connected to: MockDAC"}],
        },
        {
            "cell_type": "markdown",
            "source": "## Test Section\nThis is a test markdown cell.",
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "source": "# Read voltage\nvoltage = mock_dac.ch01.voltage()\nprint(f'Voltage: {voltage} V')",
            "outputs": [{"output_type": "stream", "text": "Voltage: 0.0 V"}],
        },
    ]


@pytest.fixture
def mock_database_path(temp_dir):
    """Create a mock database path for testing."""
    db_path = temp_dir / "test_database.db"
    # Create the actual file so path resolution doesn't fail
    db_path.touch()
    return str(db_path)


@pytest.fixture
def mock_qcodes_db_config(temp_dir, monkeypatch):
    """Configure QCodes to use a test database that exists."""
    db_path = temp_dir / "qcodes_test.db"
    db_path.touch()

    # Use monkeypatch to set qc.config.core.db_location
    import instrmcp.extensions.database.query_tools as query_tools

    if hasattr(query_tools, "qc") and hasattr(query_tools.qc, "config"):
        monkeypatch.setattr(query_tools.qc.config.core, "db_location", str(db_path))

    yield str(db_path)


@pytest.fixture
def sample_experiment_data():
    """Sample experiment data for database testing."""
    return {
        "exp_id": 1,
        "name": "test_experiment",
        "sample_name": "test_sample",
        "start_time": 1234567890,
        "format_string": "{}-{}-{}",
    }


@pytest.fixture
def sample_dataset_data():
    """Sample dataset data for database testing."""
    return {
        "run_id": 1,
        "counter": 1,
        "name": "test_measurement",
        "exp_id": 1,
        "run_timestamp": "2024-01-01 12:00:00",
        "completed_timestamp": "2024-01-01 12:05:00",
        "metadata": {"temperature": 300, "gate_voltage": 0.5},
    }


@pytest.fixture
def mock_measureit_sweep():
    """Mock MeasureIt sweep for testing."""
    sweep = MagicMock()
    sweep.is_running = MagicMock(return_value=False)
    sweep.status = "idle"
    sweep.config = {
        "sweep_type": "1D",
        "parameter": "gate_voltage",
        "start": 0,
        "stop": 1,
        "num_points": 100,
    }
    return sweep


# Pytest markers (registered in pyproject.toml but documented here)
# - @pytest.mark.slow: Tests that take more than 1 second
# - @pytest.mark.integration: Integration tests requiring multiple components
# - @pytest.mark.hardware: Tests requiring physical hardware (skipped by default)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "hardware: marks tests that require hardware")
