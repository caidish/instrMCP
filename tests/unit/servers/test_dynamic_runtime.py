"""Unit tests for dynamic tool runtime."""

import pytest
from unittest.mock import Mock

from instrmcp.servers.jupyter_qcodes.options.dynamic_tool.runtime import (
    DynamicToolRuntime,
)
from instrmcp.servers.jupyter_qcodes.options.dynamic_tool import create_tool_spec


class TestDynamicToolRuntime:
    """Tests for DynamicToolRuntime class."""

    @pytest.fixture
    def mock_ipython(self):
        """Create a mock IPython instance."""
        ipython = Mock()
        ipython.user_ns = {
            "__builtins__": __builtins__,
            "test_var": 42,
        }
        return ipython

    @pytest.fixture
    def runtime(self, mock_ipython):
        """Create a DynamicToolRuntime instance."""
        return DynamicToolRuntime(mock_ipython)

    @pytest.fixture
    def simple_tool_spec(self):
        """Create a simple tool specification for testing."""
        return create_tool_spec(
            name="add_numbers",
            version="1.0.0",
            description="Add two numbers together",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[
                {"name": "a", "type": "number", "description": "First number"},
                {"name": "b", "type": "number", "description": "Second number"},
            ],
            returns={"type": "number", "description": "Sum of a and b"},
            source_code="def add_numbers(a, b):\n    return a + b",
        )

    def test_compile_simple_tool(self, runtime, simple_tool_spec):
        """Test compiling a simple tool."""
        func = runtime.compile_tool(simple_tool_spec)
        assert callable(func)
        assert runtime.is_tool_compiled("add_numbers")

    def test_execute_simple_tool(self, runtime, simple_tool_spec):
        """Test executing a simple tool."""
        runtime.compile_tool(simple_tool_spec)
        result = runtime.execute_tool("add_numbers", a=5, b=3)
        assert result == 8

    def test_compile_tool_with_imports(self, runtime):
        """Test compiling a tool that uses imports."""
        spec = create_tool_spec(
            name="multiply_array",
            version="1.0.0",
            description="Multiply array by scalar using numpy",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[
                {"name": "arr", "type": "array", "description": "Input array"},
                {"name": "scalar", "type": "number", "description": "Scalar value"},
            ],
            returns={"type": "array", "description": "Result array"},
            source_code="""
import numpy as np

def multiply_array(arr, scalar):
    return (np.array(arr) * scalar).tolist()
""",
        )

        func = runtime.compile_tool(spec)
        result = runtime.execute_tool("multiply_array", arr=[1, 2, 3], scalar=2)
        assert result == [2, 4, 6]

    def test_compile_tool_with_namespace_access(self, runtime, mock_ipython):
        """Test that compiled tools can access IPython namespace."""
        # Add a variable to IPython namespace
        mock_ipython.user_ns["multiplier"] = 10

        spec = create_tool_spec(
            name="use_namespace_var",
            version="1.0.0",
            description="Use variable from namespace",
            author="test",
            capabilities=["cap:notebook.read"],
            parameters=[
                {"name": "value", "type": "number", "description": "Input value"}
            ],
            returns={"type": "number", "description": "Result"},
            source_code="""
def use_namespace_var(value):
    return value * multiplier
""",
        )

        func = runtime.compile_tool(spec)
        result = runtime.execute_tool("use_namespace_var", value=5)
        assert result == 50

    def test_compile_tool_without_function(self, runtime):
        """Test that compilation fails if source code doesn't define the function."""
        spec = create_tool_spec(
            name="missing_function",
            version="1.0.0",
            description="Tool with missing function",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[],
            returns={"type": "string", "description": "Result"},
            source_code="x = 42  # No function defined",
        )

        with pytest.raises(RuntimeError, match="must define a function named"):
            runtime.compile_tool(spec)

    def test_compile_tool_with_syntax_error(self, runtime):
        """Test that compilation fails on syntax error."""
        # Note: This should be caught by validation in create_tool_spec,
        # but we test runtime behavior anyway
        try:
            spec = create_tool_spec(
                name="syntax_error",
                version="1.0.0",
                description="Tool with syntax error",
                author="test",
                capabilities=["cap:python.numpy"],
                parameters=[],
                returns={"type": "string", "description": "Result"},
                source_code="def syntax_error(\n    return 'bad'",  # Syntax error
            )
        except Exception:
            # Validation catches this, so skip test
            pytest.skip("Validation catches syntax errors")

    def test_execute_nonexistent_tool(self, runtime):
        """Test executing a tool that doesn't exist."""
        with pytest.raises(RuntimeError, match="not compiled/registered"):
            runtime.execute_tool("nonexistent_tool", x=1)

    def test_execute_tool_with_exception(self, runtime):
        """Test executing a tool that raises an exception."""
        spec = create_tool_spec(
            name="error_tool",
            version="1.0.0",
            description="Tool that raises an error",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[],
            returns={"type": "string", "description": "Result"},
            source_code="""
def error_tool():
    raise ValueError("Intentional error")
""",
        )

        runtime.compile_tool(spec)
        with pytest.raises(RuntimeError, match="Tool execution failed"):
            runtime.execute_tool("error_tool")

    def test_unregister_tool(self, runtime, simple_tool_spec):
        """Test unregistering a tool."""
        runtime.compile_tool(simple_tool_spec)
        assert runtime.is_tool_compiled("add_numbers")

        runtime.unregister_tool("add_numbers")
        assert not runtime.is_tool_compiled("add_numbers")

    def test_list_compiled_tools(self, runtime):
        """Test listing compiled tools."""
        spec1 = create_tool_spec(
            name="tool1",
            version="1.0.0",
            description="First tool",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[],
            returns={"type": "string", "description": "Result"},
            source_code="def tool1():\n    return 'tool1'",
        )

        spec2 = create_tool_spec(
            name="tool2",
            version="1.0.0",
            description="Second tool",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[],
            returns={"type": "string", "description": "Result"},
            source_code="def tool2():\n    return 'tool2'",
        )

        runtime.compile_tool(spec1)
        runtime.compile_tool(spec2)

        tools = runtime.list_compiled_tools()
        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    def test_tool_with_complex_logic(self, runtime):
        """Test a tool with more complex logic."""
        spec = create_tool_spec(
            name="fibonacci",
            version="1.0.0",
            description="Calculate Fibonacci number",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[
                {"name": "n", "type": "number", "description": "Position in sequence"}
            ],
            returns={"type": "number", "description": "Fibonacci number"},
            source_code="""
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
""",
        )

        runtime.compile_tool(spec)
        assert runtime.execute_tool("fibonacci", n=0) == 0
        assert runtime.execute_tool("fibonacci", n=1) == 1
        assert runtime.execute_tool("fibonacci", n=10) == 55

    def test_tool_returns_dict(self, runtime):
        """Test a tool that returns a dictionary."""
        spec = create_tool_spec(
            name="get_stats",
            version="1.0.0",
            description="Get statistics",
            author="test",
            capabilities=["cap:python.numpy"],
            parameters=[
                {"name": "numbers", "type": "array", "description": "List of numbers"}
            ],
            returns={"type": "object", "description": "Statistics"},
            source_code="""
def get_stats(numbers):
    return {
        'count': len(numbers),
        'sum': sum(numbers),
        'mean': sum(numbers) / len(numbers) if numbers else 0
    }
""",
        )

        runtime.compile_tool(spec)
        result = runtime.execute_tool("get_stats", numbers=[1, 2, 3, 4, 5])
        assert result["count"] == 5
        assert result["sum"] == 15
        assert result["mean"] == 3.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
