"""Guard the resource-override application path (fastmcp 4 API).

fastmcp 4 removed `FastMCP.get_resources()`; the override path has to use
`list_resources()` (a sequence) instead. This was silently failing behind a
try/except until the migration was verified against a live server, so it gets a
focused regression test: with the old call the fake raises AttributeError, the
warning path leaves the resource untouched, and the assertions fail.
"""

from types import SimpleNamespace

from instrmcp.servers.jupyter_qcodes.mcp_server import JupyterMCPServer
from instrmcp.utils.metadata_config import MetadataConfig, ResourceOverride


class FakeMCP:
    """Minimal FastMCP stand-in exposing only the fastmcp 4 resource API."""

    def __init__(self, resources):
        self._resources = resources
        self.calls = 0

    async def list_resources(self):
        self.calls += 1
        return self._resources


def make_server(resources):
    server = object.__new__(JupyterMCPServer)
    server.mcp = FakeMCP(resources)
    return server


def test_resource_override_is_applied_via_list_resources():
    resource = SimpleNamespace(
        uri="resource://known", name="Old name", description="old description"
    )
    server = make_server([resource])
    config = MetadataConfig(
        resources={
            "resource://known": ResourceOverride(
                name="Known resource", description="new description"
            )
        }
    )

    server._apply_resource_overrides(config)

    assert server.mcp.calls == 1
    assert resource.name == "Known resource"
    assert resource.description == "new description"


def test_unknown_resource_is_skipped_without_raising():
    resource = SimpleNamespace(
        uri="resource://known", name="Old name", description="old description"
    )
    server = make_server([resource])
    config = MetadataConfig(
        resources={"resource://elsewhere": ResourceOverride(name="Nowhere")}
    )

    server._apply_resource_overrides(config)

    assert resource.name == "Old name"
    assert resource.description == "old description"
