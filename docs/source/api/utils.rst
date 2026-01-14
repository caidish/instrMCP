Utils
=====

This module contains internal utilities and helpers.

STDIO Proxy
-----------

.. automodule:: instrmcp.utils.stdio_proxy
   :members:
   :undoc-members:
   :show-inheritance:

Key Classes
~~~~~~~~~~~

HttpMCPProxy
^^^^^^^^^^^^

.. autoclass:: instrmcp.utils.stdio_proxy.HttpMCPProxy
   :members:
   :undoc-members:
   :show-inheritance:

   The HTTP MCP proxy enables STDIO-based MCP clients (like Claude Desktop)
   to communicate with HTTP-based MCP servers.

   **Example usage**:

   .. code-block:: python

      proxy = HttpMCPProxy("http://127.0.0.1:8123")
      result = await proxy.call("qcodes/instrument_info", name="lockin")

Key Functions
~~~~~~~~~~~~~

check_http_mcp_server
^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: instrmcp.utils.stdio_proxy.check_http_mcp_server

create_stdio_proxy_server
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: instrmcp.utils.stdio_proxy.create_stdio_proxy_server

   Creates a FastMCP server that proxies STDIO to HTTP.

   **Example usage**:

   .. code-block:: python

      mcp = create_stdio_proxy_server(
          base_url="http://127.0.0.1:8123",
          server_name="InstrMCP Proxy"
      )
      mcp.run()