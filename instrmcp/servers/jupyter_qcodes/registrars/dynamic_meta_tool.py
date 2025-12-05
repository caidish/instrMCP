"""
Unified dynamic meta-tool registrar.

Consolidates 6 dynamic tools into a single meta-tool to reduce
context window overhead while preserving all functionality including
consent flows and runtime tool compilation.
"""

import json
import time
import inspect
from typing import List, Optional, Dict, Set

from mcp.types import TextContent
from fastmcp import FastMCP, Context

from instrmcp.logging_config import get_logger
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
from ..dynamic_runtime import DynamicToolRuntime
from ..tool_logger import log_tool_call

logger = get_logger("tools.dynamic")


class DynamicMetaToolRegistrar:
    """Registers unified dynamic meta-tool with the MCP server."""

    # Actions classified by safety and consent requirements
    SAFE_ACTIONS: Set[str] = {"list", "inspect", "stats"}
    UNSAFE_ACTIONS: Set[str] = {"register", "update", "revoke"}
    CONSENT_REQUIRED: Set[str] = {"register", "update"}  # revoke: NO consent
    ALL_ACTIONS: Set[str] = SAFE_ACTIONS | UNSAFE_ACTIONS

    # Action -> (required_params, optional_params_with_defaults)
    ACTION_PARAMS: Dict[str, tuple] = {
        "register": (
            ["name", "source_code"],
            {
                "version": "1.0.0",
                "description": None,
                "author": "unknown",
                "capabilities": None,
                "parameters": None,
                "returns": None,
                "examples": None,
                "tags": None,
            },
        ),
        "update": (
            ["name", "version"],
            {
                "description": None,
                "capabilities": None,
                "parameters": None,
                "returns": None,
                "source_code": None,
                "examples": None,
                "tags": None,
            },
        ),
        "revoke": (["name"], {"reason": None}),
        "list": ([], {"tag": None, "capability": None, "author": None}),
        "inspect": (["name"], {}),
        "stats": ([], {}),
    }

    # Action -> usage example for error messages
    ACTION_USAGE: Dict[str, str] = {
        "register": 'dynamic(action="register", name="my_tool", source_code="def my_tool(x): return x * 2")',
        "update": 'dynamic(action="update", name="my_tool", version="1.1.0", source_code="def my_tool(x): return x * 3")',
        "revoke": 'dynamic(action="revoke", name="my_tool") or dynamic(action="revoke", name="my_tool", reason="No longer needed")',
        "list": 'dynamic(action="list") or dynamic(action="list", author="me") or dynamic(action="list", capability="cap:numpy")',
        "inspect": 'dynamic(action="inspect", name="my_tool")',
        "stats": 'dynamic(action="stats")',
    }

    def __init__(
        self,
        mcp_server: FastMCP,
        ipython,
        auto_correct_json: bool = False,
        require_consent: bool = True,
        bypass_consent: bool = False,
        is_unsafe_mode: bool = False,
    ):
        """
        Initialize the dynamic meta-tool registrar.

        Args:
            mcp_server: FastMCP server instance
            ipython: IPython instance for tool execution
            auto_correct_json: Enable automatic JSON correction via LLM sampling
            require_consent: Require user consent for tool operations
            bypass_consent: Bypass all consent dialogs (dangerous mode)
            is_unsafe_mode: Whether server is running in unsafe mode
        """
        self.mcp = mcp_server
        self.ipython = ipython
        self.registry = ToolRegistry()
        self.runtime = DynamicToolRuntime(ipython)
        self.auto_correct_json = auto_correct_json
        self.require_consent = require_consent
        self.bypass_consent = bypass_consent
        self.is_unsafe_mode = is_unsafe_mode

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
        """Register a tool with FastMCP and compile it for execution."""
        from typing import Optional as TypingOptional

        # Compile the tool
        _ = self.runtime.compile_tool(spec)

        # Create a dynamic wrapper with proper signature for FastMCP
        if spec.parameters:
            params = []
            annotations = {}
            for param in spec.parameters:
                type_map = {
                    "string": str,
                    "number": float,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                param_type = type_map.get(param.type, str)

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

            sig = inspect.Signature(params)

            def create_wrapper():
                async def wrapper(*args, **kwargs):
                    """Wrapper for dynamically created tool."""
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

            async def dynamic_tool_wrapper():
                """Wrapper for dynamically created tool."""
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

        self.mcp.tool(name=spec.name)(dynamic_tool_wrapper)
        self._dynamic_tools[spec.name] = spec
        logger.debug(f"Registered dynamic tool with FastMCP: {spec.name}")

    def _unregister_tool_from_fastmcp(self, tool_name: str):
        """Unregister a tool from FastMCP."""
        self.runtime.unregister_tool(tool_name)

        if tool_name in self._dynamic_tools:
            del self._dynamic_tools[tool_name]

        try:
            self.mcp.remove_tool(tool_name)
            logger.debug(f"Successfully removed tool '{tool_name}' from FastMCP")
        except Exception as e:
            logger.warning(
                f"Failed to remove tool '{tool_name}' from FastMCP: {e}. "
                "Tool may still appear until server restart."
            )

    async def _attempt_json_correction(
        self,
        ctx: Context,
        field_name: str,
        malformed_json: str,
        original_error: str,
    ) -> Optional[str]:
        """Attempt to auto-correct malformed JSON using LLM sampling."""
        if not self.auto_correct_json:
            return None

        logger.debug(f"Attempting JSON correction for field '{field_name}'")

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
            result = await ctx.sample(
                correction_prompt, temperature=0.1, max_tokens=2000
            )
            corrected_json = result.text.strip()
            json.loads(corrected_json)  # Validate

            logger.debug(f"Successfully corrected JSON for field '{field_name}'")
            log_tool_error(
                "json_correction_success",
                field_name,
                f"Auto-corrected: {malformed_json} -> {corrected_json}",
            )
            return corrected_json

        except TimeoutError as e:
            logger.warning(f"JSON correction timed out for field '{field_name}'")
            log_tool_error("json_correction_timeout", field_name, f"Timeout: {e}")
            return None

        except Exception as e:
            logger.warning(f"JSON correction failed for field '{field_name}': {e}")
            log_tool_error("json_correction_failed", field_name, f"Failed: {e}")
            return None

    def register_all(self):
        """Register the unified dynamic meta-tool."""
        self._register_dynamic_tool()

    def _register_dynamic_tool(self):
        @self.mcp.tool(name="dynamic")
        async def dynamic(
            action: str,
            ctx: Context,
            # Register/update params
            name: Optional[str] = None,
            source_code: Optional[str] = None,
            version: Optional[str] = None,
            description: Optional[str] = None,
            author: Optional[str] = None,
            capabilities: Optional[str] = None,
            parameters: Optional[str] = None,
            returns: Optional[str] = None,
            examples: Optional[str] = None,
            tags: Optional[str] = None,
            # List filter params
            tag: Optional[str] = None,
            capability: Optional[str] = None,
            # Revoke param
            reason: Optional[str] = None,
        ) -> List[TextContent]:
            """Unified dynamic tool for runtime tool management.

            Create, update, inspect, and manage dynamically registered tools at runtime.
            Tools persist across server restarts in ~/.instrmcp/registry/.

            STRICT PARAMETER REQUIREMENTS BY ACTION:

            ═══ READ OPERATIONS ═══

            action="list"
                → No required params.
                → Optional: tag, capability, author (filter results)
                Examples:
                  dynamic(action="list")
                  dynamic(action="list", author="me")
                  dynamic(action="list", capability="cap:numpy")
                  dynamic(action="list", tag="analysis")

            action="inspect"
                → REQUIRES: name
                → Returns full tool specification including source code
                Example:
                  dynamic(action="inspect", name="my_tool")

            action="stats"
                → No required params.
                → Returns registry statistics (total tools, by author, by capability)
                Example:
                  dynamic(action="stats")

            ═══ WRITE OPERATIONS (unsafe mode only) ═══

            action="register" [consent required]
                → REQUIRES: name, source_code
                → Optional: version (default "1.0.0"), description, author (default "unknown"),
                  capabilities (JSON array), parameters (JSON array), returns (JSON object),
                  examples (JSON array), tags (JSON array)
                → User sees consent dialog with full source code before approval
                Examples:
                  dynamic(action="register", name="add_nums", source_code="def add_nums(a, b): return a + b")
                  dynamic(action="register", name="analyze", source_code="def analyze(data): return sum(data)",
                          capabilities='["cap:python.builtin"]',
                          parameters='[{"name": "data", "type": "array", "required": true}]')

            action="update" [consent required]
                → REQUIRES: name, version (new version, must differ from current)
                → Optional: source_code, description, capabilities, parameters, returns, examples, tags
                → Only provided fields are updated; others keep existing values
                → User sees consent dialog before approval
                Example:
                  dynamic(action="update", name="add_nums", version="1.1.0",
                          source_code="def add_nums(a, b, c=0): return a + b + c")

            action="revoke"
                → REQUIRES: name
                → Optional: reason (for audit trail)
                → Permanently removes tool from registry (cannot be undone)
                → NO consent required (destructive but explicit)
                Examples:
                  dynamic(action="revoke", name="my_tool")
                  dynamic(action="revoke", name="old_tool", reason="Replaced by new_tool")

            JSON Parameter Formats:
                capabilities: '["cap:numpy", "cap:custom.analysis"]'
                parameters: '[{"name": "x", "type": "number", "description": "Input", "required": true}]'
                returns: '{"type": "number", "description": "Result"}'
                examples: '["example usage 1", "example usage 2"]'
                tags: '["analysis", "math"]'

            Returns:
                JSON with operation result or error details including valid_actions hint.
            """
            return await self._handle_action(
                ctx=ctx,
                action=action,
                name=name,
                source_code=source_code,
                version=version,
                description=description,
                author=author,
                capabilities=capabilities,
                parameters=parameters,
                returns=returns,
                examples=examples,
                tags=tags,
                tag=tag,
                capability=capability,
                reason=reason,
            )

    async def _handle_action(
        self, ctx: Context, action: str, **kwargs
    ) -> List[TextContent]:
        """Route and execute the requested action."""
        start = time.perf_counter()

        # Sanitize action: strip quotes that LLMs sometimes add
        if action:
            action = action.strip("\"'")

        # 1. Validate action exists
        if action not in self.ALL_ACTIONS:
            return self._error_response(
                error=f"Unknown action: '{action}'",
                action=action,
                hint="Use one of the valid actions listed below",
                valid_actions=sorted(self.ALL_ACTIONS),
            )

        # 2. Check mode for unsafe actions
        if action in self.UNSAFE_ACTIONS and not self.is_unsafe_mode:
            return self._error_response(
                error=f"Action '{action}' requires unsafe mode",
                action=action,
                hint="Enable unsafe mode with %mcp_unsafe magic command",
            )

        # 3. Validate required parameters
        required_params, _ = self.ACTION_PARAMS[action]
        missing = [p for p in required_params if kwargs.get(p) is None]
        if missing:
            return self._error_response(
                error=f"Missing required parameter(s): {missing}",
                action=action,
                missing=missing,
                usage=self.ACTION_USAGE.get(action, ""),
            )

        # 4. Execute action
        try:
            if action == "register":
                result = await self._action_register(ctx=ctx, **kwargs)
            elif action == "update":
                result = await self._action_update(**kwargs)
            elif action == "revoke":
                result = await self._action_revoke(**kwargs)
            elif action == "list":
                result = await self._action_list(**kwargs)
            elif action == "inspect":
                result = await self._action_inspect(**kwargs)
            elif action == "stats":
                result = await self._action_stats()
            else:
                return self._error_response(
                    error=f"Action '{action}' not implemented",
                    action=action,
                )

            duration = (time.perf_counter() - start) * 1000
            log_tool_call("dynamic", {"action": action, **kwargs}, duration, "success")
            return [TextContent(type="text", text=result)]

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            log_tool_call(
                "dynamic", {"action": action, **kwargs}, duration, "error", str(e)
            )
            logger.error(f"Error in dynamic action '{action}': {e}")
            return self._error_response(
                error=str(e),
                action=action,
            )

    async def _action_register(
        self,
        ctx: Context,
        name: str,
        source_code: str,
        version: Optional[str] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        capabilities: Optional[str] = None,
        parameters: Optional[str] = None,
        returns: Optional[str] = None,
        examples: Optional[str] = None,
        tags: Optional[str] = None,
        **_,
    ) -> str:
        """Register a new dynamic tool."""
        corrected_fields = {}

        try:
            # Parse JSON strings with optional auto-correction
            async def parse_json_field(field_name: str, json_str: Optional[str]):
                if not json_str:
                    return None
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    corrected = await self._attempt_json_correction(
                        ctx, field_name, json_str, str(e)
                    )
                    if corrected:
                        corrected_fields[field_name] = {
                            "original": json_str,
                            "corrected": corrected,
                        }
                        return json.loads(corrected)
                    raise

            capabilities_list = await parse_json_field("capabilities", capabilities)
            parameters_list = await parse_json_field("parameters", parameters)
            returns_dict = await parse_json_field("returns", returns)
            examples_list = await parse_json_field("examples", examples)
            tags_list = await parse_json_field("tags", tags)

            # Create and validate tool spec
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
                        logger.warning(f"Tool registration declined: {name} - {reason}")
                        log_tool_error(
                            "registration_declined", name, f"Consent denied: {reason}"
                        )
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"Tool registration declined: {reason}",
                                "tool_name": name,
                            }
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

            # Register with FastMCP first, then registry
            self._register_tool_with_fastmcp(spec)
            self.registry.register(spec)

            log_tool_registration(
                tool_name=name,
                version=version,
                author=author,
                capabilities=capabilities_list,
            )

            response = {
                "status": "success" if not corrected_fields else "success_corrected",
                "message": f"Tool '{name}' registered successfully",
                "tool_name": name,
                "version": version or "1.0.0",
            }

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

    async def _action_update(
        self,
        name: str,
        version: str,
        description: Optional[str] = None,
        capabilities: Optional[str] = None,
        parameters: Optional[str] = None,
        returns: Optional[str] = None,
        source_code: Optional[str] = None,
        examples: Optional[str] = None,
        tags: Optional[str] = None,
        **_,
    ) -> str:
        """Update an existing dynamic tool."""
        try:
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
                returns=json.loads(returns) if returns else existing_spec.returns,
                source_code=source_code or existing_spec.source_code,
                examples=json.loads(examples) if examples else existing_spec.examples,
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
                        logger.warning(f"Tool update declined: {name} - {reason}")
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

                except TimeoutError:
                    logger.error(f"Consent request timed out for tool update '{name}'")
                    log_tool_error("update_timeout", name, "Consent request timed out")
                    return json.dumps(
                        {
                            "status": "error",
                            "message": "Consent request timed out",
                            "tool_name": name,
                        }
                    )

            # Unregister old, register new (with rollback on failure)
            self._unregister_tool_from_fastmcp(name)
            try:
                self._register_tool_with_fastmcp(updated_spec)
            except Exception:
                self._register_tool_with_fastmcp(existing_spec)
                raise

            self.registry.update(updated_spec)

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

    async def _action_revoke(
        self,
        name: str,
        reason: Optional[str] = None,
        **_,
    ) -> str:
        """Revoke (delete) a dynamic tool."""
        try:
            spec = self.registry.get(name)
            if not spec:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"Tool '{name}' does not exist",
                    }
                )

            version = spec.version
            self.registry.revoke(name)
            self._unregister_tool_from_fastmcp(name)

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

    async def _action_list(
        self,
        tag: Optional[str] = None,
        capability: Optional[str] = None,
        author: Optional[str] = None,
        **_,
    ) -> str:
        """List all registered dynamic tools with optional filtering."""
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
                {
                    "status": "error",
                    "message": f"Failed to list tools: {e}",
                }
            )

    async def _action_inspect(self, name: str, **_) -> str:
        """Inspect a dynamic tool's complete specification."""
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
                {
                    "status": "success",
                    "tool": spec.to_dict(),
                },
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to inspect tool: {e}",
                }
            )

    async def _action_stats(self, **_) -> str:
        """Get statistics about the dynamic tool registry."""
        try:
            stats = self.registry.get_stats()
            return json.dumps(
                {
                    "status": "success",
                    "stats": stats,
                },
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to get stats: {e}",
                }
            )

    def _error_response(
        self,
        error: str,
        action: str = None,
        hint: str = None,
        valid_actions: list = None,
        missing: list = None,
        usage: str = None,
    ) -> List[TextContent]:
        """Build a structured error response."""
        response = {"error": error}
        if action:
            response["action"] = action
        if hint:
            response["hint"] = hint
        if valid_actions:
            response["valid_actions"] = valid_actions
        if missing:
            response["missing"] = missing
        if usage:
            response["usage"] = usage
        return [TextContent(type="text", text=json.dumps(response, indent=2))]
