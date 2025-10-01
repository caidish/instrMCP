"""
Configuration management for InstrMCP.

Handles automatic path detection, configuration file management,
and eliminates the need for manual environment variable setup.
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

try:
    import importlib.resources as pkg_resources
except ImportError:
    # Fallback for Python < 3.9
    import importlib_resources as pkg_resources

logger = logging.getLogger(__name__)


class InstrMCPConfig:
    """Configuration manager for InstrMCP."""

    def __init__(self):
        self._config: Optional[Dict[str, Any]] = None
        self._config_paths = self._get_config_paths()

    def _get_config_paths(self) -> Dict[str, Path]:
        """Get all possible configuration file paths."""
        paths = {}

        # 1. Package installation directory (for defaults)
        try:
            if hasattr(pkg_resources, "files"):
                # Python 3.9+
                package_path = pkg_resources.files("instrmcp")
            else:
                # Fallback for older Python
                import instrmcp

                package_path = Path(instrmcp.__file__).parent
            paths["package"] = Path(package_path)
        except Exception:
            # Fallback: use current working directory
            paths["package"] = Path(__file__).parent.parent

        # 2. User home directory
        paths["user"] = Path.home() / ".instrmcp"

        # 3. Current working directory
        paths["cwd"] = Path.cwd() / ".instrmcp"

        # 4. Environment variable override
        env_path = os.getenv("instrMCP_PATH")
        if env_path:
            paths["env"] = Path(env_path)

        return paths

    def get_package_path(self) -> Path:
        """Get the InstrMCP package installation path."""
        return self._config_paths["package"]

    def get_user_config_dir(self) -> Path:
        """Get the user configuration directory."""
        return self._config_paths["user"]

    def get_config_file(self) -> Optional[Path]:
        """Find and return the path to the active configuration file."""
        # Priority order: cwd > user > env > package
        search_order = ["cwd", "user", "env", "package"]

        for location in search_order:
            if location not in self._config_paths:
                continue

            config_path = self._config_paths[location] / "config.yaml"
            if config_path.exists():
                return config_path

        return None

    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if self._config is not None and not force_reload:
            return self._config

        config_file = self.get_config_file()

        if config_file and config_file.exists():
            try:
                with open(config_file, "r") as f:
                    self._config = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config from {config_file}: {e}")
                self._config = self._get_default_config()
        else:
            self._config = self._get_default_config()
            # Create user config file if it doesn't exist
            self._create_user_config()

        # Update paths to absolute paths
        self._resolve_paths()

        return self._config

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        package_path = self.get_package_path()

        return {
            "version": "0.3.0",
            "paths": {
                "package": str(package_path),
                "data": str(package_path / "config" / "data"),
                "templates": str(package_path / "config" / "templates"),
                "user_data": str(self.get_user_config_dir() / "data"),
            },
            "servers": {
                "jupyter_qcodes": {
                    "host": "127.0.0.1",
                    "port": 8123,
                    "safe_mode": True,
                    "auto_start": False,
                },
                "qcodes": {
                    "host": "127.0.0.1",
                    "port": 8000,
                    "station_config": None,  # Will be set to package default
                },
            },
            "jupyter": {
                "extension": {"auto_load": True, "comm_target": "mcp:active_cell"},
                "magic_commands": {"auto_register": True},
            },
            "logging": {"level": "INFO", "file": None},  # None = console only
        }

    def _resolve_paths(self):
        """Convert relative paths to absolute paths."""
        if "paths" not in self._config:
            return

        for key, path in self._config["paths"].items():
            if path and not os.path.isabs(path):
                # Make relative paths relative to package directory
                abs_path = self.get_package_path() / path
                self._config["paths"][key] = str(abs_path)

    def _create_user_config(self):
        """Create user configuration directory and file."""
        user_dir = self.get_user_config_dir()
        user_dir.mkdir(parents=True, exist_ok=True)

        user_config_file = user_dir / "config.yaml"
        if not user_config_file.exists():
            try:
                with open(user_config_file, "w") as f:
                    yaml.dump(
                        self._get_default_config(),
                        f,
                        default_flow_style=False,
                        indent=2,
                    )
                logger.info(f"Created user config at {user_config_file}")
            except Exception as e:
                logger.warning(f"Failed to create user config: {e}")

        # Create user data directory
        user_data_dir = user_dir / "data"
        user_data_dir.mkdir(exist_ok=True)

    def get_path(self, key: str) -> Path:
        """Get a configured path."""
        config = self.load_config()
        path_str = config.get("paths", {}).get(key)

        if not path_str:
            raise ValueError(f"Path '{key}' not configured")

        return Path(path_str)

    def get_server_config(self, server_name: str) -> Dict[str, Any]:
        """Get server configuration."""
        config = self.load_config()
        return config.get("servers", {}).get(server_name, {})

    def get_jupyter_config(self) -> Dict[str, Any]:
        """Get Jupyter configuration."""
        config = self.load_config()
        return config.get("jupyter", {})


# Global configuration instance
config = InstrMCPConfig()


# Convenience functions
def get_package_path() -> Path:
    """Get the InstrMCP package path."""
    return config.get_package_path()


def get_config() -> Dict[str, Any]:
    """Get the current configuration."""
    return config.load_config()


def get_path(key: str) -> Path:
    """Get a configured path."""
    return config.get_path(key)


def get_server_config(server_name: str) -> Dict[str, Any]:
    """Get server configuration."""
    return config.get_server_config(server_name)


# For backwards compatibility with environment variables
def get_legacy_path() -> Optional[str]:
    """Get path from legacy instrMCP_PATH environment variable."""
    return os.getenv("instrMCP_PATH")


def ensure_path_compatibility() -> str:
    """Ensure path compatibility with legacy code."""
    # Try new config system first
    try:
        return str(get_package_path())
    except Exception:
        # Fall back to environment variable
        legacy_path = get_legacy_path()
        if legacy_path:
            return legacy_path
        # Last resort: current directory
        return str(Path.cwd())
