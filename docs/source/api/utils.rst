Utils
=====

This module contains internal utilities and helpers.

STDIO Proxy
-----------

.. automodule:: instrmcp.utils.stdio_proxy
   :members:
   :undoc-members:
   :show-inheritance:

Key Functions
~~~~~~~~~~~~~

check_http_mcp_server
^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: instrmcp.utils.stdio_proxy.check_http_mcp_server

create_stdio_proxy_server
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: instrmcp.utils.stdio_proxy.create_stdio_proxy_server

   Creates a FastMCP proxy server that forwards STDIO to an HTTP backend.
   Uses FastMCP's built-in ``as_proxy()`` pattern for automatic tool and
   resource mirroring with full description forwarding.

   **Example usage**:

   .. code-block:: python

      mcp = create_stdio_proxy_server(
          base_url="http://127.0.0.1:8123",
          server_name="InstrMCP Proxy"
      )
      mcp.run()
