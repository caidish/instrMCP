# Changelog

All notable changes to instrMCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-10-02

### Added - Visual Diff Consent for apply_patch

**Feature:** Enhanced `notebook_apply_patch` with visual diff consent dialog, mimicking Claude Code/Codex behavior.

### Added - Line Range Parameters for notebook_get_editing_cell

**Feature:** Added `line_start` and `line_end` parameters to control context window consumption.

#### Parameters
- `line_start` (Optional[int]): Starting line number, 1-indexed (default: 1)
- `line_end` (Optional[int]): Ending line number, 1-indexed inclusive (default: 100)
- Returns metadata: `total_lines`, `line_start`, `line_end`, `truncated`

#### Benefits
- **Context Window Management** - Prevents large cells from consuming excessive LLM context
- **Flexible Range Selection** - Get specific line ranges for focused analysis
- **Automatic Bounds Clamping** - Invalid ranges safely clamped to cell boundaries
- **Truncation Indicator** - `truncated` flag shows when content is partial

#### Implementation
- **Backend** ([tools.py:655-732](instrmcp/servers/jupyter_qcodes/tools.py#L655-L732)):
  - Added line slicing with 1-indexed bounds
  - Returns empty string (not error) for out-of-bounds ranges
  - Includes line count and truncation metadata
- **MCP Tool** ([notebook_tools.py:88-120](instrmcp/servers/jupyter_qcodes/registrars/notebook_tools.py#L88-L120)):
  - Updated tool signature and documentation
  - Default: lines 1-100 to save context
- **STDIO Proxy** ([stdio_proxy.py:266-278](instrmcp/tools/stdio_proxy.py#L266-L278)):
  - Added parameters to proxy for Claude Desktop/Codex integration
- **Tests**: Updated test expectations for new signature

**Fixed:**
- Backend was using wrong dictionary key (`"text"` instead of `"cell_content"`) causing empty content in diff display
- Replaced custom diff algorithm with industry-standard `diff` library (npm package used by GitHub/GitLab) for robust pattern matching
- Fixed linter issues: removed unused imports in modified files

#### User Experience
- **Visual Diff Display** - Shows exactly what will change before applying patch:
  - Red background with strikethrough for deleted text
  - Green background for added text
  - Grey context lines (3 before/after change location)
  - Line numbers for easy navigation
  - Scrollable view (max 400px height)
  - **Pattern not found warning** - Shows prominent yellow warning if old_text doesn't exist in cell
- **Change Statistics** - Shows chars removed, chars added, and delta
- **Cell Context** - Displays cell type, cell index, and operation description
- **Approval Buttons** - "Decline" | "Allow" | "Always Allow" (session-based permission)

#### Implementation
- **Backend** ([tools_unsafe.py:373-426](instrmcp/servers/jupyter_qcodes/tools_unsafe.py#L373-L426)):
  - Added consent check to `_register_apply_patch`
  - Passes cell content with old/new text for frontend diff computation
  - Returns declined error if user rejects
- **Frontend** ([index.ts:649-886](instrmcp/extensions/jupyterlab/src/index.ts#L649-L886)):
  - `generateDiffDisplay()` - Computes unified diff with context
  - `handlePatchConsentRequest()` - Shows consent dialog with diff visualization
  - Wired into existing `mcp:capcall` consent comm channel
- **Documentation** - Updated CLAUDE.md with consent requirements for all unsafe tools

#### Technical Details
- Follows same consent pattern as `execute_cell` and `delete_cell`
- Uses infinite timeout (user reviews at their own pace)
- **Session-based "always allow"** - Grants permission for "MCP Server" author until restart
- **Uses `diff` library (v8.0.2)** - Battle-tested npm package from GitHub/GitLab
  - Handles all edge cases (unicode, whitespace, newlines)
  - Generates proper unified diff hunks
  - Shows +/- indicators like git diff
  - Zero custom string matching bugs

#### Testing
- All 463 tests pass (1 skipped) across entire codebase
- JupyterLab extension builds successfully with `diff` library integration
- Code formatted with black, all linter checks pass

### Changed
- **Version Update** - System-wide version updated from 1.0.0 to 2.0.0
  - [pyproject.toml](pyproject.toml#L7) - Package version
  - [instrmcp/__init__.py](instrmcp/__init__.py#L9) - Module `__version__`
  - [docs/source/conf.py](docs/source/conf.py#L16-L17) - Documentation version
  - JupyterLab extension remains at 1.0.0
- **CLAUDE.md** - Updated tool documentation:
  - Added line range parameters to `notebook_get_editing_cell` documentation
  - Updated unsafe tool descriptions to indicate consent requirements
  - Clarified which operations require consent (execute, delete, apply_patch)
- **Consent System Documentation** - Clarified which operations require consent
- **Dependencies** - Added `diff` npm package (v8.0.2) to JupyterLab extension

## [2.0.0] - 2025-10-01

### Added - Dynamic Tool Creation System

**Major Feature:** LLM-powered runtime tool creation with user consent workflow.

#### Core Functionality
- **6 Meta-Tools** for dynamic tool management:
  - `dynamic_register_tool` - Create new tools at runtime
  - `dynamic_update_tool` - Update existing tools (requires consent)
  - `dynamic_revoke_tool` - Delete tools from registry
  - `dynamic_list_tools` - List with optional filtering (tag, capability, author)
  - `dynamic_inspect_tool` - Get full tool specification
  - `dynamic_registry_stats` - Registry statistics and analytics

#### Security & Consent
- **JupyterLab Consent Dialog** - Visual approval workflow for tool registration/updates
  - Shows full source code with syntax highlighting
  - Displays capabilities, author, and version
  - "Always allow" checkbox for trusted authors
  - Infinite timeout support for thorough review
- **Session-Only Permissions** - "Always allow" cleared on server restart (configurable)
- **Audit Trail** - All operations logged to `~/.instrmcp/audit/tool_audit.log`
- **Bypass Mode** - `INSTRMCP_CONSENT_BYPASS` environment variable for testing

#### Capability System (v2.0.0 - Labels Only)
- **Freeform Capability Labels** - Tag tools with descriptive capabilities
  - Suggested format: `cap:library.action` (e.g., `cap:numpy.array`)
  - Any non-empty string accepted
  - Used for discovery, filtering, and transparency
  - **Not enforced** - enforcement deferred to v3.0.0

#### Persistence & Storage
- **Persistent Registry** - Tools saved to `~/.instrmcp/registry/{tool_name}.json`
- **Auto-reload** - Registered tools restored on server restart
- **Audit Logging** - Comprehensive operation history

#### JSON Auto-Correction (Phase 4)
- **MCP Sampling Integration** - Automatic JSON error correction via LLM
  - Opt-in via `%mcp_option auto_correct_json`
  - Fixes structural errors in: capabilities, parameters, returns, examples, tags
  - Max 1 correction attempt per registration
  - 60-second timeout with transparent error reporting
  - All corrections logged to audit trail

#### Testing & Quality
- **94 Unit Tests** - 98% pass rate (93 passed, 1 skipped)
  - 29 tests: Tool spec, registry, audit (test_dynamic_tools.py)
  - 26 tests: Consent workflow, always allow (test_consent.py)
  - 11 tests: Runtime execution, compilation (test_dynamic_runtime.py)
  - 8 tests: FastMCP integration (test_dynamic_registrar_integration.py)
  - 20 tests: JSON auto-correction (test_json_auto_correction.py)
- **Mock-Based Testing** - No physical hardware required

#### Documentation
- **New User Guides**:
  - `docs/DYNAMIC_TOOLS.md` - Comprehensive user guide with examples
  - `docs/DYNAMIC_TOOLS_QUICKSTART.md` - 5-minute quick start
- **Updated Documentation**:
  - `README.md` - v2.0.0 features section
  - `CLAUDE.md` - Meta-tools and capability guidance
  - `TODO.md` - Complete implementation status

#### JupyterLab Extension
- **Consent UI** - React-based dialog with comm channel (`mcp:capcall`)
- **Frontend-Backend Communication** - Real-time consent requests and responses

### Changed

- **Tool Spec Validation** - Removed strict capability pattern validation
  - v1.x: Required `cap:domain.action` format
  - v2.0.0: Any non-empty string allowed
- **Consent Manager** - Changed default timeout from 5 minutes to infinite
  - Configurable per-manager instance
  - Session-only permissions by default (no disk persistence)

### Technical Details

#### New Modules
- `instrmcp/tools/dynamic/tool_spec.py` - Tool specification and validation
- `instrmcp/tools/dynamic/tool_registry.py` - File-based tool persistence
- `instrmcp/servers/jupyter_qcodes/dynamic_registrar.py` - FastMCP integration with consent
- `instrmcp/servers/jupyter_qcodes/dynamic_runtime.py` - Tool compilation and execution
- `instrmcp/servers/jupyter_qcodes/security/consent.py` - Consent management system
- `instrmcp/servers/jupyter_qcodes/security/audit.py` - Audit logging

#### Updated Modules
- `instrmcp/servers/jupyter_qcodes/mcp_server.py` - Integrated dynamic tool system
- `instrmcp/tools/stdio_proxy.py` - Added 6 dynamic meta-tool proxies
- `instrmcp/extensions/jupyterlab/src/index.ts` - Consent dialog UI

#### File Structure
```
~/.instrmcp/
├── registry/           # Tool specifications (JSON)
├── consents/           # Session-only permissions (in-memory by default)
└── audit/              # Operation logs
    └── tool_audit.log
```

### Known Limitations

- **No Sandboxing** - Tools run with full Jupyter kernel access (by design)
- **No Capability Enforcement** - Capabilities are labels only in v2.0.0
- **No Integration Tests** - Only unit tests included (integration tests planned for v2.1.0)
- **Session-Only Permissions** - "Always allow" cleared on restart (can be changed to persistent)

### Migration Guide

No breaking changes for existing users. Dynamic tools are opt-in:

1. Start server in unsafe mode: `instrmcp jupyter --unsafe --port 3000`
2. Use meta-tools to create dynamic tools
3. Approve tools via JupyterLab consent dialog

Existing MCP tools and workflows unchanged.

### Roadmap

**v2.1.0** (Future)
- Integration tests for end-to-end workflows
- Performance optimizations
- Additional meta-tool features

**v3.0.0** (Future)
- Capability enforcement with taxonomy
- Mode-based security restrictions
- Resource limits (timeout, memory, rate limiting)
- Advanced audit analytics

---

## [1.x.x] - Previous Versions

See git history for changes in v1.x releases.

---

## Release Notes

### v2.0.0 Highlights

This is a **major release** introducing LLM-powered tool creation:

✅ **Production Ready** - 94 tests, comprehensive documentation
✅ **User Consent** - Visual approval workflow with source code review
✅ **Persistent Storage** - Tools survive server restarts
✅ **Flexible Capabilities** - Freeform labels for discovery
✅ **Audit Trail** - Complete operation history
✅ **Auto JSON Correction** - Optional LLM-powered error fixing

**Breaking Changes:** None - fully backward compatible

**Upgrade Recommendations:**
- Review consent dialogs carefully before approving tools
- Use "always allow" only for trusted authors
- Check audit logs periodically: `tail ~/.instrmcp/audit/tool_audit.log`
- Enable JSON auto-correction if you frequently encounter JSON errors

**Security Notice:**
Dynamic tools have full kernel access. Review all source code in consent dialogs. Use bypass mode only in trusted environments.

---

**Maintained by:** instrMCP Development Team
**Repository:** https://github.com/caidish/instrMCP
**Documentation:** https://instrmcp.readthedocs.io
