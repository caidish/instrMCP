"""Tool specification data structures and validation.

This module defines the ToolSpec dataclass and JSON schema validation for dynamic tools.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import re


@dataclass
class ToolParameter:
    """Parameter specification for a dynamic tool."""

    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.enum is not None:
            result["enum"] = self.enum
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolParameter":
        """Create from dictionary representation."""
        return cls(
            name=data["name"],
            type=data["type"],
            description=data["description"],
            required=data.get("required", True),
            default=data.get("default"),
            enum=data.get("enum"),
        )


@dataclass
class ToolSpec:
    """Specification for a dynamically created tool."""

    name: str
    version: str
    description: str
    author: str
    created_at: str
    updated_at: str
    capabilities: List[str]
    parameters: List[ToolParameter]
    returns: Dict[str, str]  # {"type": "string/number/...", "description": "..."}
    source_code: str
    examples: Optional[List[str]] = None
    tags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for JSON serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "capabilities": self.capabilities,
            "parameters": [p.to_dict() for p in self.parameters],
            "returns": self.returns,
            "source_code": self.source_code,
            "examples": self.examples or [],
            "tags": self.tags or [],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolSpec":
        """Create from dictionary representation."""
        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data["author"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            capabilities=data["capabilities"],
            parameters=[ToolParameter.from_dict(p) for p in data["parameters"]],
            returns=data["returns"],
            source_code=data["source_code"],
            examples=data.get("examples"),
            tags=data.get("tags"),
        )

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "ToolSpec":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


# JSON Schema for tool specifications
TOOL_SPEC_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "name",
        "version",
        "description",
        "author",
        "created_at",
        "updated_at",
        "capabilities",
        "parameters",
        "returns",
        "source_code",
    ],
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-z_][a-z0-9_]*$",
            "minLength": 1,
            "maxLength": 64,
            "description": "Tool name (snake_case, max 64 chars)",
        },
        "version": {
            "type": "string",
            "pattern": r"^\d+\.\d+\.\d+$",
            "description": "Semantic version (e.g., 1.0.0)",
        },
        "description": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500,
            "description": "Tool description (10-500 chars)",
        },
        "author": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
            "description": "Tool author identifier",
        },
        "created_at": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp",
        },
        "updated_at": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp",
        },
        "capabilities": {
            "type": "array",
            "items": {
                "type": "string",
                "minLength": 1,
            },
            "description": "Freeform capability labels for documentation/discovery (e.g., cap:numpy, cap:qcodes.read). Not enforced.",
        },
        "parameters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "description"],
                "properties": {
                    "name": {
                        "type": "string",
                        "pattern": "^[a-z_][a-z0-9_]*$",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["string", "number", "boolean", "array", "object"],
                    },
                    "description": {"type": "string", "minLength": 1},
                    "required": {"type": "boolean"},
                    "default": {},
                    "enum": {"type": "array"},
                },
            },
        },
        "returns": {
            "type": "object",
            "required": ["type", "description"],
            "properties": {
                "type": {"type": "string"},
                "description": {"type": "string", "minLength": 1},
            },
        },
        "source_code": {
            "type": "string",
            "minLength": 1,
            "maxLength": 10000,
            "description": "Python function source code (max 10KB)",
        },
        "examples": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Usage examples",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Searchable tags",
        },
    },
}


class ValidationError(Exception):
    """Raised when tool spec validation fails."""


def validate_tool_spec(spec: ToolSpec) -> None:
    """Validate a tool specification.

    Args:
        spec: The tool specification to validate

    Raises:
        ValidationError: If validation fails
    """
    # Validate name
    if not re.match(r"^[a-z_][a-z0-9_]*$", spec.name):
        raise ValidationError(
            f"Invalid tool name '{spec.name}': must be snake_case and start with letter or underscore"
        )
    if len(spec.name) > 64:
        raise ValidationError(f"Tool name too long: {len(spec.name)} chars (max 64)")

    # Validate version
    if not re.match(r"^\d+\.\d+\.\d+$", spec.version):
        raise ValidationError(
            f"Invalid version '{spec.version}': must be semantic version (e.g., 1.0.0)"
        )

    # Validate description
    if len(spec.description) < 10:
        raise ValidationError(
            f"Description too short: {len(spec.description)} chars (min 10)"
        )
    if len(spec.description) > 500:
        raise ValidationError(
            f"Description too long: {len(spec.description)} chars (max 500)"
        )

    # Validate author
    if not spec.author or len(spec.author) > 100:
        raise ValidationError("Author must be 1-100 characters")

    # Validate timestamps
    try:
        datetime.fromisoformat(spec.created_at.replace("Z", "+00:00"))
        datetime.fromisoformat(spec.updated_at.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValidationError(f"Invalid timestamp format: {e}")

    # Validate capabilities (freeform labels - for documentation/discovery only, not enforced)
    # No pattern validation - LLMs can use any format to describe tool dependencies
    # Suggested format: 'cap:library.action' (e.g., 'cap:numpy.array', 'cap:qcodes.read')
    # But any descriptive string is allowed for flexibility
    for cap in spec.capabilities:
        if not isinstance(cap, str) or len(cap) == 0:
            raise ValidationError(
                f"Invalid capability '{cap}': must be non-empty string"
            )

    # Validate parameters
    param_names = set()
    for param in spec.parameters:
        if param.name in param_names:
            raise ValidationError(f"Duplicate parameter name: {param.name}")
        param_names.add(param.name)

        if not re.match(r"^[a-z_][a-z0-9_]*$", param.name):
            raise ValidationError(
                f"Invalid parameter name '{param.name}': must be snake_case"
            )

        if param.type not in ["string", "number", "boolean", "array", "object"]:
            raise ValidationError(
                f"Invalid parameter type '{param.type}' for {param.name}"
            )

    # Validate returns
    if not spec.returns.get("type") or not spec.returns.get("description"):
        raise ValidationError("Returns must specify type and description")

    # Validate source code
    if not spec.source_code or len(spec.source_code) > 10000:
        raise ValidationError("Source code must be 1-10000 characters")

    # Basic Python syntax check
    try:
        compile(spec.source_code, f"<tool:{spec.name}>", "exec")
    except SyntaxError as e:
        raise ValidationError(f"Source code has syntax error: {e}")


def create_tool_spec(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    author: str = "unknown",
    capabilities: Optional[List[str]] = None,
    parameters: Optional[List[Dict[str, Any]]] = None,
    returns: Optional[Dict[str, str]] = None,
    source_code: str = "",
    examples: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> ToolSpec:
    """Create and validate a tool specification.

    Args:
        name: Tool name (snake_case)
        version: Semantic version (default: "1.0.0")
        description: Tool description (default: auto-generated from name)
        author: Author identifier (default: "unknown")
        capabilities: Freeform capability labels for documentation/discovery (default: [])
                     Suggested format: 'cap:library.action' (e.g., 'cap:numpy.array', 'cap:qcodes.read')
                     But any descriptive string is allowed. Not enforced - labels only.
        parameters: Parameter specifications (default: [])
        returns: Return type specification (default: {"type": "object", "description": "Result"})
        source_code: Python function source code
        examples: Usage examples (optional)
        tags: Searchable tags (optional)

    Returns:
        Validated ToolSpec

    Raises:
        ValidationError: If validation fails
    """
    now = datetime.utcnow().isoformat() + "Z"

    # Set defaults
    if not description:
        description = f"Dynamic tool: {name}"
    if capabilities is None:
        capabilities = []  # Empty default - capabilities are freeform labels for documentation/discovery, not enforced
    if parameters is None:
        parameters = []
    if returns is None:
        returns = {"type": "object", "description": "Result"}

    spec = ToolSpec(
        name=name,
        version=version,
        description=description,
        author=author,
        created_at=now,
        updated_at=now,
        capabilities=capabilities,
        parameters=[ToolParameter.from_dict(p) for p in parameters],
        returns=returns,
        source_code=source_code,
        examples=examples,
        tags=tags,
    )

    validate_tool_spec(spec)
    return spec
