"""InstrMCP App / Launcher.

A product-grade launcher around the kernel-hosted MCP server. Provides:

- Profile-based configuration (``instrmcp/app/profiles.py``)
- A doctor / health-check report (``instrmcp/app/doctor.py``)
- An auto-loading ``instrmcp`` Jupyter kernelspec (``instrmcp/app/install_kernel.py``)
- A supervisor that launches JupyterLab and observes runtime health
  (``instrmcp/app/supervisor.py``, added in Milestone 2)
- A static webapp served by the supervisor (``instrmcp/app/webapp/``)

The supervisor is an *observer + orchestrator*: it never imports or owns the
kernel-hosted :class:`JupyterMCPServer`. The MCP server starts automatically when a
notebook opens on the ``instrmcp`` kernel (whose ``kernel.json`` runs ``%mcp_start``).
"""

from __future__ import annotations

from instrmcp.app.profiles import Profile, load_profile, list_profiles, validate_profile

__all__ = [
    "Profile",
    "load_profile",
    "list_profiles",
    "validate_profile",
]
