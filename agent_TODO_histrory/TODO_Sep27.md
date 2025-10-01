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
- [x] Create `get_dataset_info` tool - Get detailed information about a specific dataset
- [x] Create `get_database_stats` tool - Get database statistics and health information
- [x] ~~Create `query_datasets` tool~~ - Deleted (functionality merged into `get_dataset_info`)
- [x] ~~Create `suggest_database_setup` tool~~ - Deleted (users can write basic database setup code themselves)
- [x] ~~Create `suggest_measurement_from_history` tool~~ - Deleted (overly complex with limited practical use)

### 2.2 Database Resources

- [x] Create `database_config` resource - Current QCodes database configuration, path, and connection status
- [x] Create `recent_measurements` resource - Metadata for recent measurements across all experiments
- [x] ~~Create `measurement_templates` resource~~ - Deleted (overly complex analysis with limited value)

### 2.3 Integration Completed

- [x] Added database integration to mcp_server.py with conditional registration
- [x] Updated magic commands to support `%mcp_option database`
- [x] Updated README.md with database integration documentation

### 2.4 ✅ Database Tools Rewrite - COMPLETED

**Status**: Database functionality completely rewritten and working

#### Issues Fixed

- [x] **Completely Rewritten query_tools.py**: Used proper QCodes API patterns from databaseExample.ipynb
  - Fixed `list_experiments()` to properly iterate over run IDs and match to experiments
  - Enhanced `get_dataset_info()` to include parameter data and MeasureIt sweep configuration
  - Improved `get_database_stats()` with measurement type analysis
  - Deleted `query_datasets()` - functionality merged into `get_dataset_info()`

- [x] **Deleted Unnecessary Code Generators**: Removed overly complex, low-value functions
  - Deleted entire `code_generators.py` file

- [x] **Simplified db_resources.py**: Kept only useful resources
  - Kept `get_current_database_config()` - basic database connection info
  - Enhanced `get_recent_measurements()` with MeasureIt metadata extraction
  - Deleted `get_measurement_templates()` - overly complex analysis with limited value

#### Streamlined Architecture

- [x] **3 Core Query Tools**: `list_experiments`, `get_dataset_info`, `get_database_stats`
- [x] **2 Simple Resources**: `database_config`, `recent_measurements`
- [x] **Updated __init__.py**: Removed imports for deleted functions
- [x] **Updated mcp_server.py**: Removed tool registrations for deleted functions

#### Key Improvements

- Based on actual QCodes usage patterns from databaseExample.ipynb
- Proper use of `load_by_id()`, `dataset.get_parameter_data()`, `dataset.metadata['measureit']`
- Extract MeasureIt sweep configurations (Sweep0D/1D/2D/SimulSweep) from metadata
- Return limited parameter data to avoid huge responses
- Focus on direct database queries rather than generic code generation

#### Priority: **COMPLETED** - All database tools now functional and streamlined

## Phase 3: Enhanced Jupyter Integration (Optional - requires `%mcp_option measureit`)

### 3.1 Workflow Tools

- [x] Create `get_measureit_status` tool - check if any MeasureIt sweep is currently running

## Phase 8: Code Architecture Refactoring (OPTIONAL - LOW PRIORITY)

**Status**: Major modularity improvements already completed. Remaining work is optional optimization.

### 8.1 ✅ PHASE 8 COMPLETED (Updated Sep 29, 2024)

- [x] `mcp_server.py` reduced from **973 lines** → **914 lines** → **870 lines** → **234 lines** (76% reduction!)
- [x] **MeasureIt templates** modularized to `instrmcp/extensions/MeasureIt/measureit_templates.py` (33KB)
- [x] **Database tools** modularized to `instrmcp/extensions/database/`:
  - `db_integration.py` (15KB) - 3 core query tools
  - `db_resources.py` (7.7KB) - 2 simple resources
- [x] **Optional feature system** implemented with `%mcp_option measureit/database`
- [x] **Conditional imports** - optional features only loaded when enabled
- [x] **Core tools** extracted to `tools.py` (35KB)
- [x] **Unsafe tools** extracted to `tools_unsafe.py` with registrar pattern (130 lines)
- [x] **Registrar pattern** fully implemented with `registrars/` directory (6 modules)
- [x] **All tool registration** moved to category-specific registrars (saved 442 lines)
- [x] **All resource registration** moved to ResourceRegistrar (saved 225 lines)
- [x] **Imports cleaned** - removed unused imports from mcp_server.py

**Result**: mcp_server.py is now clean coordination logic only (234 lines)

### 8.2 ✅ Final Structure Achieved

```text
instrmcp/servers/jupyter_qcodes/
├── mcp_server.py              # ✅ 234 lines (was 973) - coordination only
├── tools.py                   # Core tool implementations (35KB)
├── tools_unsafe.py            # UnsafeToolRegistrar (130 lines)
├── registrars/                # ✅ NEW: Category-specific registrars
│   ├── __init__.py           # Package exports
│   ├── qcodes_tools.py       # QCodesToolRegistrar (2 tools)
│   ├── notebook_tools.py     # NotebookToolRegistrar (7 tools)
│   ├── measureit_tools.py    # MeasureItToolRegistrar (1 tool)
│   ├── database_tools.py     # DatabaseToolRegistrar (3 tools)
│   └── resources.py          # ResourceRegistrar (11 resources)
├── active_cell_bridge.py      # Cell manipulation bridge (18KB)
└── cache.py                   # Parameter caching (6.7KB)

instrmcp/extensions/           # Optional features
├── MeasureIt/
│   └── measureit_templates.py # Template resources (33KB)
└── database/
    ├── db_integration.py      # Database query tools (15KB)
    └── db_resources.py        # Database resources (7.7KB)
```

**No further refactoring needed** - all goals achieved!

### 8.3 ✅ Complete Modularization - COMPLETED

**Status**: Successfully refactored mcp_server.py using registrar pattern

#### Implementation Steps Completed

- [x] Extract unsafe mode tools to `tools_unsafe.py`
- [x] Create registrar modules in `registrars/` directory:
  - `qcodes_tools.py` - QCodesToolRegistrar (2 tools)
  - `notebook_tools.py` - NotebookToolRegistrar (7 tools)
  - `measureit_tools.py` - MeasureItToolRegistrar (1 tool)
  - `database_tools.py` - DatabaseToolRegistrar (3 tools)
  - `resources.py` - ResourceRegistrar (11 resources)
- [x] Replace `_register_tools()` method with registrar calls (saved 442 lines)
- [x] Replace `_register_resources()` method with registrar calls (saved 225 lines)
- [x] Total reduction: 870 lines → 234 lines (73% reduction, 636 lines saved)

#### File Structure

```
instrmcp/servers/jupyter_qcodes/
├── mcp_server.py              # 234 lines (was 870) - coordination only
├── tools.py                   # Core QCodes/Jupyter tool implementations
├── tools_unsafe.py            # UnsafeToolRegistrar
└── registrars/
    ├── __init__.py            # Package exports
    ├── qcodes_tools.py        # QCodesToolRegistrar
    ├── notebook_tools.py      # NotebookToolRegistrar
    ├── measureit_tools.py     # MeasureItToolRegistrar
    ├── database_tools.py      # DatabaseToolRegistrar
    └── resources.py           # ResourceRegistrar
```

#### Benefits Achieved

- **73% size reduction**: 870 → 234 lines in mcp_server.py
- **Single responsibility**: Each registrar handles one category
- **Easy testing**: Registrars can be tested independently
- **Scalability**: Adding new categories is straightforward
- **Clear separation**: Core/optional features clearly isolated
- **Maintainability**: Changes to one category don't affect others

### 8.4 ✅ Hierarchical Tool Naming - COMPLETED

**Status**: Implemented MCP-standard hierarchical tool naming with slash notation

#### Changes Made

- [x] **Tool Names Updated** to follow MCP 2025-06-18 specification
  - QCodes tools: `qcodes/instrument_info`, `qcodes/get_parameter_values`
  - Notebook tools: `notebook/list_variables`, `notebook/get_editing_cell`, etc.
  - Unsafe tools: `notebook/execute_cell`, `notebook/add_cell`, `notebook/delete_cell`, `notebook/apply_patch`
  - MeasureIt tools: `measureit/get_status`
  - Database tools: `database/list_experiments`, `database/get_dataset_info`, `database/get_database_stats`

- [x] **Files Updated**:
  - `mcp_server.py` - Added `name=` parameter to all `@mcp.tool()` decorators
  - `tools_unsafe.py` - Updated all unsafe tool registrations
  - `stdio_proxy.py` - Updated all proxy tool names and proxy.call() arguments
  - `CLAUDE.md` - Updated documentation with hierarchical names

#### Benefits

- **Better Organization**: Tools grouped by category (`qcodes/*`, `notebook/*`, `measureit/*`, `database/*`)
- **MCP Standard Compliance**: Follows MCP 2025-06-18 specification for hierarchical naming
- **Clearer Intent**: Tool names show which system they belong to
- **Future-Proof**: Ready for MCP clients that support namespace filtering
- **Better AI Understanding**: Claude can see tool relationships and categories

### 8.5 When to Revisit This Phase

**No further refactoring needed!** mcp_server.py is now at 234 lines (target achieved).

Consider revisiting only if:
- New categories of tools are added (e.g., plotting tools, data analysis tools)
- Individual registrars exceed 300 lines and need internal restructuring

## Key Design Principles

- **Transparency**: User sees exact code before execution
- **Safety**: No direct measurement control by AI
- **Education**: User learns MeasureIt patterns
- **Flexibility**: User can modify suggested code
- **Simplicity**: Fewer complex tools, more template resources
- **Integration**: Works with existing Jupyter cell editing tools

## Implementation Notes

- **Optional Feature**: All MeasureIt functionality is behind `%mcp_option measureit` flag
- **Environment**: Consider MeasureItHome environment variable handling
- **Compatibility**: Ensure compatibility with existing QCoDeS instruments
- **Safety**: Think about safe mode vs unsafe mode implications
- **Long-running**: Consider how to handle long-running measurements
- **Plotting**: Think about real-time plot integration

## Phase 9: Enhanced Cell Error Handling & Batch Cell Management ✅ COMPLETED

### 9.1 ✅ Error Tracking for Notebook Tools - COMPLETED

**Status**: Implemented error capture using Python's sys.last_* exception tracking

**Changes Made**:
- [x] Enhanced `notebook/get_editing_cell_output` to capture exceptions
  - Now detects cells that raised errors vs cells with no output
  - Returns error type, message, and full traceback
  - New status types: `"error"`, `"completed"`, `"completed_no_output"`, `"running"`
  - Includes `has_error` boolean and `error` object with details

- [x] Enhanced `notebook/get_notebook_cells` to detect error cells
  - Checks sys.last_* to identify most recent error
  - Adds `has_error` field to each cell
  - Includes `error_count` in response metadata
  - Note: Only most recent error trackable due to Python limitations

**Implementation Details**:
- Uses `sys.last_type`, `sys.last_value`, `sys.last_traceback` for error detection
- Falls back gracefully when error information unavailable
- Compatible with both In/Out cache and history_manager methods
- Error information formatted as JSON with type, message, and traceback

**Benefits**:
- AI can now see which cells failed and why
- Better debugging assistance with full error context
- Complete notebook history including successes and failures

### 9.2 ✅ Batch Cell Deletion Tool - COMPLETED

**Status**: Implemented `notebook/delete_cells` tool for deleting multiple cells by execution count

**New Tool**: `notebook/delete_cells(cell_numbers: str)`
- **Type**: UNSAFE - only available in unsafe mode
- **Input**: JSON string with list of execution counts: `"[1, 2, 5]"` or single number: `"3"`
- **Output**: Detailed deletion results for each cell

**Implementation Stack**:
1. **JupyterLab Extension** (`index.ts`):
   - Added `handleDeleteCellsByNumber()` handler
   - Maps execution counts to cell indices
   - Validates all cells before deletion
   - Deletes in descending order (prevents index shifts)
   - Clears last cell instead of deleting it
   - Returns per-cell results

2. **Python Bridge** (`active_cell_bridge.py`):
   - Added `delete_cells_by_number()` function
   - Sends requests via comm protocol
   - Handles timeout and error cases

3. **Tools Layer** (`tools.py`):
   - Added `delete_cells_by_number()` method
   - Wraps bridge function with metadata

4. **MCP Registrar** (`tools_unsafe.py`):
   - Added `_register_delete_cells()` method
   - Handles JSON parsing (supports both int and list)
   - Registered as `notebook/delete_cells` tool

5. **STDIO Proxy** (`stdio_proxy.py`):
   - Added proxy for Claude Desktop/Code integration

**Safety Features**:
- UNSAFE mode required
- Validates cell numbers exist
- Won't delete if it's the last cell (clears content instead)
- Returns detailed status for each deletion attempt
- Clear warnings in all responses

### 9.3 ✅ Documentation Updates - COMPLETED

- [x] Updated `notebook/execute_cell` docstring to reference `get_editing_cell_output`
- [x] Added Phase 9 to TODO.md with full implementation details
- [ ] Update CLAUDE.md with new tool and enhanced capabilities

**Files Modified**:
1. `instrmcp/servers/jupyter_qcodes/registrars/notebook_tools.py` - Error tracking
2. `instrmcp/servers/jupyter_qcodes/tools_unsafe.py` - Delete cells registrar
3. `instrmcp/servers/jupyter_qcodes/tools.py` - Delete cells method
4. `instrmcp/servers/jupyter_qcodes/active_cell_bridge.py` - Bridge function
5. `instrmcp/extensions/jupyterlab/src/index.ts` - Frontend handler
6. `instrmcp/tools/stdio_proxy.py` - Proxy for delete_cells
7. `agent_TODO_histrory/TODO.md` - Phase 9 documentation

**Testing Checklist**:
- [X] Test error capture with cells that raise exceptions
- [X] Test error capture with cells that have no output
- [X] Test delete_cells with single cell number
- [x] Test delete_cells with list of cell numbers
- [x] Test delete_cells with invalid cell numbers
- [x] Test delete_cells with last cell (should clear, not delete)
- [x] Verify execute_cell → get_editing_cell_output workflow

**Summary**: Phase 9 significantly enhances the notebook integration by adding error tracking and batch cell management. The error tracking provides complete visibility into cell execution status, while batch deletion enables efficient notebook cleanup operations.