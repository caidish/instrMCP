"""Profile configuration for the InstrMCP App / Launcher.

A *profile* is a human-readable YAML file describing how to bring up instrmcp:
the Python environment, JupyterLab settings, MCP mode/options, an (informational)
harness expectation, and MeasureIt monitoring.

Architecture mirrors :mod:`instrmcp.utils.metadata_config`:

1. **Bundled default** (``instrmcp/app/defaults/default_profile.yaml``) ships with the
   package and provides every default value.
2. **User / project profiles** (``~/.instrmcp/profiles/<name>.yaml`` and
   ``./.instrmcp/profiles/<name>.yaml``) are deep-merged over the bundled default.

Search order for a named profile is project-local → user → bundled (``default`` only).
``yaml.safe_load`` is used throughout for security.
"""

from __future__ import annotations

import importlib.resources
import os
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:  # pragma: no cover - yaml is a hard dependency in practice
    yaml = None  # type: ignore[assignment]
    YAML_AVAILABLE = False

from instrmcp.utils.logging_config import get_logger

logger = get_logger("app.profiles")

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

#: User-global profile directory.
USER_PROFILE_DIR = Path.home() / ".instrmcp" / "profiles"

#: Project-local profile directory (relative to the current working directory).
PROJECT_PROFILE_DIRNAME = ".instrmcp/profiles"

#: Name of the bundled default profile shipped with the package.
DEFAULT_PROFILE_NAME = "default_profile.yaml"

#: Valid MCP options (mirrors the ``%mcp_option`` magic).
VALID_OPTIONS = {"measureit", "database", "dynamictool", "auto_correct_json"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EnvironmentCfg(BaseModel):
    """Python environment + process environment for spawned subprocesses."""

    conda_env: Optional[str] = None  # doctor warn-only check
    working_dir: Optional[str] = None  # cwd for the JupyterLab subprocess
    env_vars: dict[str, str] = Field(default_factory=dict)


class JupyterCfg(BaseModel):
    """JupyterLab launch settings."""

    port: int = 8888
    host: str = "127.0.0.1"
    open_browser: bool = True
    kernel_name: str = "instrmcp"
    notebook_dir: Optional[str] = None


class McpCfg(BaseModel):
    """Kernel-hosted MCP server settings (baked into the kernelspec exec_lines)."""

    host: str = "127.0.0.1"
    port: int = 8123
    mode: Literal["safe", "unsafe", "dangerous"] = "safe"
    options: list[str] = Field(default_factory=list)
    autostart: bool = True  # whether the kernelspec injects %mcp_start


class HarnessCfg(BaseModel):
    """Agent harness expectation.

    Connect-only: the supervisor never spawns a harness. ``expected`` simply tells
    the dashboard/doctor to note that an external harness is expected.
    """

    expected: bool = False


class MeasureItCfg(BaseModel):
    """MeasureIt monitoring settings (status-only)."""

    enabled: bool = False
    stream_interval_s: float = 1.0


class Profile(BaseModel):
    """Root profile model."""

    version: int = 1
    name: str = "default"
    environment: EnvironmentCfg = Field(default_factory=EnvironmentCfg)
    jupyter: JupyterCfg = Field(default_factory=JupyterCfg)
    mcp: McpCfg = Field(default_factory=McpCfg)
    harness: HarnessCfg = Field(default_factory=HarnessCfg)
    measureit: MeasureItCfg = Field(default_factory=MeasureItCfg)
    supervisor_port: int = 8124


class ProfileInfo(BaseModel):
    """Lightweight description of a discoverable profile (for ``profiles list``)."""

    name: str
    path: str
    source: Literal["project", "user", "bundled"]


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _require_yaml() -> None:
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required for profile configuration. "
            "Install with: pip install pyyaml"
        )


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict if it doesn't exist or is empty."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:  # type: ignore[union-attr]
        raise ValueError(f"Invalid YAML in {path}: {e}") from e
    return raw if isinstance(raw, dict) else {}


def _load_bundled_default() -> dict[str, Any]:
    """Load the bundled default profile as a raw dict."""
    try:
        with importlib.resources.files("instrmcp.app.defaults").joinpath(
            DEFAULT_PROFILE_NAME
        ).open() as f:
            raw = yaml.safe_load(f)
        return raw if isinstance(raw, dict) else {}
    except FileNotFoundError:  # pragma: no cover - shipped with the package
        logger.warning("Bundled default profile not found, using model defaults")
        return {}


def _bundled_profile_overlay(name: str) -> Optional[dict[str, Any]]:
    """Load a bundled named profile (``defaults/<name>.yaml``) as a raw dict."""
    if name == "default":
        return None
    try:
        res = importlib.resources.files("instrmcp.app.defaults").joinpath(
            f"{name}.yaml"
        )
        if res.is_file():
            raw = yaml.safe_load(res.read_text())
            return raw if isinstance(raw, dict) else {}
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto ``base`` (override wins for scalars/lists)."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def profile_search_paths(name: str) -> list[tuple[Path, str]]:
    """Return candidate ``(path, source)`` locations for a named profile.

    Order is project-local first (highest precedence), then user, then bundled.
    """
    candidates: list[tuple[Path, str]] = [
        (Path.cwd() / PROJECT_PROFILE_DIRNAME / f"{name}.yaml", "project"),
        (USER_PROFILE_DIR / f"{name}.yaml", "user"),
    ]
    return candidates


def list_profiles() -> list[ProfileInfo]:
    """Discover all available profiles across project, user, and bundled locations."""
    found: dict[str, ProfileInfo] = {}

    # Bundled profiles (lowest precedence, always present).
    found["default"] = ProfileInfo(
        name="default",
        path="<bundled>",
        source="bundled",
    )
    try:
        for res in importlib.resources.files("instrmcp.app.defaults").iterdir():
            if res.name.endswith(".yaml") and res.name != DEFAULT_PROFILE_NAME:
                n = res.name[:-5]
                found[n] = ProfileInfo(name=n, path="<bundled>", source="bundled")
    except (FileNotFoundError, ModuleNotFoundError, OSError):  # pragma: no cover
        pass

    # User profiles.
    if USER_PROFILE_DIR.is_dir():
        for path in sorted(USER_PROFILE_DIR.glob("*.yaml")):
            name = path.stem
            found[name] = ProfileInfo(name=name, path=str(path), source="user")

    # Project-local profiles (highest precedence).
    project_dir = Path.cwd() / PROJECT_PROFILE_DIRNAME
    if project_dir.is_dir():
        for path in sorted(project_dir.glob("*.yaml")):
            name = path.stem
            found[name] = ProfileInfo(name=name, path=str(path), source="project")

    return [found[k] for k in sorted(found)]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_profile(name: Optional[str] = None) -> Profile:
    """Load a named profile, deep-merged over the bundled default.

    Args:
        name: Profile name (without ``.yaml``). Defaults to ``"default"``.

    Returns:
        A validated :class:`Profile`.

    Raises:
        FileNotFoundError: If a non-default profile name resolves to no file.
        ValueError: If YAML parsing or model validation fails.
    """
    _require_yaml()
    name = name or "default"

    merged = _load_bundled_default()

    overlay_path: Optional[Path] = None
    for path, _source in profile_search_paths(name):
        if path.exists():
            overlay_path = path
            break

    overlay: Optional[dict] = None
    if overlay_path is not None:
        overlay = _load_yaml_file(overlay_path)
        logger.debug("Loaded profile '%s' from %s", name, overlay_path)
    else:
        overlay = _bundled_profile_overlay(name)
        if overlay is not None:
            logger.debug("Loaded bundled profile '%s'", name)

    if overlay is not None:
        merged = _deep_merge(merged, overlay)
        # The resolved name is the requested name unless the overlay sets one
        # explicitly (the bundled default's name="default" must not shadow it).
        if "name" not in overlay:
            merged["name"] = name
    elif name != "default":
        searched = ", ".join(str(p) for p, _ in profile_search_paths(name))
        raise FileNotFoundError(
            f"Profile '{name}' not found. Searched: {searched}, <bundled>"
        )
    else:
        merged.setdefault("name", name)

    try:
        return Profile.model_validate(merged)
    except Exception as e:  # pydantic ValidationError
        raise ValueError(f"Invalid profile '{name}': {e}") from e


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_profile(profile: Profile) -> list[str]:
    """Validate a profile's semantic constraints.

    Returns a list of human-readable error strings (empty if valid).
    """
    errors: list[str] = []

    # Port collisions.
    ports = {
        "jupyter.port": profile.jupyter.port,
        "mcp.port": profile.mcp.port,
        "supervisor_port": profile.supervisor_port,
    }
    seen: dict[int, str] = {}
    for label, port in ports.items():
        if port in seen:
            errors.append(
                f"Port {port} is used by both {seen[port]} and {label}; "
                "ports must be distinct."
            )
        else:
            seen[port] = label

    # Unknown options.
    for opt in profile.mcp.options:
        if opt not in VALID_OPTIONS:
            errors.append(f"Unknown MCP option '{opt}'. Valid: {sorted(VALID_OPTIONS)}")

    # dynamictool requires dangerous mode (mirrors the %mcp_option rule).
    if "dynamictool" in profile.mcp.options and profile.mcp.mode != "dangerous":
        errors.append(
            "Option 'dynamictool' requires mcp.mode == 'dangerous' "
            f"(got '{profile.mcp.mode}')."
        )

    # measureit option vs measureit.enabled consistency (warn via error list).
    if profile.measureit.enabled and "measureit" not in profile.mcp.options:
        errors.append(
            "measureit.enabled is true but 'measureit' is not in mcp.options; "
            "the kernel will not expose measureit tools."
        )

    return errors


# ---------------------------------------------------------------------------
# Saving (used by future `profiles init`)
# ---------------------------------------------------------------------------


def save_profile(profile: Profile, path: Optional[Path] = None) -> Path:
    """Save a profile to YAML with user-only permissions (0o600)."""
    _require_yaml()
    if path is None:
        path = USER_PROFILE_DIR / f"{profile.name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = profile.model_dump(exclude_none=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    os.chmod(path, 0o600)
    logger.info("Saved profile to %s", path)
    return path
