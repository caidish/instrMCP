"""Tool registry for managing dynamic tool specifications.

This module handles persistent storage and retrieval of tool specifications
in the ~/.instrmcp/registry/ directory.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .tool_spec import ToolSpec, ValidationError


class RegistryError(Exception):
    """Raised when registry operations fail."""

    pass


class ToolRegistry:
    """Registry for managing dynamic tool specifications."""

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize the tool registry.

        Args:
            registry_path: Path to registry directory (defaults to ~/.instrmcp/registry/)
        """
        if registry_path is None:
            registry_path = Path.home() / ".instrmcp" / "registry"

        self.registry_path = registry_path
        self.registry_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache of loaded tools
        self._cache: Dict[str, ToolSpec] = {}
        self._load_all()

    def _tool_file_path(self, tool_name: str) -> Path:
        """Get the file path for a tool specification.

        Args:
            tool_name: Name of the tool

        Returns:
            Path to the tool's JSON file
        """
        return self.registry_path / f"{tool_name}.json"

    def _load_all(self) -> None:
        """Load all tool specifications from disk into cache."""
        self._cache.clear()

        for file_path in self.registry_path.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    spec = ToolSpec.from_dict(data)
                    self._cache[spec.name] = spec
            except Exception as e:
                # Log error but continue loading other tools
                print(f"Warning: Failed to load {file_path}: {e}")

    def register(self, spec: ToolSpec) -> None:
        """Register a new tool specification.

        Args:
            spec: The tool specification to register

        Raises:
            RegistryError: If tool already exists or registration fails
        """
        if spec.name in self._cache:
            raise RegistryError(
                f"Tool '{spec.name}' already exists. Use update() to modify it."
            )

        file_path = self._tool_file_path(spec.name)
        if file_path.exists():
            raise RegistryError(
                f"Tool file already exists: {file_path}. Registry may be out of sync."
            )

        try:
            # Write to disk
            with open(file_path, "w") as f:
                json.dump(spec.to_dict(), f, indent=2)

            # Update cache
            self._cache[spec.name] = spec

        except Exception as e:
            # Clean up if write failed
            if file_path.exists():
                file_path.unlink()
            raise RegistryError(f"Failed to register tool: {e}")

    def update(self, spec: ToolSpec) -> None:
        """Update an existing tool specification.

        Args:
            spec: The updated tool specification

        Raises:
            RegistryError: If tool doesn't exist or update fails
        """
        if spec.name not in self._cache:
            raise RegistryError(
                f"Tool '{spec.name}' does not exist. Use register() to create it."
            )

        file_path = self._tool_file_path(spec.name)

        try:
            # Update timestamp
            spec.updated_at = datetime.utcnow().isoformat() + "Z"

            # Write to disk
            with open(file_path, "w") as f:
                json.dump(spec.to_dict(), f, indent=2)

            # Update cache
            self._cache[spec.name] = spec

        except Exception as e:
            raise RegistryError(f"Failed to update tool: {e}")

    def revoke(self, tool_name: str) -> None:
        """Revoke (delete) a tool specification.

        Args:
            tool_name: Name of the tool to revoke

        Raises:
            RegistryError: If tool doesn't exist or revocation fails
        """
        if tool_name not in self._cache:
            raise RegistryError(f"Tool '{tool_name}' does not exist")

        file_path = self._tool_file_path(tool_name)

        try:
            # Remove from disk
            if file_path.exists():
                file_path.unlink()

            # Remove from cache
            del self._cache[tool_name]

        except Exception as e:
            raise RegistryError(f"Failed to revoke tool: {e}")

    def get(self, tool_name: str) -> Optional[ToolSpec]:
        """Get a tool specification by name.

        Args:
            tool_name: Name of the tool

        Returns:
            The tool specification, or None if not found
        """
        return self._cache.get(tool_name)

    def list_tools(
        self,
        tag: Optional[str] = None,
        capability: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """List all registered tools with optional filtering.

        Args:
            tag: Filter by tag (optional)
            capability: Filter by capability (optional)
            author: Filter by author (optional)

        Returns:
            List of tool summaries (name, version, description)
        """
        results = []

        for spec in self._cache.values():
            # Apply filters
            if tag and (not spec.tags or tag not in spec.tags):
                continue
            if capability and capability not in spec.capabilities:
                continue
            if author and spec.author != author:
                continue

            results.append(
                {
                    "name": spec.name,
                    "version": spec.version,
                    "description": spec.description,
                    "author": spec.author,
                    "created_at": spec.created_at,
                    "updated_at": spec.updated_at,
                }
            )

        # Sort by name
        results.sort(key=lambda x: x["name"])
        return results

    def get_all(self) -> Dict[str, ToolSpec]:
        """Get all tool specifications.

        Returns:
            Dictionary mapping tool names to specifications
        """
        return self._cache.copy()

    def exists(self, tool_name: str) -> bool:
        """Check if a tool exists in the registry.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool exists, False otherwise
        """
        return tool_name in self._cache

    def reload(self) -> None:
        """Reload all tool specifications from disk.

        Useful if registry files have been modified externally.
        """
        self._load_all()

    def get_stats(self) -> Dict[str, any]:
        """Get registry statistics.

        Returns:
            Dictionary with registry statistics
        """
        return {
            "total_tools": len(self._cache),
            "registry_path": str(self.registry_path),
            "tools_by_author": self._count_by_author(),
            "tools_by_capability": self._count_by_capability(),
        }

    def _count_by_author(self) -> Dict[str, int]:
        """Count tools by author."""
        counts = {}
        for spec in self._cache.values():
            counts[spec.author] = counts.get(spec.author, 0) + 1
        return counts

    def _count_by_capability(self) -> Dict[str, int]:
        """Count tools by capability."""
        counts = {}
        for spec in self._cache.values():
            for cap in spec.capabilities:
                counts[cap] = counts.get(cap, 0) + 1
        return counts
