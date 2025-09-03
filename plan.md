# qcodes-mcp-server — Implementation Plan

## Goal
Expose a remote **MCP** server (Streamable HTTP transport) that:
- Boots a **QCoDeS Station** from YAML configuration
- Publishes a **resource**: `available_instr` (JSON list of instruments present/loaded)
- Exposes **tools**:
  - `all_instr_health(update: bool = false)` → station snapshot (optionally live-update)
  - `inst_health(name: str, update: bool = true)` → single-instrument snapshot
  - Backward-compat alias: `inst_healtn` → `inst_health` (typo-tolerant)

## Architecture Overview

### Transport
- Use **FastMCP** with `transport="http"` (Streamable HTTP) on path `/mcp`
- This is the recommended remote deployment transport and supports streaming
- Server binds to `HOST:PORT/mcp` endpoint

### Station Bootstrap
- Station initialized in separate module `station_init.py`:
  - Load `config/station.station.yaml` using `Station.load_config_files(...)`
  - Optionally merge multiple YAML files
  - Instruments are **declared** in YAML; actual device objects created lazily via `station.load_instrument(name)`
- On server start:
  - Load YAML into a Station instance
  - Eagerly instantiate configured subset (env var `QMS_AUTOLOAD` = comma-separated names), or none by default
  - Write `state/available_instr.json` with instrument names present in `station.components` after autoload

### Resources
- `available_instr` → file-backed JSON resource: `state/available_instr.json`
- Auto-generated at server startup, contains list of available/loaded instruments

### Tools
- `all_instr_health(update: bool = false)`:
  - Return `station.snapshot(update=update)` (recursive dict of all components)
  - `update=false` by default for performance (avoids slow hardware reads)
- `inst_health(name: str, update: bool = true)`:
  - Resolve component by name from station
  - Call the object's `snapshot(update=update)` method
  - Instruments and parameters implement `snapshot`/`snapshot_base` methods
- Alias `inst_healtn` → `inst_health` for typo tolerance

### Snapshot Considerations
- `update=true` may touch hardware and be slow; default `false` for station-wide calls
- Can pass `params_to_skip_update` at driver level to avoid slow parameter reads
- Snapshot format is standardized QCoDeS JSON structure

## Configuration & Environment Variables

### Environment Variables
- `STATION_YAML=./config/station.station.yaml` - Main station configuration
- `DRIVERS_YAML=./config/drivers.yaml` - Optional driver registry map
- `STATE_DIR=./state` - Directory for runtime state files
- `HOST=0.0.0.0` - Server host binding
- `PORT=8000` - Server port
- `MCP_PATH=/mcp` - MCP endpoint path
- `QMS_AUTOLOAD=` - Comma-separated list of instruments to autoload on startup

### Configuration Files

#### `config/station.station.yaml`
Standard QCoDeS Station YAML format:
```yaml
instruments:
  mock_dac:
    driver: qcodes.instrument_drivers.mock.MockDAC
    name: mock_dac_1
    parameters:
      voltage_limit: 10.0
  
  keithley_2400:
    driver: qcodes.instrument_drivers.Keithley.keithley_2400.Keithley2400
    name: k2400
    address: GPIB0::24::INSTR
    enable: false  # Disabled by default for safety
```

#### `config/drivers.yaml` (Optional)
Custom driver registry for mapping names to classes:
```yaml
drivers:
  mock_dac: qcodes.instrument_drivers.mock.MockDAC
  keithley_2400: qcodes.instrument_drivers.Keithley.keithley_2400.Keithley2400
  sr830: qcodes.instrument_drivers.stanford_research.SR830.SR830
```

## Context7 Integration
- When implementing QCoDeS-specific behaviors (YAML semantics, snapshot quirks), **query the "Context7" MCP tool** to retrieve relevant QCoDeS docs/examples
- Keep thin wrapper in `tools/context7_client.py` for Context7 MCP server communication
- Use Context7 for understanding Station configuration patterns and snapshot method behaviors

## Security & Safety
- Start with **read-only** tools (`snapshot` only) - no parameter setting or measurement execution
- Add allowlist mechanism before enabling mutating tools (setters/sweeps)
- Rate-limiting and timeouts on snapshot updates per instrument
- Log every MCP request + response hash to `state/logs/`
- Validate YAML configuration on load to prevent malicious instrument instantiation

## Error Handling & Robustness
- Graceful handling of instrument connection failures during autoload
- Timeout protection for slow snapshot operations
- Detailed error reporting in tool responses
- Fallback behavior when instruments are unreachable
- State file corruption recovery

## Testing Strategy
- Use dummy/mock instruments (QCoDeS mock drivers) in CI tests
- Verify station loads correctly from YAML
- Test resource enumeration of instruments
- Validate tools return JSON-serializable snapshots
- Integration tests with actual FastMCP HTTP transport
- Performance tests for large station snapshots

## Implementation Milestones

### M0: Server Skeleton + HTTP Transport + Resources
**Deliverables:**
- FastMCP server with Streamable HTTP transport on `/mcp`
- Basic directory structure (servers/, config/, state/, tools/)
- `available_instr` resource serving static JSON
- Health check endpoint

**Success Criteria:**
- Server starts and responds to MCP discovery requests
- `available_instr` resource accessible via MCP client
- HTTP transport working on specified host:port/mcp

### M1: Station YAML Loader + Health Tools
**Deliverables:**
- `station_init.py` module with Station YAML loading
- `all_instr_health` and `inst_health` MCP tools
- Environment variable configuration system
- Autoload functionality with `QMS_AUTOLOAD`

**Success Criteria:**
- Station loads from YAML configuration
- Mock instruments can be autoloaded and health-checked
- Snapshot data returns valid JSON through MCP tools
- `state/available_instr.json` generated correctly

### M2: Robust Error Handling + Logging + Tests
**Deliverables:**
- Comprehensive error handling for all failure modes
- Request/response logging system
- Timeout protection for slow operations
- Full test suite with mock instruments
- Performance monitoring and optimization

**Success Criteria:**
- Server handles instrument failures gracefully
- All operations have reasonable timeouts
- Test coverage >90% for core functionality
- Performance benchmarks established

### M3: Packaging + Examples + Deployment Documentation
**Deliverables:**
- `pyproject.toml` for modern Python packaging
- Example configurations for common instruments
- Deployment guides (systemd, containers, cloud)
- Integration examples with Context7
- Production hardening (logging, monitoring)

**Success Criteria:**
- Package installable via pip
- Complete deployment documentation
- Production-ready configuration examples
- Integration with external MCP servers demonstrated

## Directory Structure (Final)
```
instrMCP/
├── plan.md                      # This implementation plan
├── README.md                    # User documentation
├── pyproject.toml               # Modern Python packaging metadata
├── requirements.txt             # Core dependencies
├── .env.example                 # Environment variable template
├── servers/                     # MCP server implementations
│   ├── qcodes/
│   │   ├── server.py           # FastMCP server (Streamable HTTP)
│   │   ├── station_init.py     # Station bootstrapper (YAML-driven)
│   │   └── __init__.py
│   ├── redpitaya/              # Future: RedPitaya MCP server
│   │   ├── server.py           # FastMCP server wrapping pyrpl
│   │   └── __init__.py
│   └── labassist/              # Future: Misc lab helpers
│       ├── server.py
│       └── __init__.py
├── config/                      # Configuration files
│   ├── station.station.yaml    # QCoDeS Station YAML (example)
│   ├── drivers.yaml            # Optional driver registry map
│   └── qcodes.ini              # Optional QCoDeS global config
├── state/                       # Runtime state and data
│   ├── available_instr.json    # Generated at server start
│   ├── logs/                   # Request/response logs
│   └── snapshots/              # On-demand JSON snapshot dumps
├── tests/                       # Test suite
│   ├── test_qcodes_server.py   # Server functionality tests
│   ├── test_station_init.py    # Station loading tests
│   ├── conftest.py             # Pytest configuration
│   └── __init__.py
└── tools/                       # Helper utilities
    ├── context7_client.py      # Thin MCP client wrapper to call Context7
    └── __init__.py
```

## Development Workflow
1. **Setup**: Use provided `.env.example` to configure environment
2. **Configuration**: Customize `config/station.station.yaml` for your lab setup
3. **Development**: Use mock instruments for rapid iteration
4. **Testing**: Run comprehensive test suite before deployment
5. **Deployment**: Follow M3 deployment guides for production setup

## Future Extensions
- Multi-station support for distributed lab setups
- Real-time measurement streaming capabilities
- Integration with electronic lab notebooks
- Web dashboard for station monitoring
- Advanced security with authentication/authorization