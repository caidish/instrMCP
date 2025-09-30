InstrMCP Documentation
======================

.. image:: https://img.shields.io/badge/python-3.8+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.8+

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

.. image:: https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg
   :target: https://github.com/anthropics/mcp
   :alt: MCP

Welcome to InstrMCP
-------------------

InstrMCP is an MCP server suite for quantum device physics laboratory instrumentation control, enabling Large Language Models to interact directly with physics instruments and measurement systems through QCodes and JupyterLab.

Features
--------

- **Full QCodes Integration**: Built-in support for all QCodes instrument drivers
- **Database Integration**: Read-only access to QCodes databases with intelligent code generation
- **MeasureIt Templates**: Comprehensive measurement pattern library and code generation
- **JupyterLab Native**: Seamless integration with JupyterLab
- **Safe Mode**: Read-only mode with optional unsafe execution
- **CLI**: Easy server management with ``instrmcp`` command
- **MCP**: Standard Model Context Protocol for LLM integration
- Tested with Claude Desktop, Claude Code, and Codex CLI

Quick Links
-----------

* **GitHub Repository**: https://github.com/caidish/instrMCP
* **PyPI Package**: Coming soon
* **Issue Tracker**: https://github.com/caidish/instrMCP/issues

Documentation Contents
----------------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   architecture
   mcp_tools
   jupyter_integration
   database_integration
   measureit_integration

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index

.. toctree::
   :maxdepth: 1
   :caption: Development

   changelog
   contributing
   license

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`