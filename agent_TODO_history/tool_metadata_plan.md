# Tool and Resource Metadata Configuration Plan

## Goals

- Provide a global config to override tool and resource metadata exposed to the model.
- Make updates config-only (apply on server restart).
- Keep the configuration in a single global file: `~/.instrmcp/metadata.yaml`.
- Metadata propagates automatically from main server to stdio proxy.

## Proposed Config Shape

```yaml
version: 1
strict: true  # false = warn on unknown tools/resources instead of error

tools:
  qcodes_instrument_info:
    title: "Get Instrument Info"
    description: "Describe instruments and parameter hierarchy."
    arguments:
      name:
        description: "Instrument name or '*' for all."
      with_values:
        description: "Include cached values (not for '*')."

resources:
  resource://available_instruments:
    name: "Available Instruments"
    description: "JSON list of instruments in the namespace."
    use_when: "Need instrument names before calling tools."
    example: "Check this, then call qcodes_instrument_info."

resource_templates:
  resource://measureit_sweep1d_template:
    description: "Sweep1D code examples and patterns."
```

**Resource Description Composition:**

For resources, the final description sent to the model is composed as:

```text
{description}

When to use: {use_when}
Example: {example}
```

## Implementation Steps

### 1. Add `instrmcp/utils/metadata_config.py`

Use **Pydantic** for schema validation (cleaner error messages than manual dict parsing):

```python
from pydantic import BaseModel, Field
from typing import Optional
import yaml

class ArgOverride(BaseModel):
    description: Optional[str] = None

class ToolOverride(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    arguments: dict[str, ArgOverride] = Field(default_factory=dict)

class ResourceOverride(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    use_when: Optional[str] = None
    example: Optional[str] = None

class MetadataConfig(BaseModel):
    version: int = 1
    strict: bool = True  # warn vs error on unknown items
    tools: dict[str, ToolOverride] = Field(default_factory=dict)
    resources: dict[str, ResourceOverride] = Field(default_factory=dict)
    resource_templates: dict[str, ResourceOverride] = Field(default_factory=dict)
```

**Security requirements:**

```python
import yaml
import os

def load_config(path: str) -> MetadataConfig:
    if not os.path.exists(path):
        return MetadataConfig()  # graceful default

    # Security: use safe_load to prevent YAML tag execution
    with open(path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return MetadataConfig()

    return MetadataConfig.model_validate(raw)

def save_config(config: MetadataConfig, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(config.model_dump(exclude_none=True), f)
    # Security: restrict file permissions
    os.chmod(path, 0o600)
```

**Validation functions:**

- `validate_against_schema(registered_tools, registered_resources, strict: bool) -> list[str]`
  - Check tool names exist
  - Check argument names exist in tool schema
  - Check resource URIs exist
  - Return errors (strict=True) or warnings (strict=False)

### 2. Apply Tool Overrides After Registration (Server Only)

**Location:** `instrmcp/servers/jupyter_qcodes/mcp_server.py` only

**Verified FastMCP API (tested with v2.13.0):**

```python
from fastmcp.tools.tool_transform import ToolTransformConfig, ArgTransformConfig

def _apply_tool_overrides(self, metadata_config: MetadataConfig):
    """Apply tool metadata overrides from config."""
    for tool_name, overrides in metadata_config.tools.items():
        arg_transforms = {}
        for arg_name, arg_config in overrides.arguments.items():
            if arg_config.description:
                arg_transforms[arg_name] = ArgTransformConfig(
                    description=arg_config.description
                )

        transform = ToolTransformConfig(
            title=overrides.title,
            description=overrides.description,
            arguments=arg_transforms if arg_transforms else {},
        )

        self.mcp.add_tool_transformation(tool_name, transform)
```

**Key API Notes:**

- `add_tool_transformation(tool_name, config)` modifies tool in-place (no need to disable/re-add)
- `ToolTransformConfig` fields: `name`, `title`, `description`, `tags`, `meta`, `enabled`, `arguments`
- `ArgTransformConfig` fields: `name`, `description`, `default`, `hide`, `required`, `examples`

### 3. Apply Resource Overrides After Registration

**Key Finding:** FastMCP has NO `add_resource_transformation()` API.

**Solution:** Directly modify `FunctionResource` attributes after registration:

```python
async def _apply_resource_overrides(self, metadata_config: MetadataConfig):
    """Apply resource metadata overrides from config."""
    registered = await self.mcp.get_resources()

    for uri, overrides in metadata_config.resources.items():
        if uri not in registered:
            if metadata_config.strict:
                raise ValueError(f"Config references unknown resource: {uri}")
            logger.warning(f"Config references unknown resource: {uri}")
            continue

        res = registered[uri]

        # Compose description with use_when and example
        if overrides.description:
            desc_parts = [overrides.description]
            if overrides.use_when:
                desc_parts.append(f"\nWhen to use: {overrides.use_when}")
            if overrides.example:
                desc_parts.append(f"\nExample: {overrides.example}")
            res.description = "".join(desc_parts)

        if overrides.name:
            res.name = overrides.name
```

### 4. Refactor `mcp_list_resources` to Be Dynamic

**Problem:** Current implementation uses hardcoded static list that won't reflect overrides.

**Solution:** Query `mcp.get_resources()` dynamically:

```python
@self.mcp.tool(name="mcp_list_resources")
async def list_resources():
    """List all available MCP resources dynamically."""
    registered = await self.mcp.get_resources()

    resources_list = []
    for uri, res in registered.items():
        entry = {
            "uri": str(res.uri),
            "name": res.name,
            "description": res.description,
        }
        resources_list.append(entry)

    guide = {
        "total_resources": len(resources_list),
        "resources": resources_list,
        "guidance": {
            "workflow": "Check resources first for context, then use tools for operations",
        },
    }

    return [TextContent(type="text", text=json.dumps(guide, indent=2))]
```

### 5. Extend CLI with `instrmcp metadata`

Subcommands:

- `init` — Create default `~/.instrmcp/metadata.yaml` with commented examples
- `edit` — Open config in `$EDITOR` (better UX for multi-line descriptions)
- `list` — Show all configured overrides
- `show <tool|resource>` — Show specific override config
- `set <tool|resource> <field> <value>` — Set a field value
- `unset <tool|resource> [field]` — Remove override (or specific field)
- `validate` — Validate config against running server's schema
- `export` — Export current server's default metadata as YAML template

All edits warn: "Server restart required for changes to take effect."

### 6. Validation Flow

```text
Server Startup
     │
     ▼
Load ~/.instrmcp/metadata.yaml (yaml.safe_load)
     │
     ├── File missing? ──────────► Use empty defaults (ok)
     ├── Parse error? ───────────► Clear error message, abort
     │
     ▼
Pydantic validation (schema, types, allowed fields)
     │
     ├── Unknown field? ─────────► ERROR: "Unknown field 'desc', did you mean 'description'?"
     │
     ▼
Register all tools & resources (with default metadata)
     │
     ▼
Validate config against registered items
     │
     ├── strict=true + unknown tool? ────► ERROR: "Unknown tool: xyz"
     ├── strict=false + unknown tool? ───► WARN: "Unknown tool: xyz (skipped)"
     ├── Invalid arg name? ──────────────► ERROR: "Tool 'abc' has no argument 'xyz'"
     ├── Unknown resource URI? ──────────► ERROR/WARN based on strict mode
     │
     ▼
Apply tool transformations via add_tool_transformation()
     │
     ▼
Apply resource overrides via direct FunctionResource modification
     │
     ▼
Server ready
```

### 7. Documentation

Add section to `docs/ARCHITECTURE.md`:

- Config file location and format
- Supported fields per tool/resource
- `version` field for future schema changes
- `strict` mode behavior
- Validation rules and error messages
- Restart requirement

### 8. Tests

Unit tests for `metadata_config.py`:

- Valid config loading
- Missing file handling (graceful default)
- Invalid tool name detection (strict mode)
- Invalid tool name warning (non-strict mode)
- Invalid argument name detection
- Invalid resource URI detection
- Resource description composition (with use_when/example)
- YAML safe_load security
- File permission (0o600) on save

Integration test:

- Server starts with custom metadata
- `tools/list` returns overridden descriptions
- `mcp_list_resources` returns overridden descriptions
- Dynamic tools (if dynamictool enabled) validation behavior

## Files to Modify

| File | Changes |
|------|---------|
| `instrmcp/utils/metadata_config.py` | **NEW** - Pydantic models, loader, validator |
| `instrmcp/servers/jupyter_qcodes/mcp_server.py` | Apply tool + resource overrides after registration |
| `instrmcp/servers/jupyter_qcodes/core/resources.py` | Refactor `mcp_list_resources` to be dynamic |
| `instrmcp/cli.py` | Add `metadata` subcommand group (including `edit`) |
| `docs/ARCHITECTURE.md` | Document metadata configuration |
| `pyproject.toml` | Ensure `fastmcp>=2.8.0` for transformation API |
| `tests/unit/test_metadata_config.py` | **NEW** - Unit tests |

## Acceptance Criteria

- [x] Tool overrides appear in `tools/list` output from FastMCP
- [x] Resource overrides appear in `resources/list` output
- [x] Resource overrides appear in `mcp_list_resources` tool output (dynamic query)
- [x] Invalid config (typos, wrong args) raises clear error on server start (strict mode)
- [x] Invalid config logs warning and continues (non-strict mode)
- [x] CLI can create, update, validate config without running server
- [x] `instrmcp metadata edit` opens config in `$EDITOR`
- [x] `instrmcp metadata validate` checks config against live server schema (via STDIO proxy)
- [x] Config file created with 0o600 permissions
- [x] YAML loaded with `safe_load` (no arbitrary code execution)

## Implementation Status (Updated)

**Core implementation complete:**
- `instrmcp/utils/metadata_config.py` - Pydantic models with baseline + user override merging
- `instrmcp/config/metadata_baseline.yaml` - Default metadata (single source of truth)
- Tool overrides via `add_tool_transformation()` API
- Resource overrides via direct `FunctionResource` modification
- `mcp_list_resources` dynamically queries registered resources
- E2E test with snapshot verification and user config detection

**CLI implementation complete:**
- `instrmcp metadata init` - Create default config file
- `instrmcp metadata edit` - Open config in $EDITOR
- `instrmcp metadata list` - Show all configured overrides
- `instrmcp metadata show <name>` - Show specific override
- `instrmcp metadata path` - Show config file path
- `instrmcp metadata validate` - Validate config against live server (via STDIO proxy)

**All acceptance criteria met.**

## Verified API References

**Tested on FastMCP 2.13.0.2:**

```python
# Tool transformation imports
from fastmcp.tools.tool_transform import ToolTransformConfig, ArgTransformConfig

# Apply tool transformation (sync method)
mcp.add_tool_transformation(tool_name: str, transformation: ToolTransformConfig) -> None

# Get resources (async method) - returns dict[uri, FunctionResource]
resources = await mcp.get_resources()

# Modify resource directly (FunctionResource is mutable Pydantic model)
resources['resource://foo'].name = "New Name"
resources['resource://foo'].description = "New Description"
```

## Design Decisions (from Gemini + Codex Review)

| Decision | Rationale |
|----------|-----------|
| Use Pydantic for validation | Better error messages, type checking, structural validation |
| Add `version: 1` to config | Future-proofs schema changes |
| Add `strict` mode | Graceful handling of dynamic tools / disabled extensions |
| Add `metadata edit` command | Better UX for multi-line descriptions than `set` |
| Refactor `mcp_list_resources` | Fix dual-source-of-truth problem identified by Codex |
| Use `yaml.safe_load` | Prevent YAML tag code execution (security) |
| Set file permissions to 0o600 | Prevent unauthorized reading of config |
| Direct FunctionResource modification | FastMCP has no resource transformation API |

## Open Questions (Resolved)

- ~~FastMCP tool API~~ → `add_tool_transformation()` exists
- ~~FastMCP resource API~~ → No transformation API; use direct attribute modification
- ~~stdio_proxy changes~~ → Not needed, metadata propagates via MCP protocol
- ~~Tags field~~ → Removed from scope (but API supports it if needed later)
- ~~Multi-client configs~~ → Single global config for all clients
- ~~FastMCP version~~ → Requires `>=2.8.0` (tool transformation introduced in 2.8)
- ~~`mcp_list_resources` issue~~ → Refactor to dynamically query `mcp.get_resources()`
