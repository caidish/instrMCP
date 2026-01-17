"""
Metadata configuration for MCP tool and resource descriptions.

This module provides Pydantic models for loading tool/resource metadata.
The architecture is:

1. **Baseline** (`instrmcp/config/metadata_baseline.yaml`):
   Contains all default tool/resource descriptions bundled with the package.

2. **User overrides** (`~/.instrmcp/metadata.yaml`):
   Optional user customizations that override the baseline.

Final metadata = Baseline merged with User overrides
"""

from __future__ import annotations

import importlib.resources
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    YAML_AVAILABLE = False

from instrmcp.utils.logging_config import get_logger

logger = get_logger("metadata_config")

# User override config path
USER_CONFIG_PATH = Path.home() / ".instrmcp" / "metadata.yaml"

# Baseline config is bundled with the package
BASELINE_CONFIG_NAME = "metadata_baseline.yaml"


class ArgOverride(BaseModel):
    """Override configuration for a tool argument."""

    description: Optional[str] = None


class ToolOverride(BaseModel):
    """Override configuration for a tool."""

    title: Optional[str] = None
    description: Optional[str] = None
    arguments: dict[str, ArgOverride] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Strip trailing whitespace from description (YAML preserves it)."""
        if self.description:
            object.__setattr__(self, "description", self.description.rstrip())


class ResourceOverride(BaseModel):
    """Override configuration for a resource.

    The final description is composed as:
        {description}

        When to use: {use_when}
        Example: {example}
    """

    name: Optional[str] = None
    description: Optional[str] = None
    use_when: Optional[str] = None
    example: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        """Strip trailing whitespace from description (YAML preserves it)."""
        if self.description:
            object.__setattr__(self, "description", self.description.rstrip())

    def compose_description(self) -> Optional[str]:
        """Compose the full description with use_when and example."""
        if not self.description:
            return None

        parts = [self.description]
        if self.use_when:
            parts.append(f"\nWhen to use: {self.use_when}")
        if self.example:
            parts.append(f"\nExample: {self.example}")

        return "".join(parts)


class MetadataConfig(BaseModel):
    """Root configuration model for metadata overrides.

    Attributes:
        version: Schema version for future compatibility
        strict: If True, raise errors on unknown tools/resources;
                if False, log warnings and continue
        tools: Tool metadata overrides keyed by tool name
        resources: Resource metadata overrides keyed by resource URI
        resource_templates: Resource template overrides keyed by URI
    """

    version: int = 1
    strict: bool = True
    tools: dict[str, ToolOverride] = Field(default_factory=dict)
    resources: dict[str, ResourceOverride] = Field(default_factory=dict)
    resource_templates: dict[str, ResourceOverride] = Field(default_factory=dict)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file and return parsed dict.

    Args:
        path: Path to YAML file

    Returns:
        Parsed dict, or empty dict if file doesn't exist or is empty

    Raises:
        ValueError: If YAML parsing fails
    """
    if not path.exists():
        return {}

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}") from e

    return raw if raw is not None else {}


def _load_baseline_config() -> MetadataConfig:
    """Load the baseline metadata configuration bundled with the package.

    Returns:
        MetadataConfig from the baseline file
    """
    try:
        # Use importlib.resources to load from package data
        # This works whether the package is installed as .py files or in a zip
        with importlib.resources.files("instrmcp.config").joinpath(
            BASELINE_CONFIG_NAME
        ).open() as f:
            raw = yaml.safe_load(f)

        if raw is None:
            logger.warning("Baseline config is empty, using defaults")
            return MetadataConfig()

        config = MetadataConfig.model_validate(raw)
        logger.debug(
            f"Loaded baseline config: {len(config.tools)} tools, "
            f"{len(config.resources)} resources"
        )
        return config

    except FileNotFoundError:
        logger.warning("Baseline config not found, using empty defaults")
        return MetadataConfig()
    except Exception as e:
        logger.error(f"Failed to load baseline config: {e}")
        return MetadataConfig()


def _merge_configs(
    baseline: MetadataConfig, overrides: MetadataConfig
) -> MetadataConfig:
    """Merge user overrides on top of baseline config.

    User overrides take precedence. For tools/resources, individual fields
    are merged (so you can override just the title without losing description).

    Args:
        baseline: Base configuration (from package)
        overrides: User overrides (from ~/.instrmcp/metadata.yaml)

    Returns:
        Merged configuration
    """
    # Start with baseline values
    merged_tools = dict(baseline.tools)
    merged_resources = dict(baseline.resources)
    merged_templates = dict(baseline.resource_templates)

    # Merge tool overrides
    for tool_name, tool_override in overrides.tools.items():
        if tool_name in merged_tools:
            # Merge individual fields
            base_tool = merged_tools[tool_name]
            merged_tools[tool_name] = ToolOverride(
                title=tool_override.title or base_tool.title,
                description=tool_override.description or base_tool.description,
                arguments={**base_tool.arguments, **tool_override.arguments},
            )
        else:
            # New tool override
            merged_tools[tool_name] = tool_override

    # Merge resource overrides
    for uri, res_override in overrides.resources.items():
        if uri in merged_resources:
            base_res = merged_resources[uri]
            merged_resources[uri] = ResourceOverride(
                name=res_override.name or base_res.name,
                description=res_override.description or base_res.description,
                use_when=res_override.use_when or base_res.use_when,
                example=res_override.example or base_res.example,
            )
        else:
            merged_resources[uri] = res_override

    # Merge resource template overrides
    for uri, res_override in overrides.resource_templates.items():
        if uri in merged_templates:
            base_res = merged_templates[uri]
            merged_templates[uri] = ResourceOverride(
                name=res_override.name or base_res.name,
                description=res_override.description or base_res.description,
                use_when=res_override.use_when or base_res.use_when,
                example=res_override.example or base_res.example,
            )
        else:
            merged_templates[uri] = res_override

    return MetadataConfig(
        version=overrides.version if overrides.version != 1 else baseline.version,
        strict=overrides.strict,  # User's strict preference takes precedence
        tools=merged_tools,
        resources=merged_resources,
        resource_templates=merged_templates,
    )


def load_config(user_config_path: Optional[Path] = None) -> MetadataConfig:
    """Load metadata configuration: baseline + user overrides.

    The configuration is loaded in two stages:
    1. Load baseline from package (instrmcp/config/metadata_baseline.yaml)
    2. Load user overrides from ~/.instrmcp/metadata.yaml (if exists)
    3. Merge: user overrides take precedence

    Uses yaml.safe_load for security (prevents YAML tag execution).

    Args:
        user_config_path: Path to user config file. Defaults to ~/.instrmcp/metadata.yaml

    Returns:
        Merged MetadataConfig (baseline + user overrides)

    Raises:
        ValueError: If YAML parsing fails or validation fails
        ImportError: If PyYAML is not installed
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required for metadata configuration. "
            "Install with: pip install pyyaml"
        )

    # Load baseline from package
    baseline = _load_baseline_config()

    # Load user overrides
    if user_config_path is None:
        user_config_path = USER_CONFIG_PATH

    if not user_config_path.exists():
        logger.debug(f"User config not found: {user_config_path}, using baseline only")
        return baseline

    try:
        raw = _load_yaml_file(user_config_path)
        if not raw:
            return baseline

        user_config = MetadataConfig.model_validate(raw)
        logger.debug(
            f"Loaded user config: {len(user_config.tools)} tool overrides, "
            f"{len(user_config.resources)} resource overrides"
        )

        # Merge user overrides on top of baseline
        merged = _merge_configs(baseline, user_config)
        logger.info(
            f"Metadata config loaded: {len(merged.tools)} tools, "
            f"{len(merged.resources)} resources "
            f"(baseline + {len(user_config.tools)} user overrides)"
        )
        return merged

    except Exception as e:
        raise ValueError(f"Invalid user config in {user_config_path}: {e}") from e


# Backwards compatibility alias
DEFAULT_CONFIG_PATH = USER_CONFIG_PATH


def save_config(config: MetadataConfig, path: Optional[Path] = None) -> None:
    """Save metadata configuration to YAML file.

    Creates parent directories if needed. Sets file permissions to 0o600
    for security (user read/write only).

    Args:
        config: Configuration to save
        path: Path to config file. Defaults to ~/.instrmcp/metadata.yaml
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required for metadata configuration. "
            "Install with: pip install pyyaml"
        )

    if path is None:
        path = DEFAULT_CONFIG_PATH

    # Create parent directory
    path.parent.mkdir(parents=True, exist_ok=True)

    # Export config, excluding None values for cleaner YAML
    data = config.model_dump(exclude_none=True)

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    # Security: restrict file permissions to user only
    os.chmod(path, 0o600)
    logger.info(f"Saved metadata config to {path}")


def validate_config_against_server(
    config: MetadataConfig,
    registered_tools: dict[str, Any],
    registered_resources: dict[str, Any],
) -> list[str]:
    """Validate config against registered tools and resources.

    Args:
        config: Configuration to validate
        registered_tools: Dict of tool_name -> tool_info from server
        registered_resources: Dict of resource_uri -> resource_info from server

    Returns:
        List of error/warning messages. Empty if valid.
        In strict mode, these are errors; in non-strict mode, warnings.
    """
    messages: list[str] = []

    # Validate tool overrides
    for tool_name, tool_override in config.tools.items():
        if tool_name not in registered_tools:
            msg = f"Unknown tool in config: {tool_name}"
            if config.strict:
                messages.append(f"ERROR: {msg}")
            else:
                messages.append(f"WARNING: {msg} (skipped)")
            continue

        # Validate argument overrides
        tool_info = registered_tools[tool_name]
        # Get argument names from tool schema
        tool_args = _get_tool_arg_names(tool_info)

        for arg_name in tool_override.arguments:
            if arg_name not in tool_args:
                msg = f"Tool '{tool_name}' has no argument '{arg_name}'"
                if config.strict:
                    messages.append(f"ERROR: {msg}")
                else:
                    messages.append(f"WARNING: {msg} (skipped)")

    # Combine resources and resource_templates for validation
    all_resource_overrides = {
        **config.resources,
        **config.resource_templates,
    }

    # Validate resource overrides
    for uri, _ in all_resource_overrides.items():
        if uri not in registered_resources:
            msg = f"Unknown resource in config: {uri}"
            if config.strict:
                messages.append(f"ERROR: {msg}")
            else:
                messages.append(f"WARNING: {msg} (skipped)")

    return messages


def _get_tool_arg_names(tool_info: Any) -> set[str]:
    """Extract argument names from tool info.

    Handles both FastMCP Tool objects and dict representations.
    """
    arg_names: set[str] = set()

    # Handle FastMCP Tool object
    if hasattr(tool_info, "parameters"):
        params = tool_info.parameters
        if isinstance(params, dict):
            # Proxy tool - parameters is a dict
            properties = params.get("properties", {})
            arg_names = set(properties.keys())
        elif hasattr(params, "model_json_schema"):
            # Regular tool - parameters is a pydantic model
            schema = params.model_json_schema()
            properties = schema.get("properties", {})
            arg_names = set(properties.keys())

    # Handle dict representation (from tools/list)
    elif isinstance(tool_info, dict):
        input_schema = tool_info.get("inputSchema", {})
        if isinstance(input_schema, dict):
            properties = input_schema.get("properties", {})
            arg_names = set(properties.keys())

    return arg_names


def generate_default_config_yaml() -> str:
    """Generate a default config YAML with commented examples.

    Returns:
        YAML string with commented example configuration
    """
    return """# InstrMCP Metadata Configuration
# This file allows overriding tool and resource metadata exposed to the model.
# Changes require server restart to take effect.
#
# Documentation: https://github.com/Qcodes/instrMCP/blob/main/docs/ARCHITECTURE.md

version: 1
strict: true  # false = warn on unknown tools/resources instead of error

# Tool metadata overrides
# tools:
#   qcodes_instrument_info:
#     title: "Get Instrument Info"
#     description: "Describe instruments and parameter hierarchy."
#     arguments:
#       name:
#         description: "Instrument name or '*' for all."
#       with_values:
#         description: "Include cached values (not for '*')."

# Resource metadata overrides
# resources:
#   resource://available_instruments:
#     name: "Available Instruments"
#     description: "JSON list of instruments in the namespace."
#     use_when: "Need instrument names before calling tools."
#     example: "Check this, then call qcodes_instrument_info."

# Resource template overrides
# resource_templates:
#   resource://measureit_sweep1d_template:
#     description: "Sweep1D code examples and patterns."
"""
