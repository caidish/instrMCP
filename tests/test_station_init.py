"""Tests for QCodes Station initialization."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from servers.qcodes.station_init import StationManager


class TestStationManager:
    """Test StationManager functionality."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory with test configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create test station config
            station_config = {
                "instruments": {
                    "mock_dac": {
                        "driver": "qcodes.instrument_drivers.mock.MockDAC",
                        "name": "mock_dac_1",
                        "enable": True
                    },
                    "test_instrument": {
                        "driver": "qcodes.instrument_drivers.mock.MockGate", 
                        "name": "test_gate",
                        "enable": False
                    }
                },
                "station_config": {
                    "default_timeout": 10.0
                }
            }
            
            config_file = config_dir / "station.station.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(station_config, f)
            
            yield str(config_file), temp_dir
    
    @pytest.fixture
    def manager(self, temp_config_dir):
        """Create StationManager with test configuration."""
        config_file, temp_dir = temp_config_dir
        return StationManager(config_path=config_file, state_dir=temp_dir + "/state")
    
    def test_load_station_config(self, manager):
        """Test loading station configuration from YAML."""
        config = manager.load_station_config()
        
        assert "instruments" in config
        assert "mock_dac" in config["instruments"]
        assert config["instruments"]["mock_dac"]["enable"] is True
        assert config["instruments"]["test_instrument"]["enable"] is False
    
    def test_get_available_instruments(self, manager):
        """Test getting available instruments from configuration."""
        manager.load_station_config()
        available = manager.get_available_instruments()
        
        assert "mock_dac" in available
        assert "test_instrument" in available
        assert available["mock_dac"]["enabled"] is True
        assert available["test_instrument"]["enabled"] is False
        assert available["mock_dac"]["loaded"] is False  # Not loaded yet
    
    @patch('servers.qcodes.station_init.Station')
    def test_initialize_station(self, mock_station_class, manager):
        """Test station initialization."""
        mock_station = Mock()
        mock_station_class.return_value = mock_station
        
        manager.load_station_config()
        station = manager.initialize_station()
        
        assert station is mock_station
        assert manager.station is mock_station
        mock_station_class.assert_called_once()
    
    @patch('servers.qcodes.station_init.Station')
    @patch('builtins.__import__')
    def test_load_instrument_success(self, mock_import, mock_station_class, manager):
        """Test successful instrument loading."""
        # Setup mocks
        mock_station = Mock()
        mock_station.components = {}
        mock_station_class.return_value = mock_station
        
        mock_driver_class = Mock()
        mock_instrument = Mock()
        mock_driver_class.return_value = mock_instrument
        
        mock_module = Mock()
        mock_module.MockDAC = mock_driver_class
        mock_import.return_value = mock_module
        
        # Initialize manager and station
        manager.load_station_config()
        manager.initialize_station()
        
        # Load instrument
        result = manager.load_instrument("mock_dac")
        
        assert result is mock_instrument
        mock_driver_class.assert_called_once_with(name="mock_dac_1")
        mock_station.add_component.assert_called_once_with(mock_instrument)
    
    @patch('servers.qcodes.station_init.Station')
    def test_load_disabled_instrument(self, mock_station_class, manager):
        """Test loading disabled instrument returns None."""
        mock_station = Mock()
        mock_station.components = {}
        mock_station_class.return_value = mock_station
        
        manager.load_station_config()
        manager.initialize_station()
        
        result = manager.load_instrument("test_instrument")  # This is disabled
        
        assert result is None
    
    def test_load_nonexistent_instrument(self, manager):
        """Test loading non-existent instrument raises ValueError."""
        manager.load_station_config()
        
        with pytest.raises(ValueError, match="not found in configuration"):
            manager.load_instrument("nonexistent")
    
    @patch('servers.qcodes.station_init.Station')
    def test_autoload_instruments(self, mock_station_class, manager):
        """Test autoloading instruments."""
        mock_station = Mock()
        mock_station.components = {}
        mock_station_class.return_value = mock_station
        
        with patch.object(manager, 'load_instrument') as mock_load:
            mock_load.side_effect = lambda name: Mock() if name == "mock_dac" else None
            
            manager.load_station_config()
            manager.initialize_station()
            
            results = manager.autoload_instruments(["mock_dac", "test_instrument"])
            
            assert results["mock_dac"] is True
            assert results["test_instrument"] is False
            assert mock_load.call_count == 2
    
    @patch('servers.qcodes.station_init.Station')
    def test_get_station_snapshot(self, mock_station_class, manager):
        """Test getting station snapshot."""
        mock_station = Mock()
        mock_snapshot = {"instruments": {}, "__timestamp": "2023-01-01"}
        mock_station.snapshot.return_value = mock_snapshot
        mock_station_class.return_value = mock_station
        
        manager.load_station_config()
        manager.initialize_station()
        
        snapshot = manager.get_station_snapshot(update=False)
        
        assert snapshot == mock_snapshot
        mock_station.snapshot.assert_called_once_with(update=False)
    
    def test_get_station_snapshot_no_station(self, manager):
        """Test getting snapshot without initialized station raises error."""
        with pytest.raises(RuntimeError, match="Station not initialized"):
            manager.get_station_snapshot()
    
    @patch('servers.qcodes.station_init.Station')
    def test_get_instrument_snapshot(self, mock_station_class, manager):
        """Test getting instrument snapshot."""
        mock_instrument = Mock()
        mock_snapshot = {"parameters": {}, "__timestamp": "2023-01-01"}
        mock_instrument.snapshot.return_value = mock_snapshot
        
        mock_station = Mock()
        mock_station.components = {"test_instr": mock_instrument}
        mock_station_class.return_value = mock_station
        
        manager.load_station_config()
        manager.initialize_station()
        
        snapshot = manager.get_instrument_snapshot("test_instr", update=True)
        
        assert snapshot == mock_snapshot
        mock_instrument.snapshot.assert_called_once_with(update=True)
    
    @patch('servers.qcodes.station_init.Station')
    def test_get_instrument_snapshot_not_loaded(self, mock_station_class, manager):
        """Test getting snapshot for non-loaded instrument raises error."""
        mock_station = Mock()
        mock_station.components = {}
        mock_station_class.return_value = mock_station
        
        manager.load_station_config()
        manager.initialize_station()
        
        with pytest.raises(ValueError, match="not loaded"):
            manager.get_instrument_snapshot("nonexistent")
    
    @patch('servers.qcodes.station_init.Station')
    @patch('builtins.open')
    @patch('json.dump')
    def test_generate_available_instruments_file(self, mock_json_dump, mock_open, mock_station_class, manager):
        """Test generating available instruments JSON file."""
        mock_station = Mock()
        mock_station.components = {"mock_dac": Mock()}
        mock_station_class.return_value = mock_station
        
        manager.load_station_config()
        manager.initialize_station()
        
        result_path = manager.generate_available_instruments_file()
        
        assert "available_instr.json" in result_path
        mock_open.assert_called_once()
        mock_json_dump.assert_called_once()
    
    @patch('servers.qcodes.station_init.Station')
    def test_close_station(self, mock_station_class, manager):
        """Test closing station."""
        mock_station = Mock()
        mock_station_class.return_value = mock_station
        
        manager.load_station_config()
        manager.initialize_station()
        
        manager.close_station()
        
        mock_station.close_all_registered_instruments.assert_called_once()
        assert manager.station is None