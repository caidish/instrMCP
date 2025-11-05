"""Dynamic tool execution runtime.

This module handles the execution of dynamically created tools in the Jupyter kernel context.
"""

import logging
from typing import Any, Dict

from instrmcp.tools.dynamic import ToolSpec

logger = logging.getLogger(__name__)


class DynamicToolRuntime:
    """Runtime for executing dynamically created tools."""

    def __init__(self, ipython):
        """Initialize the dynamic tool runtime.

        Args:
            ipython: IPython instance for code execution
        """
        self.ipython = ipython
        self._tool_functions: Dict[str, callable] = {}

    def compile_tool(self, spec: ToolSpec) -> callable:
        """Compile a tool specification into an executable function.

        Args:
            spec: The tool specification to compile

        Returns:
            Compiled function ready for execution

        Raises:
            RuntimeError: If compilation fails
        """
        try:
            # Create a namespace for the tool
            namespace = {
                "__name__": f"dynamic_tool_{spec.name}",
                "__file__": f"<dynamic:{spec.name}>",
            }

            # Add IPython kernel's user namespace (for access to variables, imports, etc.)
            namespace.update(self.ipython.user_ns)

            # Compile and execute the source code in the namespace
            code = compile(spec.source_code, f"<tool:{spec.name}>", "exec")
            exec(code, namespace)

            # Find the tool function in the namespace
            # We expect the source code to define a function with the same name as the tool
            if spec.name not in namespace:
                raise RuntimeError(
                    f"Tool source code must define a function named '{spec.name}'"
                )

            tool_func = namespace[spec.name]
            if not callable(tool_func):
                raise RuntimeError(
                    f"'{spec.name}' in tool source code is not a function"
                )

            # Store the compiled function
            self._tool_functions[spec.name] = tool_func

            logger.debug(f"Successfully compiled dynamic tool: {spec.name}")
            return tool_func

        except Exception as e:
            logger.error(f"Failed to compile tool {spec.name}: {e}")
            raise RuntimeError(f"Tool compilation failed: {e}")

    def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a dynamic tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool function

        Returns:
            Result from the tool execution

        Raises:
            RuntimeError: If tool is not found or execution fails
        """
        if tool_name not in self._tool_functions:
            raise RuntimeError(f"Tool '{tool_name}' is not compiled/registered")

        tool_func = self._tool_functions[tool_name]

        try:
            logger.debug(f"Executing dynamic tool: {tool_name} with args: {kwargs}")
            result = tool_func(**kwargs)
            logger.debug(f"Tool {tool_name} executed successfully")
            return result

        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}", exc_info=True)
            raise RuntimeError(f"Tool execution failed: {e}")

    def unregister_tool(self, tool_name: str) -> None:
        """Unregister a compiled tool.

        Args:
            tool_name: Name of the tool to unregister
        """
        if tool_name in self._tool_functions:
            del self._tool_functions[tool_name]
            logger.debug(f"Unregistered dynamic tool: {tool_name}")

    def list_compiled_tools(self) -> list[str]:
        """Get list of currently compiled tool names.

        Returns:
            List of tool names
        """
        return list(self._tool_functions.keys())

    def is_tool_compiled(self, tool_name: str) -> bool:
        """Check if a tool is compiled and ready for execution.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool is compiled, False otherwise
        """
        return tool_name in self._tool_functions
