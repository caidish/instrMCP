"""Unit tests for dynamic tool creation system."""

import json
import pytest
from pathlib import Path
import tempfile
import shutil

from instrmcp.servers.jupyter_qcodes.options.dynamic_tool.spec import (
    ToolSpec,
    ToolParameter,
    validate_tool_spec,
    create_tool_spec,
    ValidationError,
)
from instrmcp.servers.jupyter_qcodes.options.dynamic_tool.registry import (
    ToolRegistry,
    RegistryError,
)
from instrmcp.servers.jupyter_qcodes.security.audit import AuditLogger


class TestToolParameter:
    """Tests for ToolParameter dataclass."""

    def test_create_parameter(self):
        """Test creating a tool parameter."""
        param = ToolParameter(
            name="frequency",
            type="number",
            description="Frequency in Hz",
            required=True,
        )
        assert param.name == "frequency"
        assert param.type == "number"
        assert param.description == "Frequency in Hz"
        assert param.required is True

    def test_parameter_to_dict(self):
        """Test converting parameter to dictionary."""
        param = ToolParameter(
            name="mode",
            type="string",
            description="Operation mode",
            required=False,
            default="normal",
            enum=["normal", "fast", "slow"],
        )
        param_dict = param.to_dict()
        assert param_dict["name"] == "mode"
        assert param_dict["type"] == "string"
        assert param_dict["default"] == "normal"
        assert param_dict["enum"] == ["normal", "fast", "slow"]

    def test_parameter_from_dict(self):
        """Test creating parameter from dictionary."""
        param_dict = {
            "name": "voltage",
            "type": "number",
            "description": "Voltage in V",
            "required": True,
        }
        param = ToolParameter.from_dict(param_dict)
        assert param.name == "voltage"
        assert param.type == "number"
        assert param.required is True


class TestToolSpec:
    """Tests for ToolSpec dataclass."""

    @pytest.fixture
    def valid_spec_dict(self):
        """Create a valid tool specification dictionary."""
        return {
            "name": "test_tool",
            "version": "1.0.0",
            "description": "A test tool for unit testing",
            "author": "test_author",
            "created_at": "2025-10-01T12:00:00Z",
            "updated_at": "2025-10-01T12:00:00Z",
            "capabilities": ["cap:qcodes.read"],
            "parameters": [
                {
                    "name": "param1",
                    "type": "string",
                    "description": "Test parameter",
                    "required": True,
                }
            ],
            "returns": {"type": "string", "description": "Test result"},
            "source_code": "def test_func():\n    return 'test'",
            "examples": ["test_tool(param1='value')"],
            "tags": ["test", "example"],
        }

    def test_create_tool_spec(self, valid_spec_dict):
        """Test creating a tool spec from dictionary."""
        spec = ToolSpec.from_dict(valid_spec_dict)
        assert spec.name == "test_tool"
        assert spec.version == "1.0.0"
        assert len(spec.parameters) == 1
        assert spec.parameters[0].name == "param1"

    def test_tool_spec_to_dict(self, valid_spec_dict):
        """Test converting tool spec to dictionary."""
        spec = ToolSpec.from_dict(valid_spec_dict)
        spec_dict = spec.to_dict()
        assert spec_dict["name"] == "test_tool"
        assert spec_dict["version"] == "1.0.0"
        assert len(spec_dict["parameters"]) == 1

    def test_tool_spec_to_json(self, valid_spec_dict):
        """Test converting tool spec to JSON."""
        spec = ToolSpec.from_dict(valid_spec_dict)
        json_str = spec.to_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "test_tool"

    def test_tool_spec_from_json(self, valid_spec_dict):
        """Test creating tool spec from JSON."""
        json_str = json.dumps(valid_spec_dict)
        spec = ToolSpec.from_json(json_str)
        assert spec.name == "test_tool"


class TestToolSpecValidation:
    """Tests for tool specification validation."""

    def test_validate_valid_spec(self):
        """Test validating a valid tool spec."""
        spec = create_tool_spec(
            name="test_tool",
            version="1.0.0",
            description="A test tool for unit testing purposes",
            author="test_author",
            capabilities=["cap:qcodes.read"],
            parameters=[
                {
                    "name": "param1",
                    "type": "string",
                    "description": "Test parameter",
                }
            ],
            returns={"type": "string", "description": "Test result"},
            source_code="def test_func():\n    return 'test'",
        )
        # Should not raise
        validate_tool_spec(spec)

    def test_invalid_name_format(self):
        """Test validation fails for invalid name format."""
        with pytest.raises(ValidationError, match="Invalid tool name"):
            create_tool_spec(
                name="Test-Tool",  # Invalid: contains hyphen and uppercase
                version="1.0.0",
                description="A test tool for unit testing purposes",
                author="test_author",
                capabilities=["cap:qcodes.read"],
                parameters=[],
                returns={"type": "string", "description": "Test result"},
                source_code="def test_func():\n    return 'test'",
            )

    def test_invalid_version_format(self):
        """Test validation fails for invalid version format."""
        with pytest.raises(ValidationError, match="Invalid version"):
            create_tool_spec(
                name="test_tool",
                version="1.0",  # Invalid: not semantic version
                description="A test tool for unit testing purposes",
                author="test_author",
                capabilities=["cap:qcodes.read"],
                parameters=[],
                returns={"type": "string", "description": "Test result"},
                source_code="def test_func():\n    return 'test'",
            )

    def test_description_too_short(self):
        """Test validation fails for too short description."""
        with pytest.raises(ValidationError, match="Description too short"):
            create_tool_spec(
                name="test_tool",
                version="1.0.0",
                description="Short",  # Too short
                author="test_author",
                capabilities=["cap:qcodes.read"],
                parameters=[],
                returns={"type": "string", "description": "Test result"},
                source_code="def test_func():\n    return 'test'",
            )

    def test_freeform_capabilities_allowed(self):
        """Test that freeform capability labels are allowed (v2.0.0)."""
        # Any non-empty string is valid as capability label
        spec = create_tool_spec(
            name="test_tool",
            version="1.0.0",
            description="A test tool for unit testing purposes",
            author="test_author",
            capabilities=[
                "cap:numpy.array",  # Suggested format
                "data-processing",  # Simple label
                "custom.analysis",  # No cap: prefix
                "UPPERCASE",  # Any case
                "123numeric",  # Can start with number
            ],
            parameters=[],
            returns={"type": "string", "description": "Test result"},
            source_code="def test_func():\n    return 'test'",
        )
        # Should not raise - all freeform labels are valid
        assert len(spec.capabilities) == 5

    def test_empty_capability_string_invalid(self):
        """Test validation fails for empty capability strings."""
        with pytest.raises(ValidationError, match="Invalid capability"):
            create_tool_spec(
                name="test_tool",
                version="1.0.0",
                description="A test tool for unit testing purposes",
                author="test_author",
                capabilities=[""],  # Empty string not allowed
                parameters=[],
                returns={"type": "string", "description": "Test result"},
                source_code="def test_func():\n    return 'test'",
            )

    def test_duplicate_parameter_names(self):
        """Test validation fails for duplicate parameter names."""
        with pytest.raises(ValidationError, match="Duplicate parameter name"):
            create_tool_spec(
                name="test_tool",
                version="1.0.0",
                description="A test tool for unit testing purposes",
                author="test_author",
                capabilities=["cap:qcodes.read"],
                parameters=[
                    {"name": "param1", "type": "string", "description": "Test param"},
                    {"name": "param1", "type": "number", "description": "Duplicate"},
                ],
                returns={"type": "string", "description": "Test result"},
                source_code="def test_func():\n    return 'test'",
            )

    def test_invalid_source_code_syntax(self):
        """Test validation fails for invalid source code syntax."""
        with pytest.raises(ValidationError, match="syntax error"):
            create_tool_spec(
                name="test_tool",
                version="1.0.0",
                description="A test tool for unit testing purposes",
                author="test_author",
                capabilities=["cap:qcodes.read"],
                parameters=[],
                returns={"type": "string", "description": "Test result"},
                source_code="def test_func(\n    return 'test'",  # Syntax error
            )


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    @pytest.fixture
    def temp_registry_path(self):
        """Create a temporary registry directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def registry(self, temp_registry_path):
        """Create a tool registry with temporary path."""
        return ToolRegistry(registry_path=temp_registry_path)

    @pytest.fixture
    def sample_spec(self):
        """Create a sample tool specification."""
        return create_tool_spec(
            name="sample_tool",
            version="1.0.0",
            description="A sample tool for testing purposes",
            author="test_author",
            capabilities=["cap:qcodes.read"],
            parameters=[
                {"name": "param1", "type": "string", "description": "Test parameter"}
            ],
            returns={"type": "string", "description": "Test result"},
            source_code="def sample_func():\n    return 'sample'",
        )

    def test_register_tool(self, registry, sample_spec):
        """Test registering a new tool."""
        registry.register(sample_spec)
        assert registry.exists("sample_tool")
        retrieved = registry.get("sample_tool")
        assert retrieved.name == "sample_tool"
        assert retrieved.version == "1.0.0"

    def test_register_duplicate_tool(self, registry, sample_spec):
        """Test registering a duplicate tool fails."""
        registry.register(sample_spec)
        with pytest.raises(RegistryError, match="already exists"):
            registry.register(sample_spec)

    def test_update_tool(self, registry, sample_spec):
        """Test updating an existing tool."""
        registry.register(sample_spec)

        # Update version
        updated_spec = create_tool_spec(
            name="sample_tool",
            version="2.0.0",
            description="Updated description for testing purposes",
            author="test_author",
            capabilities=["cap:qcodes.read"],
            parameters=[
                {"name": "param1", "type": "string", "description": "Test parameter"}
            ],
            returns={"type": "string", "description": "Test result"},
            source_code="def sample_func():\n    return 'updated'",
        )

        registry.update(updated_spec)
        retrieved = registry.get("sample_tool")
        assert retrieved.version == "2.0.0"
        assert "updated" in retrieved.source_code

    def test_update_nonexistent_tool(self, registry, sample_spec):
        """Test updating a nonexistent tool fails."""
        with pytest.raises(RegistryError, match="does not exist"):
            registry.update(sample_spec)

    def test_revoke_tool(self, registry, sample_spec):
        """Test revoking a tool."""
        registry.register(sample_spec)
        assert registry.exists("sample_tool")

        registry.revoke("sample_tool")
        assert not registry.exists("sample_tool")
        assert registry.get("sample_tool") is None

    def test_revoke_nonexistent_tool(self, registry):
        """Test revoking a nonexistent tool fails."""
        with pytest.raises(RegistryError, match="does not exist"):
            registry.revoke("nonexistent_tool")

    def test_list_tools(self, registry):
        """Test listing tools."""
        # Register multiple tools
        for i in range(3):
            spec = create_tool_spec(
                name=f"tool_{i}",
                version="1.0.0",
                description=f"Tool {i} for testing purposes",
                author="test_author",
                capabilities=["cap:qcodes.read"],
                parameters=[],
                returns={"type": "string", "description": "Test result"},
                source_code="def func():\n    return 'test'",
                tags=[f"tag_{i}"],
            )
            registry.register(spec)

        tools = registry.list_tools()
        assert len(tools) == 3
        assert all("name" in tool for tool in tools)

    def test_list_tools_with_filters(self, registry):
        """Test listing tools with filters."""
        # Register tools with different attributes
        spec1 = create_tool_spec(
            name="tool_1",
            version="1.0.0",
            description="First tool for testing purposes",
            author="author1",
            capabilities=["cap:qcodes.read"],
            parameters=[],
            returns={"type": "string", "description": "Test result"},
            source_code="def func():\n    return 'test'",
            tags=["tag_a"],
        )
        spec2 = create_tool_spec(
            name="tool_2",
            version="1.0.0",
            description="Second tool for testing purposes",
            author="author2",
            capabilities=["cap:qcodes.write"],
            parameters=[],
            returns={"type": "string", "description": "Test result"},
            source_code="def func():\n    return 'test'",
            tags=["tag_b"],
        )

        registry.register(spec1)
        registry.register(spec2)

        # Filter by author
        tools = registry.list_tools(author="author1")
        assert len(tools) == 1
        assert tools[0]["name"] == "tool_1"

        # Filter by tag
        tools = registry.list_tools(tag="tag_b")
        assert len(tools) == 1
        assert tools[0]["name"] == "tool_2"

        # Filter by capability
        tools = registry.list_tools(capability="cap:qcodes.write")
        assert len(tools) == 1
        assert tools[0]["name"] == "tool_2"

    def test_registry_persistence(self, temp_registry_path, sample_spec):
        """Test that registry persists to disk."""
        # Create registry and register tool
        registry1 = ToolRegistry(registry_path=temp_registry_path)
        registry1.register(sample_spec)

        # Create new registry instance and verify tool exists
        registry2 = ToolRegistry(registry_path=temp_registry_path)
        assert registry2.exists("sample_tool")
        retrieved = registry2.get("sample_tool")
        assert retrieved.name == "sample_tool"

    def test_get_stats(self, registry):
        """Test getting registry statistics."""
        # Register some tools
        for i in range(3):
            spec = create_tool_spec(
                name=f"tool_{i}",
                version="1.0.0",
                description=f"Tool {i} for testing purposes",
                author="test_author",
                capabilities=["cap:qcodes.read"],
                parameters=[],
                returns={"type": "string", "description": "Test result"},
                source_code="def func():\n    return 'test'",
            )
            registry.register(spec)

        stats = registry.get_stats()
        assert stats["total_tools"] == 3
        assert "test_author" in stats["tools_by_author"]
        assert stats["tools_by_author"]["test_author"] == 3


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def temp_log_path(self):
        """Create a temporary log file path."""
        temp_dir = Path(tempfile.mkdtemp())
        log_path = temp_dir / "test_audit.log"
        yield log_path
        # Clean up logger handlers before removing directory
        import logging

        audit_logger = logging.getLogger("instrmcp.audit")
        # Close all handlers to release file handles
        for handler in audit_logger.handlers[:]:
            handler.close()
            audit_logger.removeHandler(handler)

        # Use ignore_errors on Windows to avoid file locking issues
        import sys

        shutil.rmtree(temp_dir, ignore_errors=(sys.platform == "win32"))

    @pytest.fixture
    def logger(self, temp_log_path):
        """Create an audit logger with temporary path."""
        # Clear any existing handlers to avoid reusing loggers across tests
        import logging

        audit_logger = logging.getLogger("instrmcp.audit")
        # Close and remove any existing handlers
        for handler in audit_logger.handlers[:]:
            handler.close()
            audit_logger.removeHandler(handler)

        # Create new logger instance
        logger_instance = AuditLogger(log_path=temp_log_path)
        yield logger_instance

        # Cleanup after test
        for handler in audit_logger.handlers[:]:
            handler.close()
            audit_logger.removeHandler(handler)

    def test_log_registration(self, logger, temp_log_path):
        """Test logging a tool registration."""
        logger.log_registration(
            tool_name="test_tool",
            version="1.0.0",
            author="test_author",
            capabilities=["cap:qcodes.read"],
        )

        # Flush handlers to ensure data is written to disk
        for handler in logger.logger.handlers:
            handler.flush()

        # Read log file
        with open(temp_log_path, "r") as f:
            log_content = f.read()

        assert "REGISTER" in log_content
        assert "test_tool" in log_content
        assert "1.0.0" in log_content

    def test_log_update(self, logger, temp_log_path):
        """Test logging a tool update."""
        logger.log_update(
            tool_name="test_tool",
            old_version="1.0.0",
            new_version="2.0.0",
            author="test_author",
        )

        # Flush handlers to ensure data is written to disk
        for handler in logger.logger.handlers:
            handler.flush()

        with open(temp_log_path, "r") as f:
            log_content = f.read()

        assert "UPDATE" in log_content
        assert "test_tool" in log_content
        assert "1.0.0" in log_content
        assert "2.0.0" in log_content

    def test_log_revocation(self, logger, temp_log_path):
        """Test logging a tool revocation."""
        logger.log_revocation(
            tool_name="test_tool", version="1.0.0", reason="Security issue"
        )

        # Flush handlers to ensure data is written to disk
        for handler in logger.logger.handlers:
            handler.flush()

        with open(temp_log_path, "r") as f:
            log_content = f.read()

        assert "REVOKE" in log_content
        assert "test_tool" in log_content
        assert "Security issue" in log_content

    def test_log_error(self, logger, temp_log_path):
        """Test logging an error."""
        logger.log_error(
            operation="register", tool_name="test_tool", error="Validation failed"
        )

        # Flush handlers to ensure data is written to disk
        for handler in logger.logger.handlers:
            handler.flush()

        with open(temp_log_path, "r") as f:
            log_content = f.read()

        assert "ERROR" in log_content
        assert "register" in log_content
        assert "Validation failed" in log_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
