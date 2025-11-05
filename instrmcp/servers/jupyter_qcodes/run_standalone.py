#!/usr/bin/env python3
"""
Standalone QCoDeS MCP server for testing without Jupyter.

This script runs the MCP server directly using STDIO transport,
making it compatible with Claude Desktop and other MCP clients.
Useful for testing the server without requiring Jupyter setup.
"""

import sys
import os
import logging

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP
from mcp.types import TextContent
from tools import QCodesReadOnlyTools

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockIPython:
    """Mock IPython instance for standalone testing."""

    def __init__(self):
        self.user_ns = {
            "standalone_mode": True,
            "test_data": [1, 2, 3, 4, 5],
            "message": "Running in standalone test mode",
        }
        self.execution_count = 1

        # Try to create some mock QCoDeS instruments if available
        try:
            import qcodes as qc
            from qcodes.instrument_drivers.mock_instruments import MockDAC

            # Create mock station
            self.user_ns["station"] = qc.Station()

            # Add mock instruments
            mock_dac1 = MockDAC("mock_dac1", num_channels=2)
            mock_dac2 = MockDAC("mock_dac2", num_channels=2)

            self.user_ns["mock_dac1"] = mock_dac1
            self.user_ns["mock_dac2"] = mock_dac2
            self.user_ns["station"].add_component(mock_dac1)
            self.user_ns["station"].add_component(mock_dac2)

            # Set some initial values
            mock_dac1.ch01.voltage(0.1)
            mock_dac1.ch02.voltage(0.2)
            mock_dac2.ch01.voltage(1.1)
            mock_dac2.ch02.voltage(1.2)

            logger.debug("Created mock QCoDeS instruments for testing")

        except ImportError as e:
            logger.warning(f"QCoDeS not available, using minimal mock: {e}")
            self.user_ns["qcodes_available"] = False
        except Exception as e:
            logger.error(f"Error creating mock instruments: {e}")
            self.user_ns["instrument_error"] = str(e)


def create_standalone_server() -> FastMCP:
    """Create a standalone MCP server for testing."""

    mcp = FastMCP("QCoDeS Standalone Test Server")

    # Create mock IPython instance
    mock_ipython = MockIPython()

    # Initialize tools with mock IPython
    tools = QCodesReadOnlyTools(mock_ipython)

    @mcp.tool()
    async def list_instruments() -> list[TextContent]:
        """List instruments available in standalone mode."""
        try:
            result = await tools.list_instruments()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            logger.error(f"Error listing instruments: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    @mcp.tool()
    async def instrument_info(
        name: str, with_values: bool = False
    ) -> list[TextContent]:
        """Get information about a mock instrument."""
        try:
            result = await tools.instrument_info(name, with_values)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            logger.error(f"Error getting instrument info: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    @mcp.tool()
    async def get_parameter_value(
        instrument: str, parameter: str, fresh: bool = False
    ) -> list[TextContent]:
        """Get a parameter value from mock instrument."""
        try:
            result = await tools.get_parameter_value(instrument, parameter, fresh)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            logger.error(f"Error getting parameter value: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    @mcp.tool()
    async def list_variables() -> list[TextContent]:
        """List variables in mock namespace."""
        try:
            result = await tools.list_variables()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            logger.error(f"Error listing variables: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    @mcp.tool()
    async def station_snapshot() -> list[TextContent]:
        """Get station snapshot if available."""
        try:
            result = await tools.station_snapshot()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            logger.error(f"Error getting station snapshot: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    @mcp.tool()
    async def server_status() -> list[TextContent]:
        """Get server status - shows this is standalone test mode."""
        status = {
            "mode": "standalone_test",
            "message": "Running standalone QCoDeS MCP server for testing",
            "tools_available": len(
                [name for name in dir(mcp) if not name.startswith("_")]
            ),
            "mock_instruments": list(
                mock_ipython.user_ns.get("station", {}).get_components()
                if "station" in mock_ipython.user_ns
                else {}
            ),
            "namespace_variables": len(mock_ipython.user_ns),
        }
        return [TextContent(type="text", text=str(status))]

    return mcp


def main():
    """Main function to run the standalone server."""
    print("🧪 Starting QCoDeS MCP Standalone Test Server...", file=sys.stderr)

    try:
        # Create and run the server
        mcp = create_standalone_server()

        print("✅ Server created successfully", file=sys.stderr)
        print(
            "🔧 Running with STDIO transport for Claude Desktop compatibility",
            file=sys.stderr,
        )
        print(
            "📋 Available tools: list_instruments, instrument_info, get_parameter_value, list_variables, station_snapshot, server_status",
            file=sys.stderr,
        )

        # Run with STDIO transport
        mcp.run(transport="stdio")

    except KeyboardInterrupt:
        print("\n👋 Standalone server stopped", file=sys.stderr)
    except Exception as e:
        print(f"❌ Server error: {e}", file=sys.stderr)
        logger.error(f"Server startup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
