"""Pytest configuration for InstrMCP tests."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock

@pytest.fixture
def mock_qcodes():
    """Mock QCodes modules to avoid import dependencies in tests."""
    with pytest.MonkeyPatch.context() as m:
        # Mock qcodes station
        mock_station = Mock()
        m.setattr("qcodes.Station", lambda: mock_station)
        
        # Mock common instrument drivers
        mock_dac = Mock()
        mock_gate = Mock()
        
        m.setattr("qcodes.instrument_drivers.mock.MockDAC", mock_dac)
        m.setattr("qcodes.instrument_drivers.mock.MockGate", mock_gate)
        
        yield {
            "station": mock_station,
            "mock_dac": mock_dac,
            "mock_gate": mock_gate
        }

@pytest.fixture
def sample_station_config():
    """Sample station configuration for testing."""
    return {
        "instruments": {
            "mock_dac": {
                "driver": "qcodes.instrument_drivers.mock.MockDAC",
                "name": "mock_dac_1", 
                "enable": True,
                "parameters": {
                    "voltage_limit": 10.0
                }
            },
            "mock_gate": {
                "driver": "qcodes.instrument_drivers.mock.MockGate",
                "name": "mock_gate_1",
                "enable": True
            },
            "disabled_instrument": {
                "driver": "qcodes.instrument_drivers.mock.MockSource",
                "name": "disabled_source",
                "enable": False
            }
        },
        "station_config": {
            "default_timeout": 10.0,
            "snapshot_base": True
        }
    }

@pytest.fixture
def temp_config_files(sample_station_config):
    """Create temporary configuration files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir) / "config"
        state_dir = Path(temp_dir) / "state" 
        
        config_dir.mkdir()
        state_dir.mkdir()
        
        # Write station config
        station_file = config_dir / "station.station.yaml"
        with open(station_file, 'w') as f:
            yaml.dump(sample_station_config, f)
        
        # Write env file
        env_file = Path(temp_dir) / ".env"
        with open(env_file, 'w') as f:
            f.write(f"STATION_YAML={station_file}\n")
            f.write(f"STATE_DIR={state_dir}\n")
            f.write("QMS_AUTOLOAD=mock_dac,mock_gate\n")
        
        yield {
            "temp_dir": temp_dir,
            "config_dir": config_dir,
            "state_dir": state_dir,
            "station_file": station_file,
            "env_file": env_file
        }

@pytest.fixture
def mock_instrument():
    """Mock QCodes instrument for testing."""
    instrument = Mock()
    instrument.name = "test_instrument"
    instrument.parameters = {
        "voltage": Mock(),
        "current": Mock()
    }
    
    # Mock snapshot method
    instrument.snapshot.return_value = {
        "name": "test_instrument",
        "parameters": {
            "voltage": {"value": 1.0, "unit": "V"},
            "current": {"value": 0.001, "unit": "A"}
        },
        "__timestamp": "2023-01-01T00:00:00"
    }
    
    return instrument

@pytest.fixture
def mock_mcp_server():
    """Mock FastMCP server for testing."""
    from unittest.mock import AsyncMock
    
    server = Mock()
    server.run = AsyncMock()
    server.tool = Mock()
    server.resource = Mock()
    
    return server

@pytest.mark.asyncio
@pytest.fixture
async def running_server(mock_mcp_server, temp_config_files):
    """Fixture for running server instance in tests."""
    from servers.qcodes.server import QCodesStationServer
    
    config = temp_config_files
    
    # Create server with test configuration
    server = QCodesStationServer(host="localhost", port=8001)
    
    # Override station manager config paths
    server.station_manager.config_path = str(config["station_file"])
    server.station_manager.state_dir = config["state_dir"]
    
    yield server
    
    # Cleanup
    await server.cleanup()