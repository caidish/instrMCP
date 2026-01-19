"""
MCP client utilities for Playwright E2E tests.
"""

from .mcp_metadata_client import (
    MCPMetadataClient,
    build_metadata_snapshot,
    compare_metadata,
    load_snapshot,
    save_snapshot,
)

__all__ = [
    "MCPMetadataClient",
    "build_metadata_snapshot",
    "compare_metadata",
    "load_snapshot",
    "save_snapshot",
]
