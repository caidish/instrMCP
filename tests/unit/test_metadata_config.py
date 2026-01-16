"""
Unit tests for metadata_config.py module.

Tests Pydantic models, YAML loading, validation, and security features
for MCP tool/resource metadata configuration.
"""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from instrmcp.utils.metadata_config import (
    ArgOverride,
    ToolOverride,
    ResourceOverride,
    MetadataConfig,
    load_config,
    save_config,
    validate_config_against_server,
    generate_default_config_yaml,
    _get_tool_arg_names,
)


class TestArgOverride:
    """Test ArgOverride Pydantic model."""

    def test_empty_override(self):
        """Test creating empty arg override."""
        override = ArgOverride()
        assert override.description is None

    def test_with_description(self):
        """Test arg override with description."""
        override = ArgOverride(description="Test description")
        assert override.description == "Test description"


class TestToolOverride:
    """Test ToolOverride Pydantic model."""

    def test_empty_override(self):
        """Test creating empty tool override."""
        override = ToolOverride()
        assert override.title is None
        assert override.description is None
        assert override.arguments == {}

    def test_full_override(self):
        """Test tool override with all fields."""
        override = ToolOverride(
            title="Test Tool",
            description="Test description",
            arguments={
                "arg1": ArgOverride(description="Arg 1 desc"),
                "arg2": ArgOverride(description="Arg 2 desc"),
            },
        )
        assert override.title == "Test Tool"
        assert override.description == "Test description"
        assert len(override.arguments) == 2
        assert override.arguments["arg1"].description == "Arg 1 desc"


class TestResourceOverride:
    """Test ResourceOverride Pydantic model."""

    def test_empty_override(self):
        """Test creating empty resource override."""
        override = ResourceOverride()
        assert override.name is None
        assert override.description is None
        assert override.use_when is None
        assert override.example is None

    def test_compose_description_none(self):
        """Test compose_description with no description."""
        override = ResourceOverride()
        assert override.compose_description() is None

    def test_compose_description_simple(self):
        """Test compose_description with only description."""
        override = ResourceOverride(description="Main description")
        assert override.compose_description() == "Main description"

    def test_compose_description_with_use_when(self):
        """Test compose_description with use_when."""
        override = ResourceOverride(
            description="Main description",
            use_when="When you need X",
        )
        expected = "Main description\nWhen to use: When you need X"
        assert override.compose_description() == expected

    def test_compose_description_with_example(self):
        """Test compose_description with example."""
        override = ResourceOverride(
            description="Main description",
            example="Do this first",
        )
        expected = "Main description\nExample: Do this first"
        assert override.compose_description() == expected

    def test_compose_description_full(self):
        """Test compose_description with all fields."""
        override = ResourceOverride(
            description="Main description",
            use_when="When you need X",
            example="Do this first",
        )
        expected = (
            "Main description\n"
            "When to use: When you need X\n"
            "Example: Do this first"
        )
        assert override.compose_description() == expected


class TestMetadataConfig:
    """Test MetadataConfig Pydantic model."""

    def test_default_config(self):
        """Test default config values."""
        config = MetadataConfig()
        assert config.version == 1
        assert config.strict is True
        assert config.tools == {}
        assert config.resources == {}
        assert config.resource_templates == {}

    def test_config_with_tools(self):
        """Test config with tool overrides."""
        config = MetadataConfig(
            tools={
                "test_tool": ToolOverride(title="Test", description="Desc"),
            }
        )
        assert len(config.tools) == 1
        assert config.tools["test_tool"].title == "Test"

    def test_config_non_strict(self):
        """Test non-strict mode."""
        config = MetadataConfig(strict=False)
        assert config.strict is False


class TestLoadConfig:
    """Test load_config function."""

    def test_load_missing_file(self):
        """Test loading non-existent user file returns baseline config."""
        config = load_config(Path("/nonexistent/path/config.yaml"))
        assert config.version == 1
        # With baseline loading, we should have tools from metadata_baseline.yaml
        # The exact count may vary, but should be > 0
        assert len(config.tools) > 0  # Baseline has tools

    def test_load_empty_file(self):
        """Test loading empty user file returns baseline config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            assert config.version == 1
            # With baseline loading, we should have tools from metadata_baseline.yaml
            assert len(config.tools) > 0  # Baseline has tools
        finally:
            temp_path.unlink()

    def test_load_valid_config(self):
        """Test loading valid YAML config."""
        yaml_content = """
version: 1
strict: false
tools:
  test_tool:
    title: "Test Tool"
    description: "Test description"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            assert config.version == 1
            assert config.strict is False
            assert "test_tool" in config.tools
            assert config.tools["test_tool"].title == "Test Tool"
        finally:
            temp_path.unlink()

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML raises error."""
        yaml_content = "invalid: [unclosed"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                load_config(temp_path)
        finally:
            temp_path.unlink()

    def test_load_invalid_structure(self):
        """Test loading YAML with invalid structure raises error."""
        yaml_content = """
version: "not_an_int"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid user config"):
                load_config(temp_path)
        finally:
            temp_path.unlink()


class TestSaveConfig:
    """Test save_config function."""

    def test_save_creates_file(self):
        """Test save_config creates file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test" / "config.yaml"
            config = MetadataConfig(tools={"test": ToolOverride(title="Test")})

            save_config(config, config_path)

            assert config_path.exists()

    def test_save_sets_permissions(self):
        """Test save_config sets restrictive file permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config = MetadataConfig()

            save_config(config, config_path)

            # Check permissions are 0o600 (user read/write only)
            file_mode = stat.S_IMODE(os.stat(config_path).st_mode)
            assert file_mode == 0o600

    def test_save_round_trip(self):
        """Test config can be saved and loaded back."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            original = MetadataConfig(
                version=1,
                strict=False,
                tools={
                    "tool1": ToolOverride(
                        title="Tool 1",
                        arguments={"arg1": ArgOverride(description="Arg desc")},
                    )
                },
                resources={
                    "resource://test": ResourceOverride(
                        name="Test Resource",
                        description="Test desc",
                        use_when="When testing",
                    )
                },
            )

            save_config(original, config_path)
            loaded = load_config(config_path)

            assert loaded.version == original.version
            assert loaded.strict == original.strict
            assert "tool1" in loaded.tools
            assert loaded.tools["tool1"].title == "Tool 1"
            assert "resource://test" in loaded.resources


class TestValidateConfigAgainstServer:
    """Test validate_config_against_server function."""

    def test_valid_config(self):
        """Test validation passes for valid config."""
        config = MetadataConfig(
            tools={"known_tool": ToolOverride(title="Test")},
            resources={"resource://known": ResourceOverride(name="Known")},
        )
        registered_tools = {"known_tool": {"name": "known_tool"}}
        registered_resources = {"resource://known": {"name": "known"}}

        errors = validate_config_against_server(
            config, registered_tools, registered_resources
        )

        assert len(errors) == 0

    def test_unknown_tool_strict(self):
        """Test unknown tool raises error in strict mode."""
        config = MetadataConfig(
            strict=True,
            tools={"unknown_tool": ToolOverride(title="Test")},
        )

        errors = validate_config_against_server(config, {}, {})

        assert len(errors) == 1
        assert "ERROR" in errors[0]
        assert "unknown_tool" in errors[0]

    def test_unknown_tool_non_strict(self):
        """Test unknown tool logs warning in non-strict mode."""
        config = MetadataConfig(
            strict=False,
            tools={"unknown_tool": ToolOverride(title="Test")},
        )

        errors = validate_config_against_server(config, {}, {})

        assert len(errors) == 1
        assert "WARNING" in errors[0]
        assert "skipped" in errors[0]

    def test_unknown_resource_strict(self):
        """Test unknown resource raises error in strict mode."""
        config = MetadataConfig(
            strict=True,
            resources={"resource://unknown": ResourceOverride(name="Test")},
        )

        errors = validate_config_against_server(config, {}, {})

        assert len(errors) == 1
        assert "ERROR" in errors[0]
        assert "resource://unknown" in errors[0]


class TestGetToolArgNames:
    """Test _get_tool_arg_names helper function."""

    def test_dict_tool_info(self):
        """Test extracting args from dict tool info."""
        tool_info = {
            "inputSchema": {
                "properties": {
                    "arg1": {"description": "Arg 1"},
                    "arg2": {"description": "Arg 2"},
                }
            }
        }

        arg_names = _get_tool_arg_names(tool_info)

        assert arg_names == {"arg1", "arg2"}

    def test_empty_tool_info(self):
        """Test extracting args from empty tool info."""
        arg_names = _get_tool_arg_names({})
        assert arg_names == set()


class TestGenerateDefaultConfigYaml:
    """Test generate_default_config_yaml function."""

    def test_generates_valid_yaml(self):
        """Test generated YAML is valid and loadable."""
        import yaml

        yaml_str = generate_default_config_yaml()
        # Should not raise
        parsed = yaml.safe_load(yaml_str)
        # Parsed should be a dict (or None for all-comments)
        assert parsed is None or isinstance(parsed, dict)

    def test_contains_version(self):
        """Test generated YAML contains version field."""
        yaml_str = generate_default_config_yaml()
        assert "version:" in yaml_str

    def test_contains_examples(self):
        """Test generated YAML contains commented examples."""
        yaml_str = generate_default_config_yaml()
        assert "# tools:" in yaml_str or "tools:" in yaml_str
        assert "qcodes_instrument_info" in yaml_str


class TestYamlSecurity:
    """Test YAML security features."""

    def test_safe_load_blocks_python_object(self):
        """Test that dangerous YAML tags are blocked."""
        # This YAML would execute code if not using safe_load
        dangerous_yaml = """
!!python/object/apply:os.system
- echo "pwned"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(dangerous_yaml)
            temp_path = Path(f.name)

        try:
            # Should raise ValueError (from YAML parsing) not execute code
            with pytest.raises(ValueError):
                load_config(temp_path)
        finally:
            temp_path.unlink()
