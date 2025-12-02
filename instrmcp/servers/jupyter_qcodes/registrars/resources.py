"""
Resource registrar for MCP server.

Registers all MCP resources (core, MeasureIt templates, and database resources).
"""

import asyncio
import json
import logging

from mcp.types import Resource, TextResourceContents

logger = logging.getLogger(__name__)


class ResourceRegistrar:
    """Registers all MCP resources with the server."""

    def __init__(
        self,
        mcp_server,
        tools,
        enabled_options=None,
        measureit_module=None,
        db_module=None,
    ):
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
        self._register_resource_guide_tool()
        self._register_core_resources()

        if "measureit" in self.enabled_options and self.measureit:
            self._register_measureit_resources()

        if "database" in self.enabled_options and self.db:
            self._register_database_resources()

    def _register_resource_guide_tool(self):
        """Register tools to help models discover and use MCP resources."""
        from mcp.types import TextContent

        @self.mcp.tool(name="mcp_list_resources")
        async def list_resources():
            """
            List all available MCP resources and guide on when to use them.

            MCP Resources provide READ-ONLY reference data and templates,
            while Tools perform active operations. Use this tool to discover
            what context and documentation is available.

            Returns:
                Comprehensive guide including all resource URIs, descriptions,
                use cases, and guidance on resources vs tools.
            """
            # Build list of available resources
            resources_list = []

            # Core QCodes resources (always available)
            resources_list.extend(
                [
                    {
                        "uri": "resource://available_instruments",
                        "name": "Available Instruments",
                        "description": "JSON list of QCodes instruments with hierarchical parameter structure",
                        "use_when": "Need to know what instruments exist BEFORE calling qcodes_instrument_info",
                        "example": "Check this first to see instrument names, then use tools to read specific parameters",
                    },
                    {
                        "uri": "resource://station_state",
                        "name": "QCodes Station State",
                        "description": "Complete station snapshot without parameter values",
                        "use_when": "Need overview of entire station configuration",
                        "example": "Get station structure without fetching live data from instruments",
                    },
                ]
            )

            # MeasureIt resources (if enabled)
            if "measureit" in self.enabled_options:
                resources_list.extend(
                    [
                        {
                            "uri": "resource://measureit_sweep0d_template",
                            "name": "MeasureIt Sweep0D Template",
                            "description": "Code examples for time-based monitoring",
                            "use_when": "Need to monitor parameters over time without sweeping",
                            "example": "Get complete working code for Sweep0D measurements",
                        },
                        {
                            "uri": "resource://measureit_sweep1d_template",
                            "name": "MeasureIt Sweep1D Template",
                            "description": "Code examples for single parameter sweeps",
                            "use_when": "Need to sweep one parameter and measure outputs",
                            "example": "Get patterns for voltage sweeps, frequency scans, etc.",
                        },
                        {
                            "uri": "resource://measureit_sweep2d_template",
                            "name": "MeasureIt Sweep2D Template",
                            "description": "Code examples for 2D parameter mapping",
                            "use_when": "Need to create 2D maps (e.g., gate voltage vs bias)",
                            "example": "Get code for two-parameter measurements",
                        },
                        {
                            "uri": "resource://measureit_simulsweep_template",
                            "name": "MeasureIt SimulSweep Template",
                            "description": "Code for simultaneous parameter sweeping",
                            "use_when": "Need to sweep multiple parameters together",
                            "example": "Coordinated multi-parameter sweeps",
                        },
                        {
                            "uri": "resource://measureit_sweepqueue_template",
                            "name": "MeasureIt SweepQueue Template",
                            "description": "Code for sequential measurement workflows",
                            "use_when": "Need to run multiple measurements in sequence",
                            "example": "Automated measurement sequences",
                        },
                        {
                            "uri": "resource://measureit_common_patterns",
                            "name": "MeasureIt Common Patterns",
                            "description": "Best practices and common patterns",
                            "use_when": "Need guidance on MeasureIt usage patterns",
                            "example": "Learn best practices for measurements",
                        },
                        {
                            "uri": "resource://measureit_code_examples",
                            "name": "MeasureIt Code Examples",
                            "description": "Complete collection of ALL MeasureIt patterns",
                            "use_when": "Need comprehensive reference for all measurement types",
                            "example": "Single source for all MeasureIt code patterns",
                        },
                    ]
                )

            # Database resources (if enabled)
            if "database" in self.enabled_options:
                resources_list.extend(
                    [
                        {
                            "uri": "resource://database_config",
                            "name": "Database Configuration",
                            "description": "Current database path and connection status",
                            "use_when": "Need to check database location before querying",
                            "example": "Verify database path before listing experiments",
                        },
                        {
                            "uri": "resource://recent_measurements",
                            "name": "Recent Measurements",
                            "description": "Metadata for recent measurements across all experiments",
                            "use_when": "Need quick overview of recent data",
                            "example": "Browse recent measurements without listing all experiments",
                        },
                    ]
                )

            # Build guidance
            guide = {
                "total_resources": len(resources_list),
                "resources": resources_list,
                "guidance": {
                    "workflow": "Check resources first for context, then use tools for operations",
                    "common_patterns": [
                        "Pattern 1: Check available_instruments → Use qcodes_instrument_info(name) for specific instrument",
                        "Pattern 2: Check measureit_code_examples → Adapt template code for specific measurement",
                        "Pattern 3: Check recent_measurements → Use database_get_dataset_info(id) for details",
                    ],
                },
            }

            return [TextContent(type="text", text=json.dumps(guide, indent=2))]

        @self.mcp.tool(name="mcp_get_resource")
        async def get_resource(uri: str):
            """
            Retrieve the content of a specific MCP resource by its URI.

            Use this tool to access resource content when you need the actual data
            (e.g., instrument list, templates, configuration). This is a fallback
            when direct resource access is not available.

            Args:
                uri: Resource URI (e.g., "resource://available_instruments")

            Returns:
                Resource content as JSON or text.

            Examples:
                - mcp_get_resource("resource://available_instruments")
                - mcp_get_resource("resource://measureit_sweep1d_template")
                - mcp_get_resource("resource://database_config")
            """
            # Map URIs to resource handlers
            resource_map = {
                "resource://available_instruments": self._get_available_instruments,
                "resource://station_state": self._get_station_state,
            }

            # Add MeasureIt resources if enabled
            if "measureit" in self.enabled_options:
                from ....extensions.measureit import (
                    get_sweep0d_template,
                    get_sweep1d_template,
                    get_sweep2d_template,
                    get_simulsweep_template,
                    get_sweepqueue_template,
                    get_common_patterns_template,
                    get_measureit_code_examples,
                )

                resource_map.update(
                    {
                        "resource://measureit_sweep0d_template": lambda: get_sweep0d_template(),
                        "resource://measureit_sweep1d_template": lambda: get_sweep1d_template(),
                        "resource://measureit_sweep2d_template": lambda: get_sweep2d_template(),
                        "resource://measureit_simulsweep_template": lambda: get_simulsweep_template(),
                        "resource://measureit_sweepqueue_template": lambda: get_sweepqueue_template(),
                        "resource://measureit_common_patterns": lambda: get_common_patterns_template(),
                        "resource://measureit_code_examples": lambda: get_measureit_code_examples(),
                    }
                )

            # Add database resources if enabled
            if "database" in self.enabled_options and self.db:
                resource_map.update(
                    {
                        "resource://database_config": lambda: self.db.get_current_database_config(),
                        "resource://recent_measurements": lambda: self.db.get_recent_measurements(),
                    }
                )

            # Check if URI is valid
            if uri not in resource_map:
                available_uris = list(resource_map.keys())
                error_msg = {
                    "error": f"Unknown resource URI: {uri}",
                    "available_uris": available_uris,
                    "hint": "Use mcp_list_resources() to see all available resources",
                }
                return [TextContent(type="text", text=json.dumps(error_msg, indent=2))]

            # Get resource content
            try:
                handler = resource_map[uri]
                if asyncio.iscoroutinefunction(handler):
                    content = await handler()
                else:
                    content = handler()

                return [TextContent(type="text", text=content)]
            except Exception as e:
                logger.error(f"Error retrieving resource {uri}: {e}")
                error_msg = {
                    "error": f"Failed to retrieve resource: {str(e)}",
                    "uri": uri,
                }
                return [TextContent(type="text", text=json.dumps(error_msg, indent=2))]

    async def _get_available_instruments(self):
        """Get available instruments resource content."""
        try:
            instruments = await self.tools.list_instruments()
            return json.dumps(instruments, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error getting available instruments: {e}")
            return json.dumps({"error": str(e), "status": "error"}, indent=2)

    async def _get_station_state(self):
        """Get station state resource content."""
        try:
            snapshot = await self.tools.get_station_snapshot()
            return json.dumps(snapshot, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error getting station state: {e}")
            return json.dumps({"error": str(e), "status": "error"}, indent=2)

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
                    contents=[
                        TextResourceContents(
                            uri="resource://available_instruments",
                            mimeType="application/json",
                            text=content,
                        )
                    ],
                )
            except Exception as e:
                logger.error(f"Error generating available_instruments resource: {e}")
                error_content = json.dumps(
                    {"error": str(e), "status": "error"}, indent=2
                )
                return Resource(
                    uri="resource://available_instruments",
                    name="Available Instruments (Error)",
                    description="Error retrieving available instruments",
                    mimeType="application/json",
                    contents=[
                        TextResourceContents(
                            uri="resource://available_instruments",
                            mimeType="application/json",
                            text=error_content,
                        )
                    ],
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
                    contents=[
                        TextResourceContents(
                            uri="resource://station_state",
                            mimeType="application/json",
                            text=content,
                        )
                    ],
                )
            except Exception as e:
                logger.error(f"Error generating station_state resource: {e}")
                error_content = json.dumps(
                    {"error": str(e), "status": "error"}, indent=2
                )
                return Resource(
                    uri="resource://station_state",
                    name="Station State (Error)",
                    description="Error retrieving station state",
                    mimeType="application/json",
                    contents=[
                        TextResourceContents(
                            uri="resource://station_state",
                            mimeType="application/json",
                            text=error_content,
                        )
                    ],
                )

    def _register_measureit_resources(self):
        """Register MeasureIt template resources."""

        # Import MeasureIt template functions
        from ....extensions.measureit import (
            get_sweep0d_template,
            get_sweep1d_template,
            get_sweep2d_template,
            get_simulsweep_template,
            get_sweepqueue_template,
            get_common_patterns_template,
            get_measureit_code_examples,
        )

        templates = [
            (
                "measureit_sweep0d_template",
                "MeasureIt Sweep0D Template",
                "Sweep0D code examples and patterns for time-based monitoring",
                get_sweep0d_template,
            ),
            (
                "measureit_sweep1d_template",
                "MeasureIt Sweep1D Template",
                "Sweep1D code examples and patterns for single parameter sweeps",
                get_sweep1d_template,
            ),
            (
                "measureit_sweep2d_template",
                "MeasureIt Sweep2D Template",
                "Sweep2D code examples and patterns for 2D parameter mapping",
                get_sweep2d_template,
            ),
            (
                "measureit_simulsweep_template",
                "MeasureIt SimulSweep Template",
                "SimulSweep code examples for simultaneous parameter sweeping",
                get_simulsweep_template,
            ),
            (
                "measureit_sweepqueue_template",
                "MeasureIt SweepQueue Template",
                "SweepQueue code examples for sequential measurement workflows",
                get_sweepqueue_template,
            ),
            (
                "measureit_common_patterns",
                "MeasureIt Common Patterns",
                "Common MeasureIt patterns and best practices",
                get_common_patterns_template,
            ),
            (
                "measureit_code_examples",
                "MeasureIt Code Examples",
                "Complete collection of ALL MeasureIt patterns in structured format",
                get_measureit_code_examples,
            ),
        ]

        for uri_suffix, name, description, get_content_func in templates:
            self._register_template_resource(
                uri_suffix, name, description, get_content_func
            )

    def _register_template_resource(
        self, uri_suffix, name, description, get_content_func
    ):
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
                contents=[
                    TextResourceContents(
                        uri=uri, mimeType="application/json", text=content
                    )
                ],
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
                contents=[
                    TextResourceContents(
                        uri="resource://database_config",
                        mimeType="application/json",
                        text=content,
                    )
                ],
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
                contents=[
                    TextResourceContents(
                        uri="resource://recent_measurements",
                        mimeType="application/json",
                        text=content,
                    )
                ],
            )
