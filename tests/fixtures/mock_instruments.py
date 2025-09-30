"""
Mock QCodes instruments for testing.

Provides mock implementations of common QCodes instruments without
requiring actual hardware or the full QCodes infrastructure.
"""

from unittest.mock import MagicMock
from typing import Dict, Any, Optional


class MockParameter:
    """Mock QCodes parameter for testing."""

    def __init__(self, name: str, initial_value: Any = 0.0, unit: str = ""):
        self.name = name
        self._value = initial_value
        self.unit = unit
        self.label = name
        self.vals = MagicMock()

    def get(self) -> Any:
        """Get parameter value."""
        return self._value

    def set(self, value: Any) -> None:
        """Set parameter value."""
        self._value = value

    def get_latest(self) -> Any:
        """Get latest cached value."""
        return self._value

    def __call__(self, value: Optional[Any] = None) -> Any:
        """Get or set parameter value."""
        if value is not None:
            self.set(value)
        return self.get()

    def snapshot(self, update: bool = False) -> Dict[str, Any]:
        """Return parameter snapshot."""
        return {
            "name": self.name,
            "value": self._value,
            "unit": self.unit,
            "label": self.label
        }


class MockChannel:
    """Mock QCodes channel/submodule for testing."""

    def __init__(self, name: str, parent: str):
        self.name = name
        self.parent = parent
        self.parameters = {}
        self._create_parameters()

    def _create_parameters(self):
        """Create default parameters for this channel."""
        self.voltage = MockParameter(f"{self.name}.voltage", 0.0, "V")
        self.current = MockParameter(f"{self.name}.current", 0.0, "A")
        self.parameters["voltage"] = self.voltage
        self.parameters["current"] = self.current

    def snapshot(self, update: bool = False) -> Dict[str, Any]:
        """Return channel snapshot."""
        return {
            "name": self.name,
            "parameters": {
                name: param.snapshot(update)
                for name, param in self.parameters.items()
            }
        }


class MockDAC:
    """Mock Digital-to-Analog Converter for testing."""

    def __init__(self, name: str, num_channels: int = 8):
        self.name = name
        self.parameters = {}
        self.submodules = {}

        # Create channels
        for i in range(1, num_channels + 1):
            channel_name = f"ch{i:02d}"
            channel = MockChannel(channel_name, self.name)
            setattr(self, channel_name, channel)
            self.submodules[channel_name] = channel

        # Create global parameters
        self.idn = MockParameter("idn", {"vendor": "Mock", "model": "DAC", "serial": "12345"})
        self.parameters["idn"] = self.idn

    def get_idn(self) -> Dict[str, str]:
        """Get instrument identification."""
        return self.idn.get()

    def snapshot(self, update: bool = False) -> Dict[str, Any]:
        """Return instrument snapshot."""
        return {
            "name": self.name,
            "parameters": {
                name: param.snapshot(update)
                for name, param in self.parameters.items()
            },
            "submodules": {
                name: submod.snapshot(update)
                for name, submod in self.submodules.items()
            }
        }

    def close(self):
        """Close instrument connection (no-op for mock)."""
        pass


class MockDMM:
    """Mock Digital Multimeter for testing."""

    def __init__(self, name: str):
        self.name = name
        self.parameters = {}

        # Create parameters
        self.voltage = MockParameter("voltage", 0.0, "V")
        self.current = MockParameter("current", 0.0, "A")
        self.resistance = MockParameter("resistance", 1000.0, "Ohm")
        self.idn = MockParameter("idn", {"vendor": "Mock", "model": "DMM", "serial": "67890"})

        self.parameters = {
            "voltage": self.voltage,
            "current": self.current,
            "resistance": self.resistance,
            "idn": self.idn
        }

    def get_idn(self) -> Dict[str, str]:
        """Get instrument identification."""
        return self.idn.get()

    def snapshot(self, update: bool = False) -> Dict[str, Any]:
        """Return instrument snapshot."""
        return {
            "name": self.name,
            "parameters": {
                name: param.snapshot(update)
                for name, param in self.parameters.items()
            }
        }

    def close(self):
        """Close instrument connection (no-op for mock)."""
        pass


class MockVNA:
    """Mock Vector Network Analyzer for testing."""

    def __init__(self, name: str):
        self.name = name
        self.parameters = {}

        # Create parameters
        self.frequency = MockParameter("frequency", 1e9, "Hz")
        self.power = MockParameter("power", -10, "dBm")
        self.s11_magnitude = MockParameter("s11_magnitude", 0.5, "")
        self.s11_phase = MockParameter("s11_phase", 45, "deg")
        self.idn = MockParameter("idn", {"vendor": "Mock", "model": "VNA", "serial": "11111"})

        self.parameters = {
            "frequency": self.frequency,
            "power": self.power,
            "s11_magnitude": self.s11_magnitude,
            "s11_phase": self.s11_phase,
            "idn": self.idn
        }

    def get_idn(self) -> Dict[str, str]:
        """Get instrument identification."""
        return self.idn.get()

    def snapshot(self, update: bool = False) -> Dict[str, Any]:
        """Return instrument snapshot."""
        return {
            "name": self.name,
            "parameters": {
                name: param.snapshot(update)
                for name, param in self.parameters.items()
            }
        }

    def close(self):
        """Close instrument connection (no-op for mock)."""
        pass


def create_mock_station() -> Dict[str, Any]:
    """Create a complete mock QCodes station with multiple instruments."""
    return {
        "mock_dac": MockDAC("mock_dac", num_channels=4),
        "mock_dmm": MockDMM("mock_dmm"),
        "mock_vna": MockVNA("mock_vna")
    }
