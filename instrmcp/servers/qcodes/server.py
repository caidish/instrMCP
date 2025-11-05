"""QCodes MCP Server

Station-based FastMCP HTTP server for QCodes instrument control.
"""

import os
import json
import logging
from typing import List

# Removed nest_asyncio - not needed for normal Python environments

from fastmcp import FastMCP
from mcp.types import Resource, TextResourceContents, TextContent

from .station_init import station_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class QCodesStationServer:
    """QCodes Station-based MCP Server using FastMCP."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.mcp_path = os.getenv("MCP_PATH", "/mcp")
        self.mcp = FastMCP("QCodes Station MCP Server")

        # Initialize station manager
        self.station_manager = station_manager

        # Setup server
        self._register_resources()
        self._register_tools()

    def _register_resources(self):
        """Register MCP resources."""

        @self.mcp.resource("resource://available_instr")
        async def available_instr() -> Resource:
            """Resource providing list of available instruments."""
            try:
                # Get available instruments
                available = self.station_manager.get_available_instruments()

                # Convert to JSON string
                content = json.dumps(available, indent=2, default=str)

                return Resource(
                    uri="resource://available_instr",
                    name="Available Instruments",
                    description="List of instruments available in the QCodes station",
                    mimeType="application/json",
                    contents=[
                        TextResourceContents(
                            uri="resource://available_instr",
                            mimeType="application/json",
                            text=content,
                        )
                    ],
                )

            except Exception as e:
                logger.error(f"Error generating available_instr resource: {e}")
                error_content = json.dumps(
                    {"error": str(e), "status": "error"}, indent=2
                )

                return Resource(
                    uri="resource://available_instr",
                    name="Available Instruments (Error)",
                    description="Error retrieving available instruments",
                    mimeType="application/json",
                    contents=[
                        TextResourceContents(
                            uri="resource://available_instr",
                            mimeType="application/json",
                            text=error_content,
                        )
                    ],
                )

    def _register_tools(self):
        """Register MCP tools."""

        @self.mcp.tool()
        async def all_instr_health(update: bool = False) -> List[TextContent]:
            """Get health snapshot for all instruments in the station.

            Args:
                update: Whether to update from hardware (slow, default: False)
            """
            try:
                logger.debug(f"Getting all instrument health (update={update})")

                if not self.station_manager.station:
                    result = {"error": "Station not initialized", "status": "error"}
                else:
                    snapshot = self.station_manager.get_station_snapshot(update=update)
                    result = {
                        "station_snapshot": snapshot,
                        "update": update,
                        "timestamp": snapshot.get("__timestamp"),
                        "status": "success",
                    }

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]

            except Exception as e:
                logger.error(f"Error in all_instr_health: {e}")
                error_result = {
                    "error": str(e),
                    "tool": "all_instr_health",
                    "status": "error",
                }
                return [
                    TextContent(type="text", text=json.dumps(error_result, indent=2))
                ]

        @self.mcp.tool()
        async def inst_health(name: str, update: bool = True) -> List[TextContent]:
            """Get health snapshot for a specific instrument.

            Args:
                name: Instrument name
                update: Whether to update from hardware (default: True for single instruments)
            """
            try:
                logger.debug(
                    f"Getting instrument health for '{name}' (update={update})"
                )

                if not self.station_manager.station:
                    result = {"error": "Station not initialized", "status": "error"}
                else:
                    snapshot = self.station_manager.get_instrument_snapshot(
                        name, update=update
                    )
                    result = {
                        "instrument": name,
                        "snapshot": snapshot,
                        "update": update,
                        "timestamp": snapshot.get("__timestamp"),
                        "status": "success",
                    }

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]

            except Exception as e:
                logger.error(f"Error in inst_health for '{name}': {e}")
                error_result = {
                    "error": str(e),
                    "instrument": name,
                    "tool": "inst_health",
                    "status": "error",
                }
                return [
                    TextContent(type="text", text=json.dumps(error_result, indent=2))
                ]

        # Backward compatibility alias for typo tolerance
        @self.mcp.tool()
        async def inst_healtn(name: str, update: bool = True) -> List[TextContent]:
            """Alias for inst_health (typo-tolerant).

            Args:
                name: Instrument name
                update: Whether to update from hardware (default: True)
            """
            logger.debug("Using typo-tolerant alias 'inst_healtn' -> 'inst_health'")
            return await inst_health(name, update)

        @self.mcp.tool()
        async def load_instrument(name: str) -> List[TextContent]:
            """Load an instrument from the station configuration.

            Args:
                name: Instrument name from configuration
            """
            try:
                logger.debug(f"Loading instrument '{name}'")

                instrument = self.station_manager.load_instrument(name)

                if instrument is None:
                    result = {
                        "error": f"Failed to load instrument '{name}' (may be disabled)",
                        "instrument": name,
                        "status": "error",
                    }
                else:
                    # Update available instruments file
                    self.station_manager.generate_available_instruments_file()

                    result = {
                        "message": f"Successfully loaded instrument '{name}'",
                        "instrument": name,
                        "type": type(instrument).__name__,
                        "parameters": (
                            list(instrument.parameters.keys())
                            if hasattr(instrument, "parameters")
                            else []
                        ),
                        "status": "success",
                    }

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error loading instrument '{name}': {e}")
                error_result = {
                    "error": str(e),
                    "instrument": name,
                    "tool": "load_instrument",
                    "status": "error",
                }
                return [
                    TextContent(type="text", text=json.dumps(error_result, indent=2))
                ]

        @self.mcp.tool()
        async def close_instrument(name: str) -> List[TextContent]:
            """Close a specific instrument and remove it from the station.

            Args:
                name: Instrument name to close
            """
            try:
                logger.debug(f"Closing instrument '{name}'")

                success = self.station_manager.close_instrument(name)

                if success:
                    # Update available instruments file
                    self.station_manager.generate_available_instruments_file()

                    result = {
                        "message": f"Successfully closed instrument '{name}'",
                        "instrument": name,
                        "status": "success",
                    }
                else:
                    result = {
                        "error": f"Failed to close instrument '{name}' (may not be loaded)",
                        "instrument": name,
                        "status": "error",
                    }

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error closing instrument '{name}': {e}")
                error_result = {
                    "error": str(e),
                    "instrument": name,
                    "tool": "close_instrument",
                    "status": "error",
                }
                return [
                    TextContent(type="text", text=json.dumps(error_result, indent=2))
                ]

        @self.mcp.tool()
        async def reconnect_instrument(name: str) -> List[TextContent]:
            """Reconnect an instrument (close and reload).

            Args:
                name: Instrument name to reconnect
            """
            try:
                logger.debug(f"Reconnecting instrument '{name}'")

                instrument = self.station_manager.reconnect_instrument(name)

                if instrument:
                    # Update available instruments file
                    self.station_manager.generate_available_instruments_file()

                    result = {
                        "message": f"Successfully reconnected instrument '{name}'",
                        "instrument": name,
                        "type": type(instrument).__name__,
                        "parameters": (
                            list(instrument.parameters.keys())
                            if hasattr(instrument, "parameters")
                            else []
                        ),
                        "status": "success",
                    }
                else:
                    result = {
                        "error": f"Failed to reconnect instrument '{name}'",
                        "instrument": name,
                        "status": "error",
                    }

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error reconnecting instrument '{name}': {e}")
                error_result = {
                    "error": str(e),
                    "instrument": name,
                    "tool": "reconnect_instrument",
                    "status": "error",
                }
                return [
                    TextContent(type="text", text=json.dumps(error_result, indent=2))
                ]

        @self.mcp.tool()
        async def station_info() -> List[TextContent]:
            """Get general station information and status."""
            try:
                logger.debug("Getting station information")

                if not self.station_manager.station:
                    result = {"error": "Station not initialized", "status": "error"}
                else:
                    components = list(self.station_manager.station.components.keys())
                    available = self.station_manager.get_available_instruments()

                    result = {
                        "station_initialized": True,
                        "loaded_instruments": components,
                        "loaded_count": len(components),
                        "available_instruments": list(available.keys()),
                        "available_count": len(available),
                        "config_path": self.station_manager.config_path,
                        "state_dir": str(self.station_manager.state_dir),
                        "status": "success",
                    }

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error getting station info: {e}")
                error_result = {
                    "error": str(e),
                    "tool": "station_info",
                    "status": "error",
                }
                return [
                    TextContent(type="text", text=json.dumps(error_result, indent=2))
                ]

    async def initialize_server(self):
        """Initialize the server and station."""
        try:
            logger.debug("Initializing QCodes Station MCP Server")

            # Initialize station
            self.station_manager.initialize_station()

            # Load all instruments automatically
            load_results = self.station_manager.load_all_instruments()
            if load_results:
                success_count = sum(load_results.values())
                total_count = len(load_results)
                logger.debug(
                    f"Auto-load complete: {success_count}/{total_count} instruments loaded"
                )
            else:
                logger.debug("No instruments to load")

            # Generate available instruments file
            self.station_manager.generate_available_instruments_file()

            logger.debug("Server initialization complete")

        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise

    def start(self):
        """Start the MCP server."""
        try:
            # Initialize server first (this needs to be sync now)
            import asyncio

            asyncio.run(self.initialize_server())

            logger.info("Starting QCodes Station MCP Server")
            logger.info(f"Host: {self.host}:{self.port}")
            logger.info(f"MCP Endpoint: http://{self.host}:{self.port}{self.mcp_path}")

            # Start FastMCP server - let it handle asyncio
            self.mcp.run(
                transport="http",
                host=self.host,
                port=self.port,  # HTTP transport
            )

        except Exception as e:
            logger.error(f"Server failed to start: {e}")
            raise

    async def cleanup(self):
        """Clean up resources on shutdown."""
        logger.debug("Cleaning up QCodes Station MCP Server")
        try:
            self.station_manager.close_station()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="QCodes Station MCP Server")
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port to bind server (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create server
    server = QCodesStationServer(host=args.host, port=args.port)

    try:
        # Run server - let FastMCP handle asyncio
        server.start()
    except KeyboardInterrupt:
        logger.debug("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
