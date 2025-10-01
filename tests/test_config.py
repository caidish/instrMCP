"""
Unit tests for config module.

Tests InstrMCPConfig class for configuration loading, path resolution,
environment variable handling, and file operations.
"""

import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from instrmcp.config import (
    InstrMCPConfig,
    get_package_path,
    get_config,
    get_path,
    get_server_config,
    get_legacy_path,
    ensure_path_compatibility,
)


class TestInstrMCPConfig:
    """Test InstrMCPConfig class for configuration management."""

    def test_config_initialization(self):
        """Test config is initialized with proper path detection."""
        config = InstrMCPConfig()
        assert config._config is None
        assert isinstance(config._config_paths, dict)
        assert "package" in config._config_paths
        assert "user" in config._config_paths
        assert "cwd" in config._config_paths

    def test_get_package_path(self):
        """Test getting package installation path."""
        config = InstrMCPConfig()
        package_path = config.get_package_path()
        assert isinstance(package_path, Path)
        assert package_path.exists()

    def test_get_user_config_dir(self):
        """Test getting user configuration directory."""
        config = InstrMCPConfig()
        user_dir = config.get_user_config_dir()
        assert isinstance(user_dir, Path)
        assert user_dir == Path.home() / ".instrmcp"

    def test_config_paths_with_env_variable(self, monkeypatch):
        """Test config paths when environment variable is set."""
        test_path = "/custom/instrmcp/path"
        monkeypatch.setenv("instrMCP_PATH", test_path)

        config = InstrMCPConfig()
        assert "env" in config._config_paths
        assert config._config_paths["env"] == Path(test_path)

    def test_config_paths_without_env_variable(self, monkeypatch):
        """Test config paths when environment variable is not set."""
        monkeypatch.delenv("instrMCP_PATH", raising=False)

        config = InstrMCPConfig()
        assert "env" not in config._config_paths

    def test_get_default_config(self):
        """Test default configuration structure."""
        config = InstrMCPConfig()
        default_config = config._get_default_config()

        assert "version" in default_config
        assert "paths" in default_config
        assert "servers" in default_config
        assert "jupyter" in default_config
        assert "logging" in default_config

        # Check paths
        assert "package" in default_config["paths"]
        assert "data" in default_config["paths"]
        assert "templates" in default_config["paths"]
        assert "user_data" in default_config["paths"]

        # Check servers
        assert "jupyter_qcodes" in default_config["servers"]
        assert "qcodes" in default_config["servers"]

    def test_default_config_values(self):
        """Test default configuration values are sensible."""
        config = InstrMCPConfig()
        default_config = config._get_default_config()

        # Check jupyter_qcodes server defaults
        jupyter_server = default_config["servers"]["jupyter_qcodes"]
        assert jupyter_server["host"] == "127.0.0.1"
        assert isinstance(jupyter_server["port"], int)
        assert jupyter_server["safe_mode"] is True
        assert jupyter_server["auto_start"] is False

        # Check qcodes server defaults
        qcodes_server = default_config["servers"]["qcodes"]
        assert qcodes_server["host"] == "127.0.0.1"
        assert isinstance(qcodes_server["port"], int)

        # Check logging defaults
        logging_config = default_config["logging"]
        assert logging_config["level"] == "INFO"
        assert logging_config["file"] is None

    def test_load_config_creates_user_config(self, temp_dir, monkeypatch):
        """Test loading config creates user config file if it doesn't exist."""
        # Use temp directory as user config dir
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        loaded_config = config.load_config()

        assert loaded_config is not None
        user_config_file = config.get_user_config_dir() / "config.yaml"
        assert user_config_file.exists()

    def test_load_config_caching(self, temp_dir, monkeypatch):
        """Test config is cached after first load."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        config1 = config.load_config()
        config2 = config.load_config()

        # Should return same object
        assert config1 is config2

    def test_load_config_force_reload(self, temp_dir, monkeypatch):
        """Test force reload updates cached config."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        config1 = config.load_config()

        # Modify internal config
        config._config["test_key"] = "test_value"

        # Force reload should reset
        config2 = config.load_config(force_reload=True)
        assert "test_key" not in config2

    def test_load_config_from_file(self, temp_dir, monkeypatch):
        """Test loading config from existing file."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Create custom config file
        user_config_dir = temp_dir / ".instrmcp"
        user_config_dir.mkdir()
        config_file = user_config_dir / "config.yaml"

        custom_config = {
            "version": "0.3.0",
            "custom_key": "custom_value",
            "paths": {"package": str(temp_dir)},
            "servers": {},
            "jupyter": {},
            "logging": {},
        }

        with open(config_file, "w") as f:
            yaml.dump(custom_config, f)

        config = InstrMCPConfig()
        loaded_config = config.load_config()

        assert "custom_key" in loaded_config
        assert loaded_config["custom_key"] == "custom_value"

    def test_load_config_invalid_yaml(self, temp_dir, monkeypatch, caplog):
        """Test handling of invalid YAML in config file."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Create invalid config file
        user_config_dir = temp_dir / ".instrmcp"
        user_config_dir.mkdir()
        config_file = user_config_dir / "config.yaml"

        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [unclosed")

        config = InstrMCPConfig()
        loaded_config = config.load_config()

        # Should fall back to default config
        assert "version" in loaded_config
        assert "paths" in loaded_config

    def test_get_config_file_priority(self, temp_dir, monkeypatch):
        """Test config file priority: cwd > user > env > package."""
        # Setup: Create config files in multiple locations
        monkeypatch.setattr(Path, "home", lambda: temp_dir / "home")
        monkeypatch.setattr(Path, "cwd", lambda: temp_dir / "cwd")

        # Create user config
        user_dir = temp_dir / "home" / ".instrmcp"
        user_dir.mkdir(parents=True)
        (user_dir / "config.yaml").write_text("user_config: true")

        # Create cwd config
        cwd_dir = temp_dir / "cwd" / ".instrmcp"
        cwd_dir.mkdir(parents=True)
        (cwd_dir / "config.yaml").write_text("cwd_config: true")

        config = InstrMCPConfig()
        config_file = config.get_config_file()

        # Should prioritize cwd
        assert config_file == cwd_dir / "config.yaml"

    def test_get_config_file_returns_none_if_not_found(self, temp_dir, monkeypatch):
        """Test get_config_file returns None if no config exists."""
        # Use non-existent temp directory
        monkeypatch.setattr(Path, "home", lambda: temp_dir / "nonexistent")
        monkeypatch.setattr(Path, "cwd", lambda: temp_dir / "nonexistent")

        config = InstrMCPConfig()
        # Clear package path to ensure no config found
        config._config_paths = {
            "user": Path("/nonexistent"),
            "cwd": Path("/nonexistent"),
        }
        config_file = config.get_config_file()

        assert config_file is None

    def test_resolve_paths_relative_to_absolute(self, temp_dir, monkeypatch):
        """Test relative paths are converted to absolute."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        config._config = {
            "paths": {
                "data": "config/data",  # Relative path
                "templates": "/absolute/path",  # Already absolute
            }
        }

        config._resolve_paths()

        # Relative path should be made absolute
        assert os.path.isabs(config._config["paths"]["data"])
        # Absolute path should remain unchanged
        assert config._config["paths"]["templates"] == "/absolute/path"

    def test_resolve_paths_empty_config(self):
        """Test resolve paths handles empty config gracefully."""
        config = InstrMCPConfig()
        config._config = {}

        # Should not raise error
        config._resolve_paths()
        assert config._config == {}

    def test_create_user_config_creates_directories(self, temp_dir, monkeypatch):
        """Test _create_user_config creates necessary directories."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        config._create_user_config()

        user_dir = config.get_user_config_dir()
        assert user_dir.exists()
        assert (user_dir / "config.yaml").exists()
        assert (user_dir / "data").exists()

    def test_create_user_config_does_not_overwrite(self, temp_dir, monkeypatch):
        """Test _create_user_config does not overwrite existing config."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Create custom config
        user_dir = temp_dir / ".instrmcp"
        user_dir.mkdir()
        config_file = user_dir / "config.yaml"
        config_file.write_text("custom: config")

        config = InstrMCPConfig()
        config._create_user_config()

        # Should not overwrite
        content = config_file.read_text()
        assert "custom: config" in content

    def test_create_user_config_handles_write_error(
        self, temp_dir, monkeypatch, caplog
    ):
        """Test _create_user_config handles file write errors gracefully."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()

        # Mock open to raise permission error during file write
        # The directory creation should succeed, but file write should fail
        original_open = open

        def mock_open(*args, **kwargs):
            # Let directory creation work, but fail on config.yaml write
            if "config.yaml" in str(args[0]) and kwargs.get("mode") == "w":
                raise PermissionError("No permission to write file")
            return original_open(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open):
            # Should not raise, only log warning
            config._create_user_config()

        # Verify warning was logged (optional, requires proper logger setup)
        # For now, just ensure it doesn't crash

    def test_get_path_success(self, temp_dir, monkeypatch):
        """Test getting a configured path."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        config.load_config()

        # Should return valid path
        data_path = config.get_path("data")
        assert isinstance(data_path, Path)

    def test_get_path_nonexistent_key(self, temp_dir, monkeypatch):
        """Test getting non-existent path raises error."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        config.load_config()

        with pytest.raises(ValueError, match="Path 'nonexistent' not configured"):
            config.get_path("nonexistent")

    def test_get_server_config_jupyter_qcodes(self, temp_dir, monkeypatch):
        """Test getting jupyter_qcodes server configuration."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        server_config = config.get_server_config("jupyter_qcodes")

        assert "host" in server_config
        assert "port" in server_config
        assert "safe_mode" in server_config
        assert "auto_start" in server_config

    def test_get_server_config_qcodes(self, temp_dir, monkeypatch):
        """Test getting qcodes server configuration."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        server_config = config.get_server_config("qcodes")

        assert "host" in server_config
        assert "port" in server_config
        assert "station_config" in server_config

    def test_get_server_config_nonexistent(self, temp_dir, monkeypatch):
        """Test getting non-existent server returns empty dict."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        server_config = config.get_server_config("nonexistent_server")

        assert server_config == {}

    def test_get_jupyter_config(self, temp_dir, monkeypatch):
        """Test getting Jupyter configuration."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        jupyter_config = config.get_jupyter_config()

        assert "extension" in jupyter_config
        assert "magic_commands" in jupyter_config
        assert jupyter_config["extension"]["auto_load"] is True
        assert jupyter_config["magic_commands"]["auto_register"] is True


class TestConvenienceFunctions:
    """Test convenience functions for accessing configuration."""

    def test_get_package_path_function(self):
        """Test get_package_path convenience function."""
        path = get_package_path()
        assert isinstance(path, Path)
        assert path.exists()

    def test_get_config_function(self, temp_dir, monkeypatch):
        """Test get_config convenience function."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        cfg = get_config()
        assert isinstance(cfg, dict)
        assert "version" in cfg
        assert "paths" in cfg

    def test_get_path_function(self, temp_dir, monkeypatch):
        """Test get_path convenience function."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        path = get_path("data")
        assert isinstance(path, Path)

    def test_get_server_config_function(self, temp_dir, monkeypatch):
        """Test get_server_config convenience function."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        server_cfg = get_server_config("jupyter_qcodes")
        assert isinstance(server_cfg, dict)
        assert "host" in server_cfg
        assert "port" in server_cfg


class TestLegacyCompatibility:
    """Test backwards compatibility with legacy environment variables."""

    def test_get_legacy_path_with_env_set(self, monkeypatch):
        """Test getting legacy path when environment variable is set."""
        test_path = "/legacy/instrmcp/path"
        monkeypatch.setenv("instrMCP_PATH", test_path)

        legacy_path = get_legacy_path()
        assert legacy_path == test_path

    def test_get_legacy_path_without_env(self, monkeypatch):
        """Test getting legacy path when environment variable is not set."""
        monkeypatch.delenv("instrMCP_PATH", raising=False)

        legacy_path = get_legacy_path()
        assert legacy_path is None

    def test_ensure_path_compatibility_new_system(self, temp_dir, monkeypatch):
        """Test path compatibility uses new config system."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        monkeypatch.delenv("instrMCP_PATH", raising=False)

        path = ensure_path_compatibility()
        assert isinstance(path, str)
        assert len(path) > 0

    def test_ensure_path_compatibility_legacy_fallback(self, monkeypatch):
        """Test path compatibility falls back to legacy env variable."""
        test_path = "/legacy/path"
        monkeypatch.setenv("instrMCP_PATH", test_path)

        # Mock get_package_path to fail
        with patch("instrmcp.config.get_package_path", side_effect=Exception("Failed")):
            path = ensure_path_compatibility()
            assert path == test_path

    def test_ensure_path_compatibility_final_fallback(self, monkeypatch):
        """Test path compatibility falls back to current directory."""
        monkeypatch.delenv("instrMCP_PATH", raising=False)

        # Mock get_package_path to fail
        with patch("instrmcp.config.get_package_path", side_effect=Exception("Failed")):
            path = ensure_path_compatibility()
            assert path == str(Path.cwd())


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def test_full_config_lifecycle(self, temp_dir, monkeypatch):
        """Test complete configuration lifecycle from creation to usage."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Create new config
        config = InstrMCPConfig()

        # Load config (creates user config)
        loaded_config = config.load_config()
        assert loaded_config is not None

        # Verify user config file was created
        user_config_file = config.get_user_config_dir() / "config.yaml"
        assert user_config_file.exists()

        # Read it back
        with open(user_config_file, "r") as f:
            file_config = yaml.safe_load(f)

        assert file_config is not None
        assert "version" in file_config

    def test_config_modification_persistence(self, temp_dir, monkeypatch):
        """Test config modifications can be persisted."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Create and load config
        config1 = InstrMCPConfig()
        config1.load_config()

        # Modify user config file
        user_config_file = config1.get_user_config_dir() / "config.yaml"
        custom_config = config1._get_default_config()
        custom_config["custom_setting"] = "custom_value"

        with open(user_config_file, "w") as f:
            yaml.dump(custom_config, f)

        # Create new config instance and load
        config2 = InstrMCPConfig()
        loaded_config = config2.load_config()

        # Should have custom setting
        assert "custom_setting" in loaded_config
        assert loaded_config["custom_setting"] == "custom_value"

    def test_multiple_config_instances_share_files(self, temp_dir, monkeypatch):
        """Test multiple config instances can coexist."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config1 = InstrMCPConfig()
        config2 = InstrMCPConfig()

        cfg1 = config1.load_config()
        cfg2 = config2.load_config()

        # Both should load from same file location
        assert config1.get_user_config_dir() == config2.get_user_config_dir()

    def test_config_with_all_paths(self, temp_dir, monkeypatch):
        """Test config system with all path types present."""
        # Setup all config locations
        monkeypatch.setattr(Path, "home", lambda: temp_dir / "home")
        monkeypatch.setattr(Path, "cwd", lambda: temp_dir / "cwd")
        monkeypatch.setenv("instrMCP_PATH", str(temp_dir / "env"))

        # Create config files in each location
        for subdir in ["home/.instrmcp", "cwd/.instrmcp", "env"]:
            path = temp_dir / subdir
            path.mkdir(parents=True)
            config_file = path / "config.yaml"
            config_file.write_text(f"{subdir.split('/')[0]}_config: true")

        config = InstrMCPConfig()
        config_file = config.get_config_file()

        # Should prioritize cwd
        assert "cwd" in str(config_file)

    def test_config_path_resolution_integration(self, temp_dir, monkeypatch):
        """Test path resolution works end-to-end."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()
        loaded_config = config.load_config()

        # All paths should be absolute
        for key, path_str in loaded_config["paths"].items():
            assert os.path.isabs(path_str), f"Path {key} is not absolute: {path_str}"

    def test_config_server_defaults_are_complete(self, temp_dir, monkeypatch):
        """Test server configurations have all required fields."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        config = InstrMCPConfig()

        # Check jupyter_qcodes server
        jupyter_cfg = config.get_server_config("jupyter_qcodes")
        assert "host" in jupyter_cfg
        assert "port" in jupyter_cfg
        assert "safe_mode" in jupyter_cfg
        assert "auto_start" in jupyter_cfg

        # Check qcodes server
        qcodes_cfg = config.get_server_config("qcodes")
        assert "host" in qcodes_cfg
        assert "port" in qcodes_cfg
        assert "station_config" in qcodes_cfg
