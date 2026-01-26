"""
Resource registrar for MCP server.

Registers all MCP resources (core, MeasureIt templates, and database resources).
Resource descriptions are loaded from metadata_baseline.yaml.
"""

import asyncio
import json
import logging
from typing import Tuple

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
        metadata_config=None,
    ):
        """
        Initialize the resource registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
            enabled_options: Set of enabled optional features
            measureit_module: MeasureIt integration module (optional)
            db_module: Database integration module (optional)
            metadata_config: MetadataConfig instance for resource descriptions
        """
        self.mcp = mcp_server
        self.tools = tools
        self.enabled_options = enabled_options or set()
        self.measureit = measureit_module
        self.db = db_module
        self.metadata_config = metadata_config

    def _get_resource_metadata(
        self, uri: str, default_name: str = "resource", default_desc: str = ""
    ) -> Tuple[str, str]:
        """Look up resource name and description from metadata config.

        Args:
            uri: Resource URI (e.g., "resource://measureit_sweep1d_template")
            default_name: Fallback name if not in config
            default_desc: Fallback description if not in config

        Returns:
            Tuple of (name, description). Falls back to defaults if not in config.
        """
        if not self.metadata_config:
            return default_name, default_desc

        # Check resources section first
        if uri in self.metadata_config.resources:
            override = self.metadata_config.resources[uri]
            return (
                override.name or default_name,
                override.compose_description() or default_desc,
            )

        # Check resource_templates section
        if uri in self.metadata_config.resource_templates:
            override = self.metadata_config.resource_templates[uri]
            return (
                override.name or default_name,
                override.compose_description() or default_desc,
            )

        return default_name, default_desc

    def register_all(self):
        """Register all resources."""
        self._register_resource_guide_tool()
        self._register_core_resources()

        if "measureit" in self.enabled_options and self.measureit:
            self._register_measureit_resources()

    def _register_resource_guide_tool(self):
        """Register tools to help models discover and use MCP resources."""
        from mcp.types import TextContent

        @self.mcp.tool(
            name="mcp_list_resources",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def list_resources(detailed: bool = False):
            # Description loaded from metadata_baseline.yaml
            # detailed parameter reserved for future use
            _ = detailed
            # Dynamically query registered resources to reflect metadata overrides
            try:
                registered = await self.mcp.get_resources()
            except Exception as e:
                logger.error(f"Failed to get registered resources: {e}")
                registered = {}

            # Build list of available resources from registered resources
            resources_list = []
            for uri, resource in registered.items():
                entry = {
                    "uri": str(uri),
                    "name": getattr(resource, "name", None) or str(uri),
                    "description": getattr(resource, "description", None),
                }
                resources_list.append(entry)

            # Sort by URI for consistent ordering
            resources_list.sort(key=lambda x: x["uri"])

            # Build guidance
            guide = {
                "total_resources": len(resources_list),
                "resources": resources_list,
            }

            return [TextContent(type="text", text=json.dumps(guide, indent=2))]

        @self.mcp.tool(
            name="mcp_get_resource",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_resource(uri: str):
            # Description loaded from metadata_baseline.yaml
            # Map URIs to resource handlers
            resource_map = {}

            # Add MeasureIt resources if enabled
            if "measureit" in self.enabled_options:
                from ..options.measureit import (
                    get_sweep0d_template,
                    get_sweep1d_template,
                    get_sweep2d_template,
                    get_simulsweep_template,
                    get_sweepqueue_template,
                    get_common_patterns_template,
                    get_measureit_code_examples,
                    # Data access templates
                    get_database_access0d_template,
                    get_database_access1d_template,
                    get_database_access2d_template,
                    get_database_access_simulsweep_template,
                    get_database_access_sweepqueue_template,
                )

                resource_map.update(
                    {
                        # Sweep templates (for running measurements)
                        "resource://measureit_sweep0d_template": lambda: get_sweep0d_template(),
                        "resource://measureit_sweep1d_template": lambda: get_sweep1d_template(),
                        "resource://measureit_sweep2d_template": lambda: get_sweep2d_template(),
                        "resource://measureit_simulsweep_template": lambda: get_simulsweep_template(),
                        "resource://measureit_sweepqueue_template": lambda: get_sweepqueue_template(),
                        "resource://measureit_common_patterns": lambda: get_common_patterns_template(),
                        "resource://measureit_code_examples": lambda: get_measureit_code_examples(),
                        # Data access templates (for loading saved data)
                        "resource://database_access0d_template": lambda: get_database_access0d_template(),
                        "resource://database_access1d_template": lambda: get_database_access1d_template(),
                        "resource://database_access2d_template": lambda: get_database_access2d_template(),
                        "resource://database_access_simulsweep_template": lambda: get_database_access_simulsweep_template(),
                        "resource://database_access_sweepqueue_template": lambda: get_database_access_sweepqueue_template(),
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

    def _register_core_resources(self):
        """Register core QCodes and notebook resources."""
        # No core resources registered.

    def _register_measureit_resources(self):
        """Register MeasureIt template resources.

        Name and description loaded from metadata_baseline.yaml.
        """
        # Import MeasureIt template functions
        from ..options.measureit import (
            get_sweep0d_template,
            get_sweep1d_template,
            get_sweep2d_template,
            get_simulsweep_template,
            get_sweepqueue_template,
            get_common_patterns_template,
            get_measureit_code_examples,
            # Data access templates
            get_database_access0d_template,
            get_database_access1d_template,
            get_database_access2d_template,
            get_database_access_simulsweep_template,
            get_database_access_sweepqueue_template,
        )

        # Map URI suffix to content function - name/description from config
        templates = [
            # Sweep templates (for running measurements)
            ("measureit_sweep0d_template", get_sweep0d_template),
            ("measureit_sweep1d_template", get_sweep1d_template),
            ("measureit_sweep2d_template", get_sweep2d_template),
            ("measureit_simulsweep_template", get_simulsweep_template),
            ("measureit_sweepqueue_template", get_sweepqueue_template),
            ("measureit_common_patterns", get_common_patterns_template),
            ("measureit_code_examples", get_measureit_code_examples),
            # Data access templates (for loading saved data from database)
            ("database_access0d_template", get_database_access0d_template),
            ("database_access1d_template", get_database_access1d_template),
            ("database_access2d_template", get_database_access2d_template),
            (
                "database_access_simulsweep_template",
                get_database_access_simulsweep_template,
            ),
            (
                "database_access_sweepqueue_template",
                get_database_access_sweepqueue_template,
            ),
        ]

        for uri_suffix, get_content_func in templates:
            self._register_template_resource(uri_suffix, get_content_func)

    def _register_template_resource(self, uri_suffix, get_content_func):
        """Helper to register a template resource.

        Name and description loaded from metadata_baseline.yaml.
        """
        uri = f"resource://{uri_suffix}"

        # Look up metadata from config (with fallback to uri_suffix as name)
        name, description = self._get_resource_metadata(
            uri,
            default_name=uri_suffix,
            default_desc=f"Template resource: {uri_suffix}",
        )

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
