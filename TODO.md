# MeasureIt Integration TODO

## Core Concept
Instead of direct MeasureIt object manipulation, provide intelligent code generation through resources and templates that the AI uses to write measurement code in Jupyter cells.

**IMPORTANT**: All MeasureIt resources and tools are OPTIONAL and only activated when user enables them with `%mcp_option measureit`. This ensures the core functionality remains lightweight while providing advanced measurement capabilities when needed.

## Phase 1: MeasureIt Code Template Resources (Optional - requires `%mcp_option measureit`)

### 1.1 Measurement Template Resources
- [x] Create `measureit_sweep0d_template` resource with Sweep0D code examples and patterns
- [x] Create `measureit_sweep1d_template` resource with Sweep1D code examples
- [x] Create `measureit_sweep2d_template` resource with Sweep2D code examples
- [x] Create `measureit_simulsweep_template` resource with SimulSweep examples
- [x] Create `measureit_sweepqueue_template` resource with SweepQueue patterns
- [x] Create `measureit_common_patterns` resource with common measurement workflows

### 1.2 Dynamic Template Resource
- [x] Create `measureit_code_examples` resource that returns ALL available MeasureIt patterns in a structured format

## Phase 2: Database Integration

### 2.1 Database Query Tools
- [x] Create `list_experiments` tool - List all experiments in current QCodes database
- [x] Create `query_datasets` tool - Query datasets with optional filters (experiment, sample, date range, run ID)
- [x] Create `get_dataset_info` tool - Get detailed information about a specific dataset
- [x] Create `get_database_stats` tool - Get database statistics and health information
- [x] ~~Create `suggest_database_setup` tool~~ - Deleted (users can write basic database setup code themselves)
- [x] ~~Create `suggest_measurement_from_history` tool~~ - Deleted (overly complex with limited practical use)

### 2.2 Database Resources
- [x] Create `database_config` resource - Current QCodes database configuration, path, and connection status
- [x] Create `recent_measurements` resource - Metadata for recent measurements across all experiments
- [x] Create `measurement_templates` resource - Common measurement patterns and templates extracted from historical data

### 2.3 Integration Completed
- [x] Added database integration to mcp_server.py with conditional registration
- [x] Updated magic commands to support `%mcp_option add database`
- [x] Updated README.md with database integration documentation

### 2.4 ✅ Database Tools Rewrite - COMPLETED
**Status**: Database functionality completely rewritten and working

#### Issues Fixed:
- [x] **Completely Rewritten query_tools.py**: Used proper QCodes API patterns from databaseExample.ipynb
  - Fixed `list_experiments()` to properly iterate over run IDs and match to experiments
  - Rewritten `query_datasets()` to use `load_by_id()` and properly extract MeasureIt metadata
  - Enhanced `get_dataset_info()` to include parameter data and MeasureIt sweep configuration
  - Improved `get_database_stats()` with measurement type analysis

- [x] **Deleted Unnecessary Code Generators**: Removed overly complex, low-value functions
  - Deleted entire `code_generators.py` file

- [x] **Simplified db_resources.py**: Kept only useful resources
  - Kept `get_current_database_config()` - basic database connection info
  - Enhanced `get_recent_measurements()` with MeasureIt metadata extraction
  - Deleted `get_measurement_templates()` - overly complex analysis with limited value

#### Streamlined Architecture:
- [x] **4 Core Query Tools**: `list_experiments`, `query_datasets`, `get_dataset_info`, `get_database_stats`
- [x] **2 Simple Resources**: `database_config`, `recent_measurements`
- [x] **Updated __init__.py**: Removed imports for deleted functions
- [x] **Updated mcp_server.py**: Removed tool registrations for deleted functions

#### Key Improvements:
- Based on actual QCodes usage patterns from databaseExample.ipynb
- Proper use of `load_by_id()`, `dataset.get_parameter_data()`, `dataset.metadata['measureit']`
- Extract MeasureIt sweep configurations (Sweep0D/1D/2D/SimulSweep) from metadata
- Return limited parameter data to avoid huge responses
- Focus on direct database queries rather than generic code generation

#### Priority: **COMPLETED** - All database tools now functional and streamlined

## Phase 3: Enhanced Jupyter Integration (Optional - requires `%mcp_option measureit`)

### 3.1 Workflow Tools
- [ ] Create `get_measureit_status` tool - check if any MeasureIt sweep is currently running

## Phase 4: Implementation Architecture

### 4.1 File Structure
```
instrmcp/servers/jupyter_qcodes/
├── measureit_integration.py   # Main integration module
├── measureit_templates.py      # Code template definitions
└── measureit_helpers.py        # Helper functions

instrmcp/config/data/
├── measureit_examples/
│   ├── sweep0d_examples.py
│   ├── sweep1d_examples.py
│   ├── sweep2d_examples.py
│   └── common_patterns.py
└── measureit_config.yaml
```

### 4.2 Tool Prompting Strategy
- [ ] Add prompts that guide the AI:
  - "When user asks for measurements, use this to generate appropriate MeasureIt code"
  - "Always suggest using MeasureIt for parameter sweeping instead of manual loops"
  - "Include proper database initialization in suggested code"

## Phase 5: Example Implementation

### 5.1 Example Workflow to Support:
1. User asks: "I want to measure lockin signal vs gate voltage from -1V to 1V"
2. AI calls `suggest_measurement_code`
3. AI uses `update_editing_cell` to write generated code
4. User reviews and executes

### 5.2 Generated Code Template:
```python
# MeasureIt Sweep1D Measurement
import os
from MeasureIt.sweep1d import Sweep1D
from MeasureIt.util import init_database

# Configure sweep
s = Sweep1D(gate.voltage, start=-1, stop=1, rate=0.01,
           inter_delay=0.1, save_data=True, bidirectional=True)

# Set parameters to follow
s.follow_param(lockin.x, lockin.y, lockin.r)

# Initialize database
database_name = "measurements.db"
exp_name = "gate_sweep"
sample_name = "sample_001"
init_database(database_name, exp_name, sample_name, s)

# Start measurement
%matplotlib qt
s.start()
```

## Phase 6: Documentation

### 6.1 Update CLAUDE.md
- [ ] Add section: "MeasureIt Integration - Code Generation Approach"
- [ ] Document the template-based workflow
- [ ] Include examples of AI-generated measurement code

### 6.2 Resource Documentation
- [ ] Document each template resource with comprehensive examples
- [ ] Add clear documentation of parameter meanings
- [ ] Include common pitfalls and solutions

## Phase 7: Testing

- [ ] Human will test. No automated tests for AI-generated code.

## Phase 8: Code Architecture Refactoring (Performance & Maintainability)

### 8.1 Problem Identified
- [x] `mcp_server.py` has grown to **973 lines** - becoming difficult to maintain
- [x] Mixing concerns: core tools, optional features, resources, server management
- [x] Difficult to test individual components in isolation
- [x] Hard to add new features without making the file even larger

### 8.2 Proposed Modular Architecture
- [ ] **Refactor into modular structure:**
```
instrmcp/servers/jupyter_qcodes/
├── mcp_server.py              # Main server class (simplified ~200 lines)
├── tools/
│   ├── __init__.py
│   ├── core.py               # Core QCodes/Jupyter tools (~250 lines)
│   ├── unsafe.py             # Unsafe execution tools (~50 lines)
│   └── database.py           # Database integration tools (~200 lines)
├── resources/
│   ├── __init__.py
│   ├── core.py               # Core resources (~100 lines)
│   ├── measureit.py          # MeasureIt template resources (~150 lines)
│   └── database.py           # Database resources (~100 lines)
└── registrars/
    ├── __init__.py
    ├── tool_registrar.py      # Tool registration helper
    └── resource_registrar.py  # Resource registration helper
```

### 8.3 Implementation Steps
- [ ] Create directory structure (`tools/`, `resources/`, `registrars/`)
- [ ] Move core tools to `tools/core.py` with registration functions
- [ ] Move unsafe tools to `tools/unsafe.py`
- [ ] Move database tools to `tools/database.py`
- [ ] Move core resources to `resources/core.py`
- [ ] Move MeasureIt resources to `resources/measureit.py`
- [ ] Move database resources to `resources/database.py`
- [ ] Create registrar pattern classes for clean tool/resource registration
- [ ] Simplify main `mcp_server.py` to use registrars (target: ~200-250 lines)
- [ ] Test each component works correctly
- [ ] Update imports in other files if needed

### 8.4 Benefits of Refactoring
- **Better Organization**: Each file has a single responsibility
- **Easier Testing**: Can test tool/resource modules independently
- **Improved Maintainability**: Finding and modifying specific tools is straightforward
- **Scalability**: Adding new optional features doesn't bloat the main file
- **Clear Dependencies**: Optional imports only when features are enabled
- **Team Collaboration**: Multiple developers can work on different modules

### 8.5 Success Criteria
- [ ] `mcp_server.py` reduced to ~200-250 lines
- [ ] All tools and resources continue to work correctly
- [ ] Optional features (measureit, database) still properly conditional
- [ ] Code organization makes it easy to add future features
- [ ] Individual modules can be tested in isolation


## Key Design Principles:
- **Transparency**: User sees exact code before execution
- **Safety**: No direct measurement control by AI
- **Education**: User learns MeasureIt patterns
- **Flexibility**: User can modify suggested code
- **Simplicity**: Fewer complex tools, more template resources
- **Integration**: Works with existing Jupyter cell editing tools

## Implementation Notes:
- **Optional Feature**: All MeasureIt functionality is behind `%mcp_option measureit` flag
- **Environment**: Consider MeasureItHome environment variable handling
- **Compatibility**: Ensure compatibility with existing QCoDeS instruments
- **Safety**: Think about safe mode vs unsafe mode implications
- **Long-running**: Consider how to handle long-running measurements
- **Plotting**: Think about real-time plot integration