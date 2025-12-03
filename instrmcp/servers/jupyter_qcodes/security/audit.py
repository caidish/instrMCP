"""Simple audit logging for dynamic tool lifecycle events.

This module provides basic logging for tool registrations, updates, and revocations.
We intentionally keep this simple and don't log every execution.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json


class AuditLogger:
    """Simple audit logger for tool lifecycle events."""

    def __init__(self, log_path: Optional[Path] = None):
        """Initialize the audit logger.

        Args:
            log_path: Path to audit log file (defaults to ~/.instrmcp/audit/tool_audit.log)
        """
        if log_path is None:
            log_path = Path.home() / ".instrmcp" / "audit" / "tool_audit.log"

        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure logger
        self.logger = logging.getLogger("instrmcp.audit")
        self.logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_path)
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_registration(
        self,
        tool_name: str,
        version: str,
        author: str,
        capabilities: list,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log tool registration event.

        Args:
            tool_name: Name of the tool
            version: Tool version
            author: Tool author
            capabilities: Required capabilities
            metadata: Additional metadata (optional)
        """
        event = {
            "event": "REGISTER",
            "tool_name": tool_name,
            "version": version,
            "author": author,
            "capabilities": capabilities,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if metadata:
            event["metadata"] = metadata

        self.logger.info(json.dumps(event))

    def log_update(
        self,
        tool_name: str,
        old_version: str,
        new_version: str,
        author: str,
        changes: Optional[str] = None,
    ) -> None:
        """Log tool update event.

        Args:
            tool_name: Name of the tool
            old_version: Previous version
            new_version: New version
            author: Tool author
            changes: Description of changes (optional)
        """
        event = {
            "event": "UPDATE",
            "tool_name": tool_name,
            "old_version": old_version,
            "new_version": new_version,
            "author": author,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if changes:
            event["changes"] = changes

        self.logger.info(json.dumps(event))

    def log_revocation(
        self, tool_name: str, version: str, reason: Optional[str] = None
    ) -> None:
        """Log tool revocation event.

        Args:
            tool_name: Name of the tool
            version: Tool version
            reason: Reason for revocation (optional)
        """
        event = {
            "event": "REVOKE",
            "tool_name": tool_name,
            "version": version,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if reason:
            event["reason"] = reason

        self.logger.info(json.dumps(event))

    def log_error(self, operation: str, tool_name: str, error: str) -> None:
        """Log an error during tool operations.

        Args:
            operation: Operation that failed (register/update/revoke)
            tool_name: Name of the tool
            error: Error message
        """
        event = {
            "event": "ERROR",
            "operation": operation,
            "tool_name": tool_name,
            "error": error,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        self.logger.error(json.dumps(event))


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Convenience functions for common operations
def log_tool_registration(
    tool_name: str,
    version: str,
    author: str,
    capabilities: list,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a tool registration event."""
    get_audit_logger().log_registration(
        tool_name, version, author, capabilities, metadata
    )


def log_tool_update(
    tool_name: str,
    old_version: str,
    new_version: str,
    author: str,
    changes: Optional[str] = None,
) -> None:
    """Log a tool update event."""
    get_audit_logger().log_update(tool_name, old_version, new_version, author, changes)


def log_tool_revocation(
    tool_name: str, version: str, reason: Optional[str] = None
) -> None:
    """Log a tool revocation event."""
    get_audit_logger().log_revocation(tool_name, version, reason)


def log_tool_error(operation: str, tool_name: str, error: str) -> None:
    """Log a tool operation error."""
    get_audit_logger().log_error(operation, tool_name, error)
