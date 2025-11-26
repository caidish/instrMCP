"""Dynamic tool registrar for runtime tool creation.

This module provides meta-tools that allow LLMs to create, update, revoke,
list, and inspect dynamically created tools at runtime.
"""

from typing import Dict, Optional
import json
import logging

from fastmcp import FastMCP, Context

from instrmcp.tools.dynamic import ToolSpec, ToolRegistry, create_tool_spec
from instrmcp.tools.dynamic.tool_spec import ValidationError
from instrmcp.tools.dynamic.tool_registry import RegistryError
from instrmcp.servers.jupyter_qcodes.security.audit import (
    log_tool_registration,
    log_tool_update,
    log_tool_revocation,
    log_tool_error,
)
from instrmcp.servers.jupyter_qcodes.security.consent import ConsentManager
from .dynamic_runtime import DynamicToolRuntime

logger = logging.getLogger(__name__)


class DynamicToolRegistrar:
    """Registrar for dynamic tool meta-tools."""

    def __init__(
        self,
        mcp: FastMCP,
        ipython,
        auto_correct_json: bool = False,
        require_consent: bool = True,
        bypass_consent: bool = False,
    ):
        """Initialize the dynamic tool registrar.

        Args:
            mcp: FastMCP server instance
            ipython: IPython instance for tool execution
            auto_correct_json: Enable automatic JSON correction via LLM
                sampling (default: False)
            require_consent: Require user consent for tool operations
                (default: True)
            bypass_consent: Bypass all consent dialogs (dangerous mode)
        """
        self.mcp = mcp
        self.ipython = ipython
        self.registry = ToolRegistry()
        self.runtime = DynamicToolRuntime(ipython)
        self.auto_correct_json = auto_correct_json
        self.require_consent = require_consent
        self.bypass_consent = bypass_consent

        # Initialize consent manager (bypass mode if dangerous mode enabled)
        self.consent_manager = (
            ConsentManager(ipython, bypass_mode=bypass_consent)
            if require_consent
            else None
        )

        # Track dynamically registered tools for execution
        self._dynamic_tools: Dict[str, ToolSpec] = {}

        # Load existing tools from registry on startup
        self._load_existing_tools()

    def _load_existing_tools(self):
        """Load and register all tools from the registry on server start."""
        try:
            all_tools = self.registry.get_all()
            logger.debug(f"Loading {len(all_tools)} existing tools from registry")

            for tool_name, spec in all_tools.items():
                try:
                    self._register_tool_with_fastmcp(spec)
                    logger.debug(f"Re-registered tool: {tool_name}")
                except Exception as e:
                    logger.error(f"Failed to re-register tool {tool_name}: {e}")

        except Exception as e:
            logger.error(f"Failed to load existing tools: {e}")

    def _register_tool_with_fastmcp(self, spec: ToolSpec):
        """Register a tool with FastMCP and compile it for execution.

        Args:
            spec: The tool specification to register

        Raises:
            RuntimeError: If registration fails
        """
        import inspect
        from typing import Optional as TypingOptional

        # Compile the tool
        _ = self.runtime.compile_tool(spec)  # Verify compilation works

        # Create a dynamic wrapper with proper signature for FastMCP
        # FastMCP requires explicit parameters, not **kwargs
        if spec.parameters:
            # Build parameter list with type hints
            params = []
            annotations = {}
            for param in spec.parameters:
                # Map JSON types to Python types
                type_map = {
                    "string": str,
                    "number": float,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                param_type = type_map.get(param.type, str)

                # Make optional parameters have Optional type hint
                if not param.required:
                    param_type = TypingOptional[param_type]
                    params.append(
                        inspect.Parameter(
                            param.name,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            default=(
                                param.default if param.default is not None else None
                            ),
                            annotation=param_type,
                        )
                    )
                else:
                    params.append(
                        inspect.Parameter(
                            param.name,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            annotation=param_type,
                        )
                    )
                annotations[param.name] = param_type

            # Create signature
            sig = inspect.Signature(params)

            # Create wrapper function with dynamic signature
            def create_wrapper():
                async def wrapper(*args, **kwargs):
                    """Wrapper for dynamically created tool."""
                    # Check for execute consent if required
                    if self.require_consent and self.consent_manager:
                        try:
                            consent_result = await self.consent_manager.request_consent(
                                operation="execute",
                                tool_name=spec.name,
                                author=spec.author,
                                details={
                                    "source_code": spec.source_code,
                                    "capabilities": spec.capabilities or [],
                                    "version": spec.version,
                                    "description": spec.description,
                                    "arguments": dict(kwargs),
                                },
                            )

                            if not consent_result["approved"]:
                                reason = consent_result.get("reason", "User declined")
                                logger.warning(
                                    f"Tool execution declined: {spec.name} - {reason}"
                                )
                                return json.dumps(
                                    {
                                        "status": "error",
                                        "message": f"Execution declined: {reason}",
                                    }
                                )
                            else:
                                logger.debug(f"✅ Tool execution approved: {spec.name}")
                        except TimeoutError:
                            logger.error(
                                f"Consent request timed out for tool execution '{spec.name}'"
                            )
                            return json.dumps(
                                {
                                    "status": "error",
                                    "message": "Consent request timed out",
                                }
                            )

                    try:
                        # Bind arguments to parameters
                        bound = sig.bind(*args, **kwargs)
                        bound.apply_defaults()
                        result = self.runtime.execute_tool(spec.name, **bound.arguments)
                        return json.dumps(
                            {"status": "success", "result": result}, default=str
                        )
                    except Exception as e:
                        return json.dumps({"status": "error", "message": str(e)})

                wrapper.__signature__ = sig
                wrapper.__name__ = spec.name
                wrapper.__doc__ = spec.description
                wrapper.__annotations__ = annotations
                return wrapper

            dynamic_tool_wrapper = create_wrapper()
        else:
            # No parameters - create a simple wrapper
            async def dynamic_tool_wrapper():
                """Wrapper for dynamically created tool."""
                # Check for execute consent if required
                if self.require_consent and self.consent_manager:
                    try:
                        consent_result = await self.consent_manager.request_consent(
                            operation="execute",
                            tool_name=spec.name,
                            author=spec.author,
                            details={
                                "source_code": spec.source_code,
                                "capabilities": spec.capabilities or [],
                                "version": spec.version,
                                "description": spec.description,
                            },
                        )

                        if not consent_result["approved"]:
                            reason = consent_result.get("reason", "User declined")
                            logger.warning(
                                f"Tool execution declined: {spec.name} - {reason}"
                            )
                            return json.dumps(
                                {
                                    "status": "error",
                                    "message": f"Execution declined: {reason}",
                                }
                            )
                        else:
                            logger.debug(f"✅ Tool execution approved: {spec.name}")
                    except TimeoutError:
                        logger.error(
                            f"Consent request timed out for tool execution '{spec.name}'"
                        )
                        return json.dumps(
                            {
                                "status": "error",
                                "message": "Consent request timed out",
                            }
                        )

                try:
                    result = self.runtime.execute_tool(spec.name)
                    return json.dumps(
                        {"status": "success", "result": result}, default=str
                    )
                except Exception as e:
                    return json.dumps({"status": "error", "message": str(e)})

            dynamic_tool_wrapper.__name__ = spec.name
            dynamic_tool_wrapper.__doc__ = spec.description

        # Register with FastMCP
        self.mcp.tool(name=spec.name)(dynamic_tool_wrapper)

        # Store in dynamic tools dict
        self._dynamic_tools[spec.name] = spec

        logger.debug(f"Registered dynamic tool with FastMCP: {spec.name}")

    def _unregister_tool_from_fastmcp(self, tool_name: str):
        """Unregister a tool from FastMCP.

        Args:
            tool_name: Name of the tool to unregister
        """
        # Unregister from runtime
        self.runtime.unregister_tool(tool_name)

        # Remove from dynamic tools dict
        if tool_name in self._dynamic_tools:
            del self._dynamic_tools[tool_name]

        # Remove from FastMCP (available since v2.9.1)
        try:
            self.mcp.remove_tool(tool_name)
            logger.debug(
                f"Successfully removed tool '{tool_name}' from FastMCP and runtime"
            )
        except Exception as e:
            logger.warning(
                f"Failed to remove tool '{tool_name}' from FastMCP: {e}. "
                "Tool may still appear in tool list until server restart."
            )

    async def _attempt_json_correction(
        self,
        ctx: Context,
        field_name: str,
        malformed_json: str,
        original_error: str,
    ) -> Optional[str]:
        """Attempt to auto-correct malformed JSON using LLM sampling.

        This method uses MCP sampling to request the client's LLM to fix
        JSON parsing errors. It's limited to simple structural fixes only.

        Args:
            ctx: FastMCP Context for LLM sampling
            field_name: Name of the field with malformed JSON (e.g., "parameters")
            malformed_json: The malformed JSON string
            original_error: The original JSON parsing error message

        Returns:
            Corrected JSON string if successful, None if correction failed

        Note:
            - Only attempts correction if auto_correct_json is enabled
            - Maximum 1 correction attempt per call (no retry loops)
            - Logs all correction attempts to audit trail
        """
        if not self.auto_correct_json:
            return None

        logger.debug(
            f"Attempting JSON correction for field '{field_name}' via LLM sampling"
        )

        correction_prompt = f"""Fix this malformed JSON string. Return ONLY the corrected JSON, no explanation.

Field name: {field_name}
Malformed JSON: {malformed_json}
Error: {original_error}

Requirements:
- Fix syntax errors (missing quotes, wrong brackets, etc.)
- Preserve the original structure and values
- Return valid JSON only
- Do not add or remove fields

Corrected JSON:"""

        try:
            # Request LLM correction via client sampling
            # Note: Timeout is configured at server level (default 60s)
            # If sampling takes too long, it will raise TimeoutError
            result = await ctx.sample(
                correction_prompt, temperature=0.1, max_tokens=2000
            )

            corrected_json = result.text.strip()

            # Validate that the correction is valid JSON
            json.loads(corrected_json)

            # Log successful correction
            logger.debug(
                f"Successfully corrected JSON for field '{field_name}': "
                f"'{malformed_json[:50]}...' -> '{corrected_json[:50]}...'"
            )

            # Audit log
            log_tool_error(
                "json_correction_success",
                field_name,
                f"Auto-corrected: {malformed_json} -> {corrected_json}",
            )

            return corrected_json

        except TimeoutError as e:
            logger.warning(
                f"JSON correction timed out for field '{field_name}' "
                f"(LLM sampling took too long). Returning original error."
            )
            log_tool_error(
                "json_correction_timeout",
                field_name,
                f"Correction timed out: {e}",
            )
            return None

        except Exception as e:
            logger.warning(
                f"JSON correction failed for field '{field_name}': {e}. "
                "Returning original error."
            )
            log_tool_error(
                "json_correction_failed", field_name, f"Correction attempt failed: {e}"
            )
            return None

    def register_all(self):
        """Register all dynamic tool meta-tools with the MCP server."""

        @self.mcp.tool()
        async def dynamic_register_tool(
            name: str,
            source_code: str,
            ctx: Context,
            version: Optional[str] = None,
            description: Optional[str] = None,
            author: Optional[str] = None,
            capabilities: Optional[str] = None,  # JSON array string
            parameters: Optional[str] = None,  # JSON array string
            returns: Optional[str] = None,  # JSON object string
            examples: Optional[str] = None,  # JSON array string
            tags: Optional[str] = None,  # JSON array string
        ) -> str:
            """Register a new dynamic tool.

            This meta-tool allows LLMs to create new tools at runtime. The tool
            specification will be validated and stored in the registry.

            Args:
                name: Tool name (snake_case, max 64 chars) - REQUIRED
                source_code: Python function source code (max 10KB) - REQUIRED
                version: Semantic version (default: "1.0.0")
                description: Tool description (default: auto-generated from name)
                author: Author identifier (default: "unknown")
                capabilities: JSON array of capabilities for documentation (default: [], not enforced)
                parameters: JSON array of parameter specifications (default: [])
                returns: JSON object with return type specification (default: {"type": "object", "description": "Result"})
                examples: Optional JSON array of usage examples
                tags: Optional JSON array of searchable tags

            Returns:
                JSON string with registration result

            Example (minimal):
                name="my_tool"
                source_code="def my_tool(x):\\n    return x * 2"

            Example (full):
                name="analyze_data"
                source_code="def analyze_data(data):\\n    return sum(data)"
                capabilities='["cap:python.numpy"]'
                parameters='[{"name": "data", "type": "array", "description": "Input data", "required": true}]'
                returns='{"type": "number", "description": "Sum of data"}'
            """
            # Track which fields were corrected for transparency
            corrected_fields = {}

            try:
                # Parse JSON strings (with defaults for empty/None values)
                # Attempt auto-correction for JSON parsing errors if enabled
                async def parse_json_field(field_name: str, json_str: Optional[str]):
                    """Parse JSON with optional auto-correction."""
                    if not json_str:
                        return None
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        # Attempt correction if enabled
                        corrected = await self._attempt_json_correction(
                            ctx, field_name, json_str, str(e)
                        )
                        if corrected:
                            corrected_fields[field_name] = {
                                "original": json_str,
                                "corrected": corrected,
                            }
                            return json.loads(corrected)
                        raise  # Re-raise if correction failed or disabled

                capabilities_list = await parse_json_field("capabilities", capabilities)
                parameters_list = await parse_json_field("parameters", parameters)
                returns_dict = await parse_json_field("returns", returns)
                examples_list = await parse_json_field("examples", examples)
                tags_list = await parse_json_field("tags", tags)

                # Create and validate tool spec (with optional parameters)
                spec = create_tool_spec(
                    name=name,
                    version=version or "1.0.0",
                    description=description or "",
                    author=author or "unknown",
                    capabilities=capabilities_list,
                    parameters=parameters_list,
                    returns=returns_dict,
                    source_code=source_code,
                    examples=examples_list,
                    tags=tags_list,
                )

                # Request consent if required
                if self.require_consent and self.consent_manager:
                    consent_details = {
                        "source_code": source_code,
                        "capabilities": capabilities_list or [],
                        "version": spec.version,
                        "description": spec.description,
                        "parameters": parameters_list or [],
                        "returns": returns_dict,
                    }

                    try:
                        consent_result = await self.consent_manager.request_consent(
                            operation="register",
                            tool_name=name,
                            author=spec.author,
                            details=consent_details,
                        )

                        if not consent_result["approved"]:
                            reason = consent_result.get("reason", "User declined")
                            logger.warning(
                                f"Tool registration declined: {name} by {spec.author} - {reason}"
                            )
                            log_tool_error(
                                "registration_declined",
                                name,
                                f"Consent denied: {reason}",
                            )
                            return json.dumps(
                                {
                                    "status": "error",
                                    "message": f"Tool registration declined: {reason}",
                                    "tool_name": name,
                                }
                            )
                        else:
                            # Consent granted - log approval
                            always_allow_status = (
                                " (always allow granted)"
                                if consent_result.get("always_allow")
                                else ""
                            )
                            logger.debug(
                                f"✅ Tool registration approved: {name} by {spec.author}{always_allow_status}"
                            )
                            if consent_result.get("reason") != "bypass_mode":
                                print(
                                    f"✅ Consent granted for tool '{name}' by '{spec.author}'{always_allow_status}"
                                )

                    except TimeoutError:
                        logger.error(f"Consent request timed out for tool '{name}'")
                        log_tool_error(
                            "registration_timeout", name, "Consent request timed out"
                        )
                        return json.dumps(
                            {
                                "status": "error",
                                "message": "Consent request timed out (5 minutes)",
                                "tool_name": name,
                            }
                        )

                # Register with FastMCP and compile for execution FIRST
                # If this fails, we don't want the tool in the registry
                self._register_tool_with_fastmcp(spec)

                # Only register with registry if FastMCP registration succeeded
                self.registry.register(spec)

                # Log registration
                log_tool_registration(
                    tool_name=name,
                    version=version,
                    author=author,
                    capabilities=capabilities_list,
                )

                # Build response with correction information if any
                response = {
                    "status": (
                        "success" if not corrected_fields else "success_corrected"
                    ),
                    "message": f"Tool '{name}' registered successfully",
                    "tool_name": name,
                    "version": version,
                }

                # Add correction details if auto-correction was used
                if corrected_fields:
                    response["auto_corrections"] = corrected_fields
                    response[
                        "message"
                    ] += f" (with {len(corrected_fields)} JSON field(s) auto-corrected)"

                return json.dumps(response)

            except (json.JSONDecodeError, ValueError) as e:
                error_msg = f"Invalid JSON in parameters: {e}"
                log_tool_error("register", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

            except ValidationError as e:
                error_msg = f"Validation failed: {e}"
                log_tool_error("register", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

            except RegistryError as e:
                error_msg = f"Registration failed: {e}"
                log_tool_error("register", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                log_tool_error("register", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

        @self.mcp.tool()
        async def dynamic_update_tool(
            name: str,
            version: str,
            description: Optional[str] = None,
            capabilities: Optional[str] = None,  # JSON array string
            parameters: Optional[str] = None,  # JSON array string
            returns: Optional[str] = None,  # JSON object string
            source_code: Optional[str] = None,
            examples: Optional[str] = None,  # JSON array string
            tags: Optional[str] = None,  # JSON array string
        ) -> str:
            """Update an existing dynamic tool.

            Updates the specified fields of an existing tool. All fields except
            name and version are optional.

            Args:
                name: Tool name (must exist)
                version: New version (must be different from current)
                description: Updated description (optional)
                capabilities: Updated capabilities JSON array (optional)
                parameters: Updated parameters JSON array (optional)
                returns: Updated return specification JSON object (optional)
                source_code: Updated source code (optional)
                examples: Updated examples JSON array (optional)
                tags: Updated tags JSON array (optional)

            Returns:
                JSON string with update result
            """
            try:
                # Get existing spec
                existing_spec = self.registry.get(name)
                if not existing_spec:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Tool '{name}' does not exist",
                        }
                    )

                old_version = existing_spec.version

                # Create updated spec (merge with existing)
                updated_spec = create_tool_spec(
                    name=name,
                    version=version,
                    description=description or existing_spec.description,
                    author=existing_spec.author,
                    capabilities=(
                        json.loads(capabilities)
                        if capabilities
                        else existing_spec.capabilities
                    ),
                    parameters=(
                        json.loads(parameters)
                        if parameters
                        else [p.to_dict() for p in existing_spec.parameters]
                    ),
                    returns=(json.loads(returns) if returns else existing_spec.returns),
                    source_code=source_code or existing_spec.source_code,
                    examples=(
                        json.loads(examples) if examples else existing_spec.examples
                    ),
                    tags=json.loads(tags) if tags else existing_spec.tags,
                )

                # Request consent if required
                if self.require_consent and self.consent_manager:
                    consent_details = {
                        "source_code": updated_spec.source_code,
                        "capabilities": updated_spec.capabilities or [],
                        "version": version,
                        "description": updated_spec.description,
                        "parameters": [p.to_dict() for p in updated_spec.parameters],
                        "returns": updated_spec.returns,
                        "old_version": old_version,
                    }

                    try:
                        consent_result = await self.consent_manager.request_consent(
                            operation="update",
                            tool_name=name,
                            author=existing_spec.author,
                            details=consent_details,
                        )

                        if not consent_result["approved"]:
                            reason = consent_result.get("reason", "User declined")
                            logger.warning(
                                f"Tool update declined: {name} by {existing_spec.author} - {reason}"
                            )
                            log_tool_error(
                                "update_declined", name, f"Consent denied: {reason}"
                            )
                            return json.dumps(
                                {
                                    "status": "error",
                                    "message": f"Tool update declined: {reason}",
                                    "tool_name": name,
                                }
                            )
                        else:
                            # Consent granted - log approval
                            always_allow_status = (
                                " (always allow granted)"
                                if consent_result.get("always_allow")
                                else ""
                            )
                            logger.debug(
                                f"✅ Tool update approved: {name} v{old_version}→v{version} by {existing_spec.author}{always_allow_status}"
                            )
                            if consent_result.get("reason") != "bypass_mode":
                                print(
                                    f"✅ Consent granted for tool update '{name}' v{old_version}→v{version}{always_allow_status}"
                                )

                    except TimeoutError:
                        logger.error(
                            f"Consent request timed out for tool update '{name}'"
                        )
                        log_tool_error(
                            "update_timeout", name, "Consent request timed out"
                        )
                        return json.dumps(
                            {
                                "status": "error",
                                "message": "Consent request timed out",
                                "tool_name": name,
                            }
                        )

                # Unregister old version and register new version with FastMCP FIRST
                # If registration fails, we'll roll back by re-registering the old version
                self._unregister_tool_from_fastmcp(name)
                try:
                    self._register_tool_with_fastmcp(updated_spec)
                except Exception:
                    # Roll back: re-register the old version
                    self._register_tool_with_fastmcp(existing_spec)
                    raise  # Re-raise to be caught by outer exception handler

                # Only update in registry if FastMCP registration succeeded
                self.registry.update(updated_spec)

                # Log update
                log_tool_update(
                    tool_name=name,
                    old_version=old_version,
                    new_version=version,
                    author=existing_spec.author,
                )

                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Tool '{name}' updated successfully",
                        "tool_name": name,
                        "old_version": old_version,
                        "new_version": version,
                    }
                )

            except (json.JSONDecodeError, ValueError) as e:
                error_msg = f"Invalid JSON in parameters: {e}"
                log_tool_error("update", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

            except ValidationError as e:
                error_msg = f"Validation failed: {e}"
                log_tool_error("update", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

            except RegistryError as e:
                error_msg = f"Update failed: {e}"
                log_tool_error("update", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                log_tool_error("update", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

        @self.mcp.tool()
        async def dynamic_revoke_tool(name: str, reason: Optional[str] = None) -> str:
            """Revoke (delete) a dynamic tool.

            Permanently removes a tool from the registry. This action cannot be undone.

            Args:
                name: Tool name to revoke
                reason: Optional reason for revocation

            Returns:
                JSON string with revocation result
            """
            try:
                # Get spec for logging
                spec = self.registry.get(name)
                if not spec:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Tool '{name}' does not exist",
                        }
                    )

                version = spec.version

                # Revoke from registry
                self.registry.revoke(name)

                # Unregister from FastMCP and runtime
                self._unregister_tool_from_fastmcp(name)

                # Log revocation
                log_tool_revocation(tool_name=name, version=version, reason=reason)

                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Tool '{name}' revoked successfully",
                        "tool_name": name,
                        "version": version,
                    }
                )

            except RegistryError as e:
                error_msg = f"Revocation failed: {e}"
                log_tool_error("revoke", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                log_tool_error("revoke", name, error_msg)
                return json.dumps({"status": "error", "message": error_msg})

        @self.mcp.tool()
        async def dynamic_list_tools(
            tag: Optional[str] = None,
            capability: Optional[str] = None,
            author: Optional[str] = None,
        ) -> str:
            """List all registered dynamic tools with optional filtering.

            Args:
                tag: Filter by tag (optional)
                capability: Filter by capability (e.g., "cap:qcodes.read") (optional)
                author: Filter by author (optional)

            Returns:
                JSON string with list of tools
            """
            try:
                tools = self.registry.list_tools(
                    tag=tag, capability=capability, author=author
                )

                return json.dumps(
                    {
                        "status": "success",
                        "count": len(tools),
                        "tools": tools,
                    },
                    indent=2,
                )

            except Exception as e:
                return json.dumps(
                    {"status": "error", "message": f"Failed to list tools: {e}"}
                )

        @self.mcp.tool()
        async def dynamic_inspect_tool(name: str) -> str:
            """Inspect a dynamic tool's complete specification.

            Returns the full tool specification including source code, parameters,
            capabilities, and metadata.

            Args:
                name: Tool name to inspect

            Returns:
                JSON string with complete tool specification
            """
            try:
                spec = self.registry.get(name)
                if not spec:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Tool '{name}' does not exist",
                        }
                    )

                return json.dumps(
                    {"status": "success", "tool": spec.to_dict()}, indent=2
                )

            except Exception as e:
                return json.dumps(
                    {"status": "error", "message": f"Failed to inspect tool: {e}"}
                )

        @self.mcp.tool()
        async def dynamic_registry_stats() -> str:
            """Get statistics about the dynamic tool registry.

            Returns information about the total number of tools, tools by author,
            tools by capability, and registry location.

            Returns:
                JSON string with registry statistics
            """
            try:
                stats = self.registry.get_stats()
                return json.dumps({"status": "success", "stats": stats}, indent=2)

            except Exception as e:
                return json.dumps(
                    {"status": "error", "message": f"Failed to get stats: {e}"}
                )
