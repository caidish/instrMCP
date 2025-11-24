"""Consent management for dynamic tool operations.

This module handles user consent for tool registration, updates, and execution.
Consent can be granted via:
1. Interactive dialog (comm channel to JupyterLab extension)
2. "Always allow" permissions stored in ~/.instrmcp/consents/always_allow.json
3. Bypass mode for testing (INSTRMCP_CONSENT_BYPASS=1)
"""

import logging
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ConsentManager:
    """Manages consent for dynamic tool operations."""

    def __init__(
        self,
        ipython=None,
        timeout_seconds: Optional[int] = None,
        persist_permissions: bool = False,
        bypass_mode: bool = False,
    ):
        """Initialize the consent manager.

        Args:
            ipython: IPython instance for comm channel communication
            timeout_seconds: Timeout for consent requests (default: None = infinite wait)
            persist_permissions: Whether to persist always_allow to disk (default: False = session-only)
            bypass_mode: If True, auto-approve all consent requests (dangerous mode)
        """
        self.ipython = ipython
        self.timeout_seconds = timeout_seconds
        self.persist_permissions = persist_permissions

        # Only set up persistence if enabled
        if persist_permissions:
            self.always_allow_path = (
                Path.home() / ".instrmcp" / "consents" / "always_allow.json"
            )
            self.always_allow_path.parent.mkdir(parents=True, exist_ok=True)
            # Load existing always_allow permissions
            self._always_allow: Dict[str, List[str]] = self._load_always_allow()
        else:
            # Session-only: start with empty permissions
            self.always_allow_path = None
            self._always_allow: Dict[str, List[str]] = {}

        # Check bypass mode - parameter takes precedence over env var
        self._bypass_mode = bypass_mode or (
            os.environ.get("INSTRMCP_CONSENT_BYPASS") == "1"
        )
        if self._bypass_mode:
            logger.warning(
                "⚠️  CONSENT BYPASS MODE ENABLED - All operations auto-approved!"
            )

        logger.debug(
            f"ConsentManager initialized: persist={persist_permissions}, timeout={timeout_seconds}s"
        )

    def _load_always_allow(self) -> Dict[str, List[str]]:
        """Load always_allow permissions from disk.

        Returns:
            Dict mapping author -> list of allowed operations
        """
        if not self.always_allow_path.exists():
            return {}

        try:
            with open(self.always_allow_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load always_allow permissions: {e}")
            return {}

    def _save_always_allow(self) -> None:
        """Save always_allow permissions to disk (only if persistence enabled)."""
        if not self.persist_permissions or self.always_allow_path is None:
            # Session-only mode: don't save to disk
            return

        try:
            with open(self.always_allow_path, "w") as f:
                json.dump(self._always_allow, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save always_allow permissions: {e}")

    def check_always_allow(self, author: str, operation: str = "register") -> bool:
        """Check if author has always_allow permission for operation.

        Args:
            author: Tool author
            operation: Operation type (register/update/execute)

        Returns:
            True if author has always_allow permission
        """
        if author not in self._always_allow:
            return False

        allowed_ops = self._always_allow[author]
        return operation in allowed_ops or "*" in allowed_ops

    def grant_always_allow(self, author: str, operation: str = "*") -> None:
        """Grant always_allow permission to an author.

        Args:
            author: Tool author
            operation: Operation type (default: * for all operations)
        """
        if author not in self._always_allow:
            self._always_allow[author] = []

        if operation not in self._always_allow[author]:
            self._always_allow[author].append(operation)
            self._save_always_allow()
            logger.debug(
                f"Granted always_allow to author '{author}' for operation '{operation}'"
            )

    def revoke_always_allow(self, author: str, operation: Optional[str] = None) -> None:
        """Revoke always_allow permission from an author.

        Args:
            author: Tool author
            operation: Specific operation to revoke (None = revoke all)
        """
        if author not in self._always_allow:
            return

        if operation is None:
            # Revoke all permissions for this author
            del self._always_allow[author]
            logger.debug(f"Revoked all always_allow permissions for author '{author}'")
        elif operation in self._always_allow[author]:
            # Revoke specific operation
            self._always_allow[author].remove(operation)
            if not self._always_allow[author]:
                del self._always_allow[author]
            logger.debug(
                f"Revoked always_allow for author '{author}' operation '{operation}'"
            )

        self._save_always_allow()

    async def request_consent(
        self,
        operation: str,
        tool_name: str,
        author: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Request user consent for a tool operation.

        Args:
            operation: Operation type (register/update/execute)
            tool_name: Name of the tool
            author: Tool author
            details: Additional details (source_code, capabilities, version, etc.)

        Returns:
            Dict with consent result:
            {
                "approved": bool,
                "always_allow": bool,  # True if user chose "Always Allow"
                "reason": str,         # Reason if declined
            }

        Raises:
            TimeoutError: If consent request times out
        """
        # Check bypass mode
        if self._bypass_mode:
            logger.debug(
                f"Consent bypassed for {operation} of tool '{tool_name}' by '{author}'"
            )
            return {"approved": True, "always_allow": False, "reason": "bypass_mode"}

        # Check always_allow permissions
        if self.check_always_allow(author, operation):
            logger.debug(
                f"Auto-approved {operation} of tool '{tool_name}' by '{author}' (always_allow)"
            )
            return {"approved": True, "always_allow": False, "reason": "always_allow"}

        # Check if IPython/comm is available
        if self.ipython is None:
            logger.warning("No IPython instance - cannot request consent interactively")
            return {
                "approved": False,
                "always_allow": False,
                "reason": "No IPython instance available for interactive consent",
            }

        # Send consent request via comm channel
        try:
            result = await self._send_consent_request(
                operation, tool_name, author, details
            )

            # If user granted always_allow, store it
            if result.get("always_allow") and result.get("approved"):
                self.grant_always_allow(author, operation)

            return result

        except TimeoutError:
            logger.error(
                f"Consent request timed out for {operation} of tool '{tool_name}'"
            )
            raise
        except Exception as e:
            logger.error(f"Consent request failed: {e}")
            return {
                "approved": False,
                "always_allow": False,
                "reason": f"Consent request failed: {e}",
            }

    async def _send_consent_request(
        self,
        operation: str,
        tool_name: str,
        author: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send consent request via comm channel and wait for response.

        Args:
            operation: Operation type
            tool_name: Tool name
            author: Tool author
            details: Tool details

        Returns:
            Consent result dict

        Raises:
            TimeoutError: If no response within timeout
        """
        # Try to get or create comm channel
        try:
            from ipykernel.comm import Comm

            # Create comm with target 'mcp:capcall'
            comm = Comm(target_name="mcp:capcall")

            # Prepare consent request message
            request_msg = {
                "type": "consent_request",
                "operation": operation,
                "tool_name": tool_name,
                "author": author,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "details": details,
            }

            # Create future for response
            response_future = asyncio.Future()

            # Set up message handler
            def on_msg(msg):
                """Handle response from frontend."""
                data = msg.get("content", {}).get("data", {})
                if data.get("type") == "consent_response":
                    if not response_future.done():
                        response_future.set_result(data)

            comm.on_msg(on_msg)

            # Send request
            comm.send(request_msg)
            logger.debug(
                f"Sent consent request for {operation} of tool '{tool_name}' by '{author}'"
            )

            # Wait for response with optional timeout
            try:
                if self.timeout_seconds is None:
                    # Wait indefinitely
                    response = await response_future
                else:
                    # Wait with timeout
                    response = await asyncio.wait_for(
                        response_future, timeout=self.timeout_seconds
                    )
                comm.close()

                return {
                    "approved": response.get("approved", False),
                    "always_allow": response.get("always_allow", False),
                    "reason": response.get("reason", "User response"),
                }
            except asyncio.TimeoutError:
                comm.close()
                raise TimeoutError(
                    f"Consent request timed out after {self.timeout_seconds} seconds"
                )

        except ImportError:
            logger.error("ipykernel.comm not available - cannot send consent request")
            return {
                "approved": False,
                "always_allow": False,
                "reason": "ipykernel.comm not available",
            }
        except Exception as e:
            logger.error(f"Failed to send consent request: {e}")
            raise

    def list_always_allow(self) -> Dict[str, List[str]]:
        """List all always_allow permissions.

        Returns:
            Dict mapping author -> list of allowed operations
        """
        return self._always_allow.copy()

    def clear_all_permissions(self) -> None:
        """Clear all always_allow permissions."""
        self._always_allow = {}
        self._save_always_allow()
        logger.debug("Cleared all always_allow permissions")
