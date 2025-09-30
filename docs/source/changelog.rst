Changelog
=========

All notable changes to InstrMCP will be documented in this file.

Version 1.0.0 (2025-01-XX)
--------------------------

**Major Release**: First stable release

Added
~~~~~

- Complete MCP server implementation for QCodes instruments
- JupyterLab extension for active cell bridging
- Safe/unsafe mode switching
- Database integration for measurement history
- MeasureIt template library
- Comprehensive tool set:
  - Notebook inspection tools
  - QCodes instrument tools
  - Cell manipulation tools (unsafe mode)
  - Database query tools
  - MeasureIt status monitoring
- MCP resources for instruments, templates, and measurements
- Magic commands for server control
- STDIO proxy for Claude Desktop/Code/Codex integration
- Cursor movement between cells
- Batch parameter reading
- Real-time cell output capture

Changed
~~~~~~~

- Improved performance by removing unnecessary wait loops
- Updated to MCP protocol 2024-11-05
- Enhanced error handling across all tools
- Better comm protocol reliability

Fixed
~~~~~

- Cell content synchronization issues
- Extension loading in JupyterLab 4.x
- Parameter caching edge cases
- Comm connection stability

Documentation
~~~~~~~~~~~~~

- Complete Sphinx documentation
- ReadTheDocs integration
- API reference
- User guides and tutorials
- Architecture documentation

Version 0.3.0 (2024-12-XX)
--------------------------

**Beta Release**: Database and MeasureIt integration

Added
~~~~~

- Database integration tools
- MeasureIt template resources
- Optional feature system (``%mcp_option``)
- Template-based code generation
- Measurement history access

Changed
~~~~~~~

- Modularized tool registration
- Improved resource management
- Better error messages

Version 0.2.0 (2024-11-XX)
--------------------------

**Alpha Release**: Extended toolset

Added
~~~~~

- Cell manipulation tools
- Unsafe mode support
- Active cell bridging via JupyterLab extension
- Comm protocol implementation
- Cursor movement
- Cell addition/deletion

Changed
~~~~~~~

- Refactored server architecture
- Enhanced safety model
- Improved Jupyter integration

Version 0.1.0 (2024-10-XX)
--------------------------

**Initial Release**: Core functionality

Added
~~~~~

- Basic MCP server
- QCodes instrument access
- Read-only notebook inspection
- Magic commands
- STDIO proxy
- Claude Desktop integration

Features
~~~~~~~~

- Instrument parameter reading
- Variable inspection
- Basic cell access

Known Issues
~~~~~~~~~~~~

- Limited error handling
- No cell manipulation
- Basic feature set

Future Plans
------------

Version 1.1.0 (Planned)
~~~~~~~~~~~~~~~~~~~~~~~

- RedPitaya instrument support
- Raspberry Pi integration for legacy instruments
- Lab wiki knowledge base integration
- Enhanced safety rails
- Additional LLM client examples

Version 1.2.0 (Planned)
~~~~~~~~~~~~~~~~~~~~~~~

- WebSocket support for real-time updates
- Enhanced plotting integration
- Automated measurement workflows
- Advanced pattern recognition
- Multi-user support

Long-term Roadmap
~~~~~~~~~~~~~~~~~

- Hardware trigger integration
- Real-time data streaming
- Advanced analysis tools
- Machine learning integration
- Cloud deployment options

Contributing
------------

We welcome contributions! See :doc:`contributing` for guidelines.

To report bugs or request features:
https://github.com/caidish/instrMCP/issues