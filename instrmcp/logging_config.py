"""Unified logging configuration for instrMCP.

This module provides centralized logging setup with:
- Rotating file handlers (prevents unbounded growth)
- Configurable debug mode via ~/.instrmcp/logging.yaml
- Logger hierarchy for different components
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Any, Dict, Optional

# Try to import yaml for config file support
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

# Directory structure
INSTRMCP_DIR = Path.home() / ".instrmcp"
LOG_DIR = INSTRMCP_DIR / "logs"
CONFIG_FILE = INSTRMCP_DIR / "logging.yaml"

# Default configuration
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "debug_enabled": False,
    "tool_logging": True,
    "max_file_size_mb": 10,
    "backup_count": 5,
}

# Log format
DEFAULT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# Module-level state
_logging_initialized = False
_config: Dict[str, Any] = {}


def load_config() -> Dict[str, Any]:
    """Load logging configuration from file or use defaults.

    Returns:
        Configuration dictionary with all settings.
    """
    config = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists() and YAML_AVAILABLE:
        try:
            with open(CONFIG_FILE) as f:
                user_config = yaml.safe_load(f) or {}
            # Merge user config with defaults
            for key, value in user_config.items():
                if key in config:
                    config[key] = value
        except Exception as e:
            # If config file is invalid, use defaults
            logging.getLogger("instrMCP").warning(
                f"Failed to load logging config from {CONFIG_FILE}: {e}"
            )

    return config


def setup_logging(force: bool = False) -> None:
    """Configure all instrMCP loggers with proper handlers.

    This sets up:
    - Main log file (mcp.log) with rotation
    - Debug log file (mcp_debug.log) when debug_enabled=True
    - Proper logger hierarchy under instrMCP.*

    Args:
        force: If True, reinitialize even if already set up.
    """
    global _logging_initialized, _config

    if _logging_initialized and not force:
        return

    # Ensure directories exist
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Load configuration
    _config = load_config()

    # Get or create root instrMCP logger
    root_logger = logging.getLogger("instrMCP")

    # Clear existing handlers to avoid duplicates on reinit
    root_logger.handlers.clear()

    # Set level based on config
    debug_enabled = _config.get("debug_enabled", False)
    log_level = _config.get("log_level", "INFO")

    if debug_enabled:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Main log file (rotating)
    max_bytes = _config.get("max_file_size_mb", 10) * 1024 * 1024
    backup_count = _config.get("backup_count", 5)

    main_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "mcp.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
    root_logger.addHandler(main_handler)

    # Debug log file (only when enabled)
    if debug_enabled:
        debug_handler = logging.FileHandler(LOG_DIR / "mcp_debug.log")
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        root_logger.addHandler(debug_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False

    _logging_initialized = True

    # Log that we've initialized
    root_logger.debug("instrMCP logging initialized")
    root_logger.debug(f"Config: {_config}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger under the instrMCP hierarchy.

    Args:
        name: Logger name (will be prefixed with 'instrMCP.')

    Returns:
        Logger instance.

    Example:
        >>> logger = get_logger("server")
        >>> # Returns logger named "instrMCP.server"
    """
    # Ensure logging is set up
    setup_logging()

    # Create hierarchical name
    if name.startswith("instrMCP."):
        full_name = name
    else:
        full_name = f"instrMCP.{name}"

    return logging.getLogger(full_name)


def get_config() -> Dict[str, Any]:
    """Get the current logging configuration.

    Returns:
        Copy of the configuration dictionary.
    """
    if not _logging_initialized:
        setup_logging()
    return _config.copy()


def is_tool_logging_enabled() -> bool:
    """Check if tool call logging is enabled.

    Returns:
        True if tool logging is enabled.
    """
    if not _logging_initialized:
        setup_logging()
    return _config.get("tool_logging", True)


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled.

    Returns:
        True if debug logging is enabled.
    """
    if not _logging_initialized:
        setup_logging()
    return _config.get("debug_enabled", False)
