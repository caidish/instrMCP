# MeasureIt Integration TODO

## Core Concept
Instead of direct MeasureIt object manipulation, provide intelligent code generation through resources and templates that the AI uses to write measurement code in Jupyter cells.

**IMPORTANT**: All MeasureIt resources and tools are OPTIONAL and only activated when user enables them with `%mcp_option measureit`. This ensures the core functionality remains lightweight while providing advanced measurement capabilities when needed.

## Phase 1: MeasureIt Code Template Resources (Optional - requires `%mcp_option measureit`)

### 1.1 Measurement Template Resources
- [ ] Create `measureit_sweep0d_template` resource with Sweep0D code examples and patterns
- [ ] Create `measureit_sweep1d_template` resource with Sweep1D code examples
- [ ] Create `measureit_sweep2d_template` resource with Sweep2D code examples
- [ ] Create `measureit_simulsweep_template` resource with SimulSweep examples
- [ ] Create `measureit_sweepqueue_template` resource with SweepQueue patterns
- [ ] Create `measureit_common_patterns` resource with common measurement workflows

### 1.2 Dynamic Template Resource
- [ ] Create `measureit_code_examples` resource that returns ALL available MeasureIt patterns in a structured format

## Phase 2: Database Integration (Optional - requires `%mcp_option measureit`)

### 2.1 Database Query Tools
- [ ] Create `query_measurement_database` tool - search and retrieve past measurements
- [ ] Create `get_database_info` tool - current database status and configuration

### 2.2 Database Resources
- [ ] Create `recent_measurements` resource - list of recent measurement metadata
- [ ] Create `database_configuration` resource - current database settings and paths

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