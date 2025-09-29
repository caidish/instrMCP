"""
Resource registrar for MCP server.

Registers all MCP resources (core, MeasureIt templates, and database resources).
"""

import json
import logging

from mcp.types import Resource, TextResourceContents

logger = logging.getLogger(__name__)


class ResourceRegistrar:
    """Registers all MCP resources with the server."""

    def __init__(self, mcp_server, tools, enabled_options=None, measureit_module=None, db_module=None):
        """
        Initialize the resource registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
            enabled_options: Set of enabled optional features
            measureit_module: MeasureIt integration module (optional)
            db_module: Database integration module (optional)
        """
        self.mcp = mcp_server
        self.tools = tools
        self.enabled_options = enabled_options or set()
        self.measureit = measureit_module
        self.db = db_module

    def register_all(self):
        """Register all resources."""
        self._register_core_resources()
        
        if 'measureit' in self.enabled_options and self.measureit:
            self._register_measureit_resources()
        
        if 'database' in self.enabled_options and self.db:
            self._register_database_resources()

    def _register_core_resources(self):
        """Register core QCodes and notebook resources."""
        
        @self.mcp.resource("resource://available_instruments")
        async def available_instruments() -> Resource:
            """Resource providing list of available QCodes instruments."""
            try:
                instruments = await self.tools.list_instruments()
                content = json.dumps(instruments, indent=2, default=str)
                
                return Resource(
                    uri="resource://available_instruments",
                    name="Available Instruments",
                    description="List of QCodes instruments available in the namespace with hierarchical parameter structure",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://available_instruments",
                        mimeType="application/json",
                        text=content
                    )]
                )
            except Exception as e:
                logger.error(f"Error generating available_instruments resource: {e}")
                error_content = json.dumps({"error": str(e), "status": "error"}, indent=2)
                return Resource(
                    uri="resource://available_instruments",
                    name="Available Instruments (Error)",
                    description="Error retrieving available instruments",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://available_instruments",
                        mimeType="application/json",
                        text=error_content
                    )]
                )

        @self.mcp.resource("resource://station_state")
        async def station_state() -> Resource:
            """Resource providing current QCodes station snapshot."""
            try:
                snapshot = await self.tools.get_station_snapshot()
                content = json.dumps(snapshot, indent=2, default=str)
                
                return Resource(
                    uri="resource://station_state",
                    name="QCodes Station State",
                    description="Current QCodes station snapshot without parameter values",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://station_state",
                        mimeType="application/json",
                        text=content
                    )]
                )
            except Exception as e:
                logger.error(f"Error generating station_state resource: {e}")
                error_content = json.dumps({"error": str(e), "status": "error"}, indent=2)
                return Resource(
                    uri="resource://station_state",
                    name="Station State (Error)",
                    description="Error retrieving station state",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://station_state",
                        mimeType="application/json",
                        text=error_content
                    )]
                )

    def _register_measureit_resources(self):
        """Register MeasureIt template resources."""
        
        # Import MeasureIt template functions
        from ....extensions.MeasureIt import (
            get_sweep0d_template,
            get_sweep1d_template,
            get_sweep2d_template,
            get_simulsweep_template,
            get_sweepqueue_template,
            get_common_patterns_template,
            get_measureit_code_examples
        )
        
        templates = [
            ("measureit_sweep0d_template", "MeasureIt Sweep0D Template", 
             "Sweep0D code examples and patterns for time-based monitoring", get_sweep0d_template),
            ("measureit_sweep1d_template", "MeasureIt Sweep1D Template",
             "Sweep1D code examples and patterns for single parameter sweeps", get_sweep1d_template),
            ("measureit_sweep2d_template", "MeasureIt Sweep2D Template",
             "Sweep2D code examples and patterns for 2D parameter mapping", get_sweep2d_template),
            ("measureit_simulsweep_template", "MeasureIt SimulSweep Template",
             "SimulSweep code examples for simultaneous parameter sweeping", get_simulsweep_template),
            ("measureit_sweepqueue_template", "MeasureIt SweepQueue Template",
             "SweepQueue code examples for sequential measurement workflows", get_sweepqueue_template),
            ("measureit_common_patterns", "MeasureIt Common Patterns",
             "Common MeasureIt patterns and best practices", get_common_patterns_template),
            ("measureit_code_examples", "MeasureIt Code Examples",
             "Complete collection of ALL MeasureIt patterns in structured format", get_measureit_code_examples),
        ]
        
        for uri_suffix, name, description, get_content_func in templates:
            self._register_template_resource(uri_suffix, name, description, get_content_func)

    def _register_template_resource(self, uri_suffix, name, description, get_content_func):
        """Helper to register a template resource."""
        uri = f"resource://{uri_suffix}"
        
        @self.mcp.resource(uri)
        async def template_resource() -> Resource:
            content = get_content_func()
            return Resource(
                uri=uri,
                name=name,
                description=description,
                mimeType="application/json",
                contents=[TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=content
                )]
            )

    def _register_database_resources(self):
        """Register database integration resources."""
        
        @self.mcp.resource("resource://database_config")
        async def database_config() -> Resource:
            """Resource providing current QCodes database configuration."""
            content = self.db.get_current_database_config()
            return Resource(
                uri="resource://database_config",
                name="Database Configuration",
                description="Current QCodes database configuration, path, and connection status",
                mimeType="application/json",
                contents=[TextResourceContents(
                    uri="resource://database_config",
                    mimeType="application/json",
                    text=content
                )]
            )

        @self.mcp.resource("resource://recent_measurements")
        async def recent_measurements() -> Resource:
            """Resource providing metadata for recent measurements."""
            content = self.db.get_recent_measurements()
            return Resource(
                uri="resource://recent_measurements",
                name="Recent Measurements",
                description="Metadata for recent measurements across all experiments",
                mimeType="application/json",
                contents=[TextResourceContents(
                    uri="resource://recent_measurements",
                    mimeType="application/json",
                    text=content
                )]
            )
