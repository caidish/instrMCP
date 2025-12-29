#!/usr/bin/env python3
"""
Unified Version Management for InstrMCP

This script provides centralized version management across all project files.
The single source of truth is instrmcp/__init__.py's __version__.

Usage:
    # Show all versions
    python tools/version.py

    # Check for mismatches (CI-friendly, exit 1 if mismatch)
    python tools/version.py --check

    # Sync all versions to match main version
    python tools/version.py --sync

    # Bump version (major, minor, patch)
    python tools/version.py --bump patch
    python tools/version.py --bump minor
    python tools/version.py --bump major

    # Set a specific version
    python tools/version.py --set 2.2.0
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Project root directory (parent of tools/)
PROJECT_ROOT = Path(__file__).parent.parent

# All version file locations (relative to project root)
VERSION_FILES = {
    "pyproject.toml": {
        "path": "pyproject.toml",
        "pattern": r'^version = "([^"]+)"',
        "format": 'version = "{version}"',
        "type": "toml",
    },
    "instrmcp/__init__.py": {
        "path": "instrmcp/__init__.py",
        "pattern": r'^__version__ = "([^"]+)"',
        "format": '__version__ = "{version}"',
        "type": "python",
    },
    "instrmcp/servers/__init__.py": {
        "path": "instrmcp/servers/__init__.py",
        "pattern": r'^__version__ = "([^"]+)"',
        "format": '__version__ = "{version}"',
        "type": "python",
    },
    "instrmcp/servers/qcodes/__init__.py": {
        "path": "instrmcp/servers/qcodes/__init__.py",
        "pattern": r'^__version__ = "([^"]+)"',
        "format": '__version__ = "{version}"',
        "type": "python",
    },
    "instrmcp/servers/jupyter_qcodes/__init__.py": {
        "path": "instrmcp/servers/jupyter_qcodes/__init__.py",
        "pattern": r'^__version__ = "([^"]+)"',
        "format": '__version__ = "{version}"',
        "type": "python",
    },
    "instrmcp/extensions/jupyterlab/mcp_active_cell_bridge/__init__.py": {
        "path": "instrmcp/extensions/jupyterlab/mcp_active_cell_bridge/__init__.py",
        "pattern": r'^__version__ = "([^"]+)"',
        "format": '__version__ = "{version}"',
        "type": "python",
    },
    "instrmcp/extensions/jupyterlab/package.json": {
        "path": "instrmcp/extensions/jupyterlab/package.json",
        "pattern": r'"version": "([^"]+)"',
        "format": None,  # JSON handled specially
        "type": "json",
    },
    "docs/source/conf.py": {
        "path": "docs/source/conf.py",
        "pattern": r'^release = "([^"]+)"',
        "format": 'release = "{version}"',
        "type": "python",
        "extra_patterns": [
            (r'^version = "([^"]+)"', 'version = "{version}"'),
        ],
    },
}

# The canonical source of truth
CANONICAL_SOURCE = "instrmcp/__init__.py"


def get_version(file_key: str) -> Optional[str]:
    """Get version from a specific file."""
    config = VERSION_FILES[file_key]
    file_path = PROJECT_ROOT / config["path"]

    if not file_path.exists():
        return None

    content = file_path.read_text()

    if config["type"] == "json":
        try:
            data = json.loads(content)
            return data.get("version")
        except json.JSONDecodeError:
            return None
    else:
        match = re.search(config["pattern"], content, re.MULTILINE)
        if match:
            return match.group(1)
    return None


def get_canonical_version() -> str:
    """Get the canonical version from the source of truth."""
    version = get_version(CANONICAL_SOURCE)
    if version is None:
        raise RuntimeError(f"Could not read version from {CANONICAL_SOURCE}")
    return version


def get_all_versions() -> dict[str, Optional[str]]:
    """Get versions from all tracked files."""
    return {key: get_version(key) for key in VERSION_FILES}


def set_version(file_key: str, new_version: str) -> bool:
    """Set version in a specific file."""
    config = VERSION_FILES[file_key]
    file_path = PROJECT_ROOT / config["path"]

    if not file_path.exists():
        print(f"  ⚠️  {file_key}: File not found, skipping")
        return False

    content = file_path.read_text()
    original_content = content

    if config["type"] == "json":
        try:
            data = json.loads(content)
            data["version"] = new_version
            content = json.dumps(data, indent=2) + "\n"
        except json.JSONDecodeError:
            print(f"  ❌ {file_key}: Invalid JSON")
            return False
    else:
        # Replace main pattern
        new_line = config["format"].format(version=new_version)
        content = re.sub(config["pattern"], new_line, content, flags=re.MULTILINE)

        # Handle extra patterns (like docs/source/conf.py has both release and version)
        if "extra_patterns" in config:
            for pattern, fmt in config["extra_patterns"]:
                new_line = fmt.format(version=new_version)
                content = re.sub(pattern, new_line, content, flags=re.MULTILINE)

    if content != original_content:
        file_path.write_text(content)
        return True
    return False


def bump_version(bump_type: str, current_version: str) -> str:
    """Bump version according to semver rules."""
    parts = current_version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {current_version}")

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}. Use: major, minor, patch")

    return f"{major}.{minor}.{patch}"


def show_versions() -> None:
    """Display all versions and highlight mismatches."""
    canonical = get_canonical_version()
    versions = get_all_versions()

    print("📦 InstrMCP Version Status")
    print("=" * 60)
    print(f"Canonical version (from {CANONICAL_SOURCE}): {canonical}")
    print("-" * 60)

    has_mismatch = False
    for file_key, version in versions.items():
        if version is None:
            status = "⚠️  (file not found)"
        elif version == canonical:
            status = "✅"
        else:
            status = f"❌ MISMATCH (expected {canonical})"
            has_mismatch = True

        print(f"  {file_key}")
        print(f"    Version: {version or 'N/A'} {status}")

    print("-" * 60)
    if has_mismatch:
        print("❌ Version mismatch detected! Run with --sync to fix.")
    else:
        print("✅ All versions are in sync!")


def sync_versions() -> None:
    """Sync all versions to match the canonical version."""
    canonical = get_canonical_version()
    print(f"🔄 Syncing all versions to {canonical}...")
    print("-" * 60)

    for file_key in VERSION_FILES:
        current = get_version(file_key)
        if current is None:
            print(f"  ⚠️  {file_key}: File not found, skipping")
        elif current == canonical:
            print(f"  ✅ {file_key}: Already at {canonical}")
        else:
            if set_version(file_key, canonical):
                print(f"  🔧 {file_key}: {current} → {canonical}")
            else:
                print(f"  ❌ {file_key}: Failed to update")

    print("-" * 60)
    print("✅ Sync complete!")


def do_bump(bump_type: str) -> None:
    """Bump version across all files."""
    current = get_canonical_version()
    new_version = bump_version(bump_type, current)

    print(f"🚀 Bumping version: {current} → {new_version} ({bump_type})")
    print("-" * 60)

    for file_key in VERSION_FILES:
        current_file_version = get_version(file_key)
        if current_file_version is None:
            print(f"  ⚠️  {file_key}: File not found, skipping")
        else:
            if set_version(file_key, new_version):
                print(f"  🔧 {file_key}: {current_file_version} → {new_version}")
            else:
                print(f"  ✅ {file_key}: Already at {new_version}")

    print("-" * 60)
    print(f"✅ Version bumped to {new_version}!")
    print("\nNext steps:")
    print(f"  1. Review changes: git diff")
    print(f"  2. Commit: git commit -am 'Bump version to {new_version}'")
    print(f"  3. Tag: git tag v{new_version}")


def set_all_versions(new_version: str) -> None:
    """Set all versions to a specific value."""
    print(f"📝 Setting all versions to {new_version}...")
    print("-" * 60)

    for file_key in VERSION_FILES:
        current = get_version(file_key)
        if current is None:
            print(f"  ⚠️  {file_key}: File not found, skipping")
        elif set_version(file_key, new_version):
            print(f"  🔧 {file_key}: {current} → {new_version}")
        else:
            print(f"  ✅ {file_key}: Already at {new_version}")

    print("-" * 60)
    print(f"✅ All versions set to {new_version}!")


def check_versions() -> int:
    """Check if all versions match. Returns 0 if all match, 1 if mismatch."""
    canonical = get_canonical_version()
    versions = get_all_versions()

    mismatches = []
    for file_key, version in versions.items():
        if version is not None and version != canonical:
            mismatches.append((file_key, version))

    if mismatches:
        print(f"❌ Version mismatch detected!")
        print(f"   Canonical version: {canonical}")
        for file_key, version in mismatches:
            print(f"   {file_key}: {version}")
        return 1

    print(f"✅ All versions match: {canonical}")
    return 0


def main() -> None:
    """CLI entry point for version management."""
    import argparse

    parser = argparse.ArgumentParser(
        description="InstrMCP Version Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/version.py              # Show all versions
  python tools/version.py --check      # Exit 1 if mismatch (CI-friendly)
  python tools/version.py --sync       # Sync all to canonical version
  python tools/version.py --bump patch # Bump patch version (2.1.0 → 2.1.1)
  python tools/version.py --bump minor # Bump minor version (2.1.0 → 2.2.0)
  python tools/version.py --bump major # Bump major version (2.1.0 → 3.0.0)
  python tools/version.py --set 2.2.0  # Set specific version
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="Check if all versions match (exit 1 if mismatch)",
    )
    group.add_argument(
        "--sync",
        action="store_true",
        help="Sync all versions to match canonical source",
    )
    group.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        help="Bump version (major, minor, or patch)",
    )
    group.add_argument(
        "--set",
        metavar="VERSION",
        help="Set all files to a specific version",
    )

    args = parser.parse_args()

    if args.check:
        sys.exit(check_versions())
    elif args.sync:
        sync_versions()
    elif args.bump:
        do_bump(args.bump)
    elif args.set:
        # Validate version format
        if not re.match(r"^\d+\.\d+\.\d+$", args.set):
            print(f"❌ Invalid version format: {args.set}")
            print("   Expected format: X.Y.Z (e.g., 2.1.0)")
            sys.exit(1)
        set_all_versions(args.set)
    else:
        show_versions()


if __name__ == "__main__":
    main()
