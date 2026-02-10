#!/usr/bin/env python3
"""
Token counting utility for InstrMCP metadata descriptions.

Counts tokens used by tool/resource definitions in the MCP metadata.
Supports two counting modes:

1. **Offline** (default): Uses tiktoken to tokenize the full MCP tool JSON
   (name + description + inputSchema). This is an approximation since
   Claude's internal tokenizer differs from tiktoken.

2. **API** (--api): Uses Anthropic's free `messages.count_tokens` endpoint
   for exact token counts. Requires ANTHROPIC_API_KEY.

Usage:
    python tools/token_count.py                          # Offline estimation
    python tools/token_count.py --api                    # Exact via API
    python tools/token_count.py --source merged          # Include user overrides
    python tools/token_count.py --format json            # JSON output
"""

import json
import sys
from pathlib import Path

# Add project root to path for standalone execution
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ---------------------------------------------------------------------------
# Tool parameter schemas (derived from Python function signatures)
# ---------------------------------------------------------------------------
# Maps tool_name -> inputSchema dict matching MCP tools/list format.
# This is the JSON schema that FastMCP generates from function signatures.
# Maintained manually; update when tool signatures change.


def _prop(type_str, default=None, nullable=False):
    """Helper to build a JSON schema property."""
    if nullable:
        schema = {"anyOf": [{"type": type_str}, {"type": "null"}], "default": default}
    elif default is not None:
        schema = {"type": type_str, "default": default}
    else:
        schema = {"type": type_str}
    return schema


TOOL_SCHEMAS = {
    # --- QCodes tools ---
    "qcodes_instrument_info": {
        "type": "object",
        "properties": {
            "name": _prop("string"),
            "with_values": _prop("boolean", default=False),
            "detailed": _prop("boolean", default=False),
        },
        "required": ["name"],
    },
    "qcodes_get_parameter_info": {
        "type": "object",
        "properties": {
            "instrument": _prop("string"),
            "parameter": _prop("string"),
            "detailed": _prop("boolean", default=False),
        },
        "required": ["parameter", "instrument"],
    },
    "qcodes_get_parameter_values": {
        "type": "object",
        "properties": {
            "queries": _prop("string"),
            "detailed": _prop("boolean", default=False),
        },
        "required": ["queries"],
    },
    # --- Notebook tools (read-only) ---
    "notebook_list_variables": {
        "type": "object",
        "properties": {
            "type_filter": _prop("string", default=None, nullable=True),
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "notebook_read_variable": {
        "type": "object",
        "properties": {
            "name": _prop("string"),
            "detailed": _prop("boolean", default=False),
        },
        "required": ["name"],
    },
    "notebook_read_active_cell": {
        "type": "object",
        "properties": {
            "fresh_ms": _prop("integer", default=1000),
            "line_start": _prop("integer", default=None, nullable=True),
            "line_end": _prop("integer", default=None, nullable=True),
            "max_lines": _prop("integer", default=200),
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "notebook_read_active_cell_output": {
        "type": "object",
        "properties": {
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "notebook_read_content": {
        "type": "object",
        "properties": {
            "num_cells": _prop("integer", default=2),
            "include_output": _prop("boolean", default=True),
            "cell_id_notebooks": _prop("string", default=None, nullable=True),
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "notebook_move_cursor": {
        "type": "object",
        "properties": {
            "target": _prop("string"),
            "detailed": _prop("boolean", default=False),
        },
        "required": ["target"],
    },
    "notebook_server_status": {
        "type": "object",
        "properties": {
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    # --- Notebook unsafe tools ---
    "notebook_execute_active_cell": {
        "type": "object",
        "properties": {
            "timeout": _prop("number", default=30.0),
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "notebook_add_cell": {
        "type": "object",
        "properties": {
            "cell_type": _prop("string", default="code"),
            "position": _prop("string", default="below"),
            "content": _prop("string", default=""),
        },
        "required": [],
    },
    "notebook_delete_cell": {
        "type": "object",
        "properties": {
            "cell_id_notebooks": _prop("string", default=None, nullable=True),
        },
        "required": [],
    },
    "notebook_apply_patch": {
        "type": "object",
        "properties": {
            "old_text": _prop("string"),
            "new_text": _prop("string"),
        },
        "required": ["new_text", "old_text"],
    },
    # --- MeasureIt tools ---
    "measureit_get_status": {
        "type": "object",
        "properties": {
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "measureit_wait_for_sweep": {
        "type": "object",
        "properties": {
            "timeout": _prop("number"),
            "variable_name": _prop("string", default=None, nullable=True),
            "all": _prop("boolean", default=False),
            "kill": _prop("boolean", default=True),
            "detailed": _prop("boolean", default=False),
        },
        "required": ["timeout"],
    },
    "measureit_kill_sweep": {
        "type": "object",
        "properties": {
            "variable_name": _prop("string", default=None, nullable=True),
            "all": _prop("boolean", default=False),
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    # --- Database tools ---
    "database_list_experiments": {
        "type": "object",
        "properties": {
            "database_path": _prop("string", default=None, nullable=True),
            "detailed": _prop("boolean", default=False),
            "scan_nested": _prop("boolean", default=False),
        },
        "required": [],
    },
    "database_get_dataset_info": {
        "type": "object",
        "properties": {
            "id": _prop("integer"),
            "database_path": _prop("string", default=None, nullable=True),
            "detailed": _prop("boolean", default=False),
            "code_suggestion": _prop("boolean", default=True),
        },
        "required": ["id"],
    },
    "database_get_database_stats": {
        "type": "object",
        "properties": {
            "database_path": _prop("string", default=None, nullable=True),
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "database_list_all_available_db": {
        "type": "object",
        "properties": {
            "scan_nested": _prop("boolean", default=True),
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    # --- MCP resource tools ---
    "mcp_list_resources": {
        "type": "object",
        "properties": {
            "detailed": _prop("boolean", default=False),
        },
        "required": [],
    },
    "mcp_get_resource": {
        "type": "object",
        "properties": {
            "uri": _prop("string"),
        },
        "required": ["uri"],
    },
}


# ---------------------------------------------------------------------------
# Offline token counting (tiktoken)
# ---------------------------------------------------------------------------


def _build_tool_json(name, tool_override):
    """Build the full MCP tool definition JSON for a tool.

    This reconstructs what Claude sees: name + description + inputSchema.
    """
    tool_def = {"name": name}
    if tool_override.description:
        tool_def["description"] = tool_override.description
    if name in TOOL_SCHEMAS:
        tool_def["input_schema"] = TOOL_SCHEMAS[name]
    return tool_def


def count_metadata_tokens(config, encoding_name="cl100k_base"):
    """Count tokens for all metadata in a MetadataConfig.

    Tokenizes the full MCP tool definition (name + description + inputSchema),
    not just the description text. This gives a much closer approximation
    to the actual token cost seen by Claude.

    Args:
        config: MetadataConfig instance from instrmcp.utils.metadata_config
        encoding_name: tiktoken encoding name (default: cl100k_base)

    Returns:
        dict with per-tool breakdown and grand total
    """
    import tiktoken

    enc = tiktoken.get_encoding(encoding_name)

    def _count(text):
        if not text:
            return 0
        return len(enc.encode(text))

    def _count_json(obj):
        return _count(json.dumps(obj, separators=(",", ":")))

    result = {
        "encoding": encoding_name,
        "tools": {},
        "resource_templates": {},
        "tools_total": 0,
        "resource_templates_total": 0,
        "grand_total": 0,
    }

    # Count tool tokens (full definition)
    for name, tool in sorted(config.tools.items()):
        tool_json = _build_tool_json(name, tool)
        total = _count_json(tool_json)
        desc_tokens = _count(tool.description)
        schema_tokens = _count_json(TOOL_SCHEMAS[name]) if name in TOOL_SCHEMAS else 0
        result["tools"][name] = {
            "description": desc_tokens,
            "schema": schema_tokens,
            "total": total,
        }
        result["tools_total"] += total

    # Count resource template tokens
    for uri, res in sorted(config.resource_templates.items()):
        desc_tokens = _count(res.compose_description() if res.description else None)
        name_tokens = _count(res.name)
        total = desc_tokens + name_tokens
        result["resource_templates"][uri] = {
            "description": desc_tokens,
            "name": name_tokens,
            "total": total,
        }
        result["resource_templates_total"] += total

    result["grand_total"] = result["tools_total"] + result["resource_templates_total"]
    return result


# ---------------------------------------------------------------------------
# API token counting (Anthropic messages.count_tokens)
# ---------------------------------------------------------------------------


def count_tokens_via_api(config, model="claude-sonnet-4-5-20250929"):
    """Count tokens using Anthropic's official count_tokens API.

    This gives exact token counts as seen by Claude. Free to use.

    Args:
        config: MetadataConfig instance
        model: Model to count tokens for

    Returns:
        dict with per-tool breakdown and API total
    """
    import anthropic

    client = anthropic.Anthropic()

    # Build the full tools array
    tools_array = []
    for name, tool in sorted(config.tools.items()):
        tool_def = {
            "name": name,
            "description": tool.description or "",
            "input_schema": TOOL_SCHEMAS.get(
                name, {"type": "object", "properties": {}}
            ),
        }
        tools_array.append(tool_def)

    # Count total tokens with all tools
    response = client.messages.count_tokens(
        model=model,
        tools=tools_array,
        messages=[{"role": "user", "content": "hi"}],
    )
    all_tools_tokens = response.input_tokens

    # Count baseline (no tools) to get the overhead
    response_no_tools = client.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": "hi"}],
    )
    baseline_tokens = response_no_tools.input_tokens

    tools_only = all_tools_tokens - baseline_tokens

    # Measure the hidden system prompt overhead for tool-use.
    # When you enable tool-use, Anthropic injects a hidden system prompt
    # (~300-500 tokens). This is paid once regardless of tool count.
    # We measure it by counting a minimal dummy tool.
    dummy_resp = client.messages.count_tokens(
        model=model,
        tools=[
            {
                "name": "_",
                "description": "",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
        messages=[{"role": "user", "content": "hi"}],
    )
    system_overhead = dummy_resp.input_tokens - baseline_tokens

    # Count per-tool tokens by including one tool at a time.
    # Subtract system_overhead to get the incremental cost of each tool.
    per_tool = {}
    for name, tool in sorted(config.tools.items()):
        tool_def = {
            "name": name,
            "description": tool.description or "",
            "input_schema": TOOL_SCHEMAS.get(
                name, {"type": "object", "properties": {}}
            ),
        }
        resp = client.messages.count_tokens(
            model=model,
            tools=[tool_def],
            messages=[{"role": "user", "content": "hi"}],
        )
        # Incremental cost = total with this tool - baseline - system overhead
        per_tool[name] = resp.input_tokens - baseline_tokens - system_overhead

    sum_individual = sum(per_tool.values())

    result = {
        "model": model,
        "method": "anthropic_api",
        "tools": {name: {"total": tokens} for name, tokens in per_tool.items()},
        "tools_total": sum_individual,
        "tool_use_system_overhead": system_overhead,
        "tools_total_with_overhead": tools_only,
        "resource_templates": {},
        "resource_templates_total": 0,
        "grand_total": tools_only,
    }

    # Resource templates (counted via tiktoken since API doesn't support them)
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        def _count(text):
            return len(enc.encode(text)) if text else 0

        for uri, res in sorted(config.resource_templates.items()):
            desc_tokens = _count(res.compose_description() if res.description else None)
            name_tokens = _count(res.name)
            total = desc_tokens + name_tokens
            result["resource_templates"][uri] = {
                "description": desc_tokens,
                "name": name_tokens,
                "total": total,
            }
            result["resource_templates_total"] += total
    except ImportError:
        pass

    result["grand_total"] += result["resource_templates_total"]
    return result


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_table(data):
    """Format token count data as a human-readable table."""
    lines = []
    is_api = data.get("method") == "anthropic_api"

    # Tools section
    tools = data["tools"]
    if tools:
        lines.append(f"Tools ({len(tools)}):")
        if is_api:
            lines.append(f"  {'Tool Name':<40s} {'Total':>6s}")
            lines.append("  " + "-" * 46)
            for name, counts in tools.items():
                lines.append(f"  {name:<40s} {counts['total']:>6d}")
        else:
            lines.append(
                f"  {'Tool Name':<40s} {'Desc':>6s} {'Schema':>7s} {'Total':>6s}"
            )
            lines.append("  " + "-" * 61)
            for name, counts in tools.items():
                lines.append(
                    f"  {name:<40s} {counts['description']:>6d} "
                    f"{counts['schema']:>7d} {counts['total']:>6d}"
                )

        lines.append("  " + "-" * (46 if is_api else 61))
        lines.append(
            f"  {'Subtotal':<40s} {'':>6s}"
            + ("" if is_api else f" {'':>7s}")
            + f" {data['tools_total']:>6d}"
        )

        if is_api and data.get("tool_use_system_overhead"):
            lines.append(
                f"  {'Tool-use system prompt':<40s} {'':>6s}"
                f" {data['tool_use_system_overhead']:>6d}"
            )
            lines.append(
                f"  {'Total with overhead':<40s} {'':>6s}"
                f" {data['tools_total_with_overhead']:>6d}"
            )
        lines.append("")

    # Resource templates section
    templates = data["resource_templates"]
    if templates:
        lines.append(f"Resource Templates ({len(templates)}):")
        lines.append(f"  {'URI':<50s} {'Desc':>6s} {'Name':>6s} {'Total':>6s}")
        lines.append("  " + "-" * 68)

        for uri, counts in templates.items():
            display_uri = uri.replace("resource://", "")
            lines.append(
                f"  {display_uri:<50s} {counts['description']:>6d} "
                f"{counts['name']:>6d} {counts['total']:>6d}"
            )

        lines.append("  " + "-" * 68)
        lines.append(
            f"  {'Subtotal':<50s} {'':>6s} {'':>6s} "
            f"{data['resource_templates_total']:>6d}"
        )
        lines.append("")

    lines.append(f"Grand Total: {data['grand_total']} tokens")
    return "\n".join(lines)


def format_csv(data):
    """Format token count data as CSV."""
    is_api = data.get("method") == "anthropic_api"

    if is_api:
        lines = ["type,name,total"]
        for name, counts in data["tools"].items():
            lines.append(f"tool,{name},{counts['total']}")
    else:
        lines = ["type,name,description,schema,total"]
        for name, counts in data["tools"].items():
            lines.append(
                f"tool,{name},{counts['description']},"
                f"{counts['schema']},{counts['total']}"
            )

    for uri, counts in data["resource_templates"].items():
        lines.append(
            f"resource_template,{uri},{counts['description']},"
            f"{counts.get('name', 0)},{counts['total']}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def run_token_count(source="baseline", output_format="table", use_api=None):
    """Run token counting and return formatted output.

    By default, tries the Anthropic API for exact counts and falls back
    to tiktoken offline estimation if the API is unavailable.

    Args:
        source: "baseline", "user", or "merged"
        output_format: "table", "csv", or "json"
        use_api: True = force API, False = force offline, None = auto

    Returns:
        Formatted string output
    """
    from instrmcp.utils.metadata_config import (
        _load_baseline_config,
        load_config,
    )

    # Load the requested config source
    if source == "baseline":
        config = _load_baseline_config()
        source_label = "baseline (instrmcp/config/metadata_baseline.yaml)"
    elif source == "user":
        config = load_config()
        source_label = "user overrides (~/.instrmcp/metadata.yaml)"
    else:  # merged
        config = load_config()
        source_label = "merged (baseline + user overrides)"

    # Determine counting method: API first, fallback to offline
    fallback_reason = None
    if use_api is not False:
        try:
            data = count_tokens_via_api(config)
            method_label = f"Anthropic API (model: {data['model']})"
        except ImportError:
            if use_api is True:
                raise
            fallback_reason = "anthropic SDK not installed"
            data = None
        except Exception as e:
            if use_api is True:
                raise
            fallback_reason = str(e)
            data = None

        if data is None:
            # Fallback to offline
            data = count_metadata_tokens(config)
            method_label = (
                f"tiktoken offline ({data['encoding']}) "
                f"[API unavailable: {fallback_reason}]"
            )
    else:
        data = count_metadata_tokens(config)
        method_label = f"tiktoken offline ({data['encoding']})"

    if output_format == "json":
        return json.dumps(data, indent=2)
    elif output_format == "csv":
        return format_csv(data)
    else:
        header = (
            f"InstrMCP Metadata Token Count\n"
            f"Method: {method_label}\n"
            f"Source: {source_label}\n"
        )
        return header + "\n" + format_table(data)


def main():
    """CLI entry point for standalone execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Count tokens in InstrMCP metadata descriptions"
    )
    parser.add_argument(
        "--source",
        choices=["baseline", "user", "merged"],
        default="baseline",
        help="Config source to analyze (default: baseline)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        dest="output_format",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force tiktoken offline estimation (skip API)",
    )

    args = parser.parse_args()

    # Default: API with auto-fallback. --offline forces tiktoken only.
    use_api = False if args.offline else None

    output = run_token_count(
        source=args.source,
        output_format=args.output_format,
        use_api=use_api,
    )
    print(output)


if __name__ == "__main__":
    main()
