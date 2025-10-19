"""QCoDeS Station initialization from YAML configuration."""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from qcodes import Station
from qcodes.instrument.base import Instrument

logger = logging.getLogger(__name__)


class StationManager:
    """Manages QCoDeS Station lifecycle and configuration."""

    def __init__(self, config_path: str = None, state_dir: str = None):
        """Initialize Station Manager.

        Args:
            config_path: Path to station YAML configuration file
            state_dir: Directory for state files (available_instr.json, etc.)
        """
        self.config_path = config_path or os.getenv(
            "STATION_YAML", "./config/station.yaml"
        )
        self.state_dir = Path(state_dir or os.getenv("STATE_DIR", "./state"))
        self.station: Optional[Station] = None

        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def initialize_station(self) -> Station:
        """Initialize QCoDeS Station from configuration using standard QCoDeS approach."""
        try:
            # Close existing station if any
            if self.station is not None:
                logger.warning("Station already exists, closing existing station")
                self.station.close_all_registered_instruments()

            # Check if config file exists
            config_path = Path(self.config_path)
            if not config_path.exists():
                logger.warning(
                    f"Station config not found: {config_path}, creating empty station"
                )
                self.station = Station()
            else:
                # Use standard QCoDeS Station initialization with config file
                logger.info(f"Loading station from {config_path}")
                self.station = Station(config_file=str(config_path))

            logger.info("Successfully initialized QCoDeS Station")
            return self.station

        except Exception as e:
            logger.error(f"Failed to initialize station: {e}")
            raise

    def get_available_instruments(self) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of available instruments from configuration."""
        instruments = {}

        if not self.station:
            return instruments

        # Get instruments from station config if available
        if hasattr(self.station, "config") and self.station.config:
            config_instruments = self.station.config.get("instruments", {})
            for name, instr_config in config_instruments.items():
                instruments[name] = {
                    "name": name,
                    "type": instr_config.get("type"),
                    "address": instr_config.get("address"),
                    "loaded": name in self.station.components,
                }

        # Also include any loaded instruments not in config
        for comp_name, component in self.station.components.items():
            if comp_name not in instruments:
                instruments[comp_name] = {
                    "name": comp_name,
                    "type": type(component).__name__,
                    "loaded": True,
                }

        return instruments

    def load_instrument(self, name: str) -> Optional[Instrument]:
        """Load a single instrument by name using QCoDeS standard approach.

        Args:
            name: Instrument name from configuration

        Returns:
            Loaded instrument instance or None if failed
        """
        if not self.station:
            raise RuntimeError("Station not initialized")

        if name in self.station.components:
            logger.info(f"Instrument '{name}' already loaded")
            return self.station.components[name]

        try:
            # Use QCoDeS standard load_instrument method
            instrument = self.station.load_instrument(name)
            logger.info(f"Successfully loaded instrument '{name}'")
            return instrument

        except Exception as e:
            logger.error(f"Failed to load instrument '{name}': {e}")
            return None

    def load_all_instruments(self) -> Dict[str, bool]:
        """Load all instruments defined in the station configuration.

        Returns:
            Dictionary mapping instrument names to load success status
        """
        if not self.station:
            raise RuntimeError("Station not initialized")

        # Get all instrument names from config
        if not hasattr(self.station, "config") or not self.station.config:
            logger.info("No station configuration found, no instruments to load")
            return {}

        instrument_names = list(self.station.config.get("instruments", {}).keys())

        if not instrument_names:
            logger.info("No instruments defined in configuration")
            return {}

        logger.info(f"Loading all instruments: {instrument_names}")

        results = {}
        for name in instrument_names:
            try:
                instrument = self.load_instrument(name)
                results[name] = instrument is not None
            except Exception as e:
                logger.error(f"Failed to load instrument '{name}': {e}")
                results[name] = False

        success_count = sum(results.values())
        logger.info(
            f"Load all complete: {success_count}/{len(instrument_names)} instruments loaded"
        )

        return results

    def autoload_instruments(
        self, instrument_names: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Autoload specified instruments.

        Args:
            instrument_names: List of instrument names to load, or None to use QMS_AUTOLOAD env var

        Returns:
            Dictionary mapping instrument names to load success status
        """
        if instrument_names is None:
            autoload_str = os.getenv("QMS_AUTOLOAD", "")
            instrument_names = [
                name.strip() for name in autoload_str.split(",") if name.strip()
            ]

        if not instrument_names:
            logger.info("No instruments to autoload")
            return {}

        logger.info(f"Autoloading instruments: {instrument_names}")

        results = {}
        for name in instrument_names:
            try:
                instrument = self.load_instrument(name)
                results[name] = instrument is not None
            except Exception as e:
                logger.error(f"Autoload failed for '{name}': {e}")
                results[name] = False

        success_count = sum(results.values())
        logger.info(
            f"Autoload complete: {success_count}/{len(instrument_names)} instruments loaded"
        )

        return results

    def close_instrument(self, name: str) -> bool:
        """Close a specific instrument and remove it from the station.

        Args:
            name: Instrument name to close

        Returns:
            True if successfully closed, False otherwise
        """
        if not self.station:
            raise RuntimeError("Station not initialized")

        if name not in self.station.components:
            logger.warning(f"Instrument '{name}' not found in station components")
            return False

        try:
            instrument = self.station.components[name]
            logger.info(f"Closing instrument '{name}'")

            # Close the instrument connection
            instrument.close()

            # Remove from station
            self.station.remove_component(name)

            logger.info(f"Successfully closed instrument '{name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to close instrument '{name}': {e}")
            return False

    def reconnect_instrument(self, name: str) -> Optional[Instrument]:
        """Reconnect an instrument (close and reload).

        Args:
            name: Instrument name to reconnect

        Returns:
            Reconnected instrument instance or None if failed
        """
        if not self.station:
            raise RuntimeError("Station not initialized")

        logger.info(f"Reconnecting instrument '{name}'")

        # Close the instrument if it's loaded
        if name in self.station.components:
            if not self.close_instrument(name):
                logger.error(f"Failed to close instrument '{name}' before reconnecting")
                return None

        # Reload the instrument
        try:
            instrument = self.load_instrument(name)
            if instrument:
                logger.info(f"Successfully reconnected instrument '{name}'")
            else:
                logger.error(f"Failed to reconnect instrument '{name}'")
            return instrument

        except Exception as e:
            logger.error(f"Failed to reconnect instrument '{name}': {e}")
            return None

    def generate_available_instruments_file(self) -> str:
        """Generate available_instr.json file and return path."""
        available_instr = self.get_available_instruments()

        output_path = self.state_dir / "available_instr.json"

        try:
            with open(output_path, "w") as f:
                json.dump(available_instr, f, indent=2, default=str)

            logger.info(f"Generated available instruments file: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to generate available instruments file: {e}")
            raise

    def get_station_snapshot(self, update: bool = False) -> Dict[str, Any]:
        """Get complete station snapshot.

        Args:
            update: Whether to update from hardware (slow)

        Returns:
            Station snapshot dictionary
        """
        if not self.station:
            raise RuntimeError("Station not initialized")

        try:
            logger.debug(f"Getting station snapshot (update={update})")
            snapshot = self.station.snapshot(update=update)
            logger.debug(
                f"Station snapshot contains {len(snapshot.get('instruments', {}))} instruments"
            )
            return snapshot

        except Exception as e:
            logger.error(f"Failed to get station snapshot: {e}")
            raise

    def get_instrument_snapshot(self, name: str, update: bool = True) -> Dict[str, Any]:
        """Get snapshot for a specific instrument.

        Args:
            name: Instrument name
            update: Whether to update from hardware (slow)

        Returns:
            Instrument snapshot dictionary
        """
        if not self.station:
            raise RuntimeError("Station not initialized")

        if name not in self.station.components:
            available = list(self.station.components.keys())
            raise ValueError(f"Instrument '{name}' not loaded. Available: {available}")

        try:
            instrument = self.station.components[name]
            logger.debug(f"Getting snapshot for instrument '{name}' (update={update})")
            snapshot = instrument.snapshot(update=update)
            return snapshot

        except Exception as e:
            logger.error(f"Failed to get snapshot for instrument '{name}': {e}")
            raise

    def close_station(self):
        """Close station and all instruments."""
        if self.station:
            logger.info("Closing station and all instruments")
            try:
                self.station.close_all_registered_instruments()
            except Exception as e:
                logger.error(f"Error closing instruments: {e}")
            finally:
                self.station = None


# Global station manager instance
station_manager = StationManager()
