# Tool and Resource Metadata CLI Plan

## Goals
- Provide a global config to override tool and resource metadata exposed to the model.
- Make updates config-only (apply on server restart).
- Keep the configuration in a single global file: `~/.instrmcp/metadata.yaml`.

## Proposed Config Shape (example)
```yaml
tools:
  qcodes_instrument_info:
    title: "Get Instrument Info"
    description: "Describe instruments and parameter hierarchy."
    tags: ["cap:qcodes.read"]
    arguments:
      name:
        description: "Instrument name or '*' for all."
      with_values:
        description: "Include cached values (not for '*')."

resources:
  resource://available_instruments:
    name: "Available Instruments"
    description: "JSON list of instruments in the namespace."
    list_entry:
      use_when: "Need instrument names before calling tools."
      example: "Check this, then call qcodes_instrument_info."

resource_templates:
  resource://measureit_sweep1d_template:
    description: "Sweep1D code examples and patterns."
```

## Implementation Steps
1. Add `instrmcp/utils/metadata_config.py`
   - Load `~/.instrmcp/metadata.yaml` with PyYAML.
   - Validate schema and normalize defaults (missing sections -> empty dicts).
   - Expose helper accessors:
     - `get_tool_transforms()` -> `dict[str, ToolTransformConfig]`
     - `get_resource_overrides()` -> `dict[str, dict]`
     - `get_list_entry_overrides()` -> `dict[str, dict]`

2. Apply tool overrides after registration
   - In `instrmcp/servers/jupyter_qcodes/mcp_server.py` and
     `instrmcp/utils/stdio_proxy.py`, call:
     - `mcp.add_tool_transformation(tool_name, ToolTransformConfig(...))`
   - Support overrides for `title`, `description`, `tags`, and per-argument
     descriptions.

3. Apply resource overrides at construction time
   - In `instrmcp/servers/jupyter_qcodes/core/resources.py` and
     `instrmcp/utils/stdio_proxy.py`, read overrides and set
     `name`/`title`/`description` on `Resource` objects and templates.
   - Update `mcp_list_resources` output to apply `list_entry.use_when` and
     `list_entry.example` overrides.

4. Extend CLI with `instrmcp toolmeta`
   - Subcommands: `init`, `list`, `show`, `set`, `unset`, `validate`, `export`.
   - All edits are config-only and should warn that a server restart is required.

5. Documentation
   - Add a short section to `README.md` or `docs/ARCHITECTURE.md` describing
     the metadata file, supported fields, and restart requirement.

6. Tests
   - Unit tests for config parsing and transformation mapping.
   - Small CLI test for reading/writing config (if test harness exists).

## Acceptance Criteria
- Tool overrides appear in `tools/list` output from FastMCP.
- Resource overrides appear in `resources/list` output and in
  `mcp_list_resources` tool output.
- CLI can create, update, validate, and export `~/.instrmcp/metadata.yaml`
  without a running server.
