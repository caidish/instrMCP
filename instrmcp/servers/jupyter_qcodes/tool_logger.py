"""Tool invocation logger for MCP server.

This module provides logging for all MCP tool invocations with:
- JSON Lines format for easy parsing
- Timing information for performance monitoring
- Argument sanitization (truncation of large values)
- Error tracking for failed calls
"""

import json
import logging
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

from instrmcp.logging_config import LOG_DIR, is_tool_logging_enabled

# Type variable for generic async functions
F = TypeVar("F", bound=Callable[..., Any])

# Tool calls log file
TOOL_CALLS_LOG = LOG_DIR / "tool_calls.log"

# Maximum length for argument values before truncation
MAX_ARG_LENGTH = 500


class ToolCallLogger:
    """Logger for MCP tool invocations.

    Logs tool calls in JSON Lines format with timing and status information.
    """

    def __init__(self, log_path: Optional[Path] = None):
        """Initialize the tool call logger.

        Args:
            log_path: Optional custom log file path.
        """
        self.log_path = log_path or TOOL_CALLS_LOG
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("instrmcp.tools.calls")
        self.logger.setLevel(logging.INFO)
        self._file_handler: Optional[logging.FileHandler] = None
        self._setup_handler()

    def _setup_handler(self) -> None:
        """Set up JSON file handler for tool calls."""
        # Avoid duplicate handlers
        if self._file_handler is not None:
            return

        self._file_handler = logging.FileHandler(self.log_path)
        self._file_handler.setLevel(logging.INFO)
        # Raw output - we format as JSON ourselves
        self._file_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(self._file_handler)

        # Don't propagate to parent loggers
        self.logger.propagate = False

    def log_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        duration_ms: float,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Log a tool invocation.

        Args:
            tool_name: Name of the tool that was called.
            args: Arguments passed to the tool.
            duration_ms: Execution time in milliseconds.
            status: "success" or "error".
            error: Error message if status is "error".
        """
        if not is_tool_logging_enabled():
            return

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "args": self._sanitize_args(args),
            "duration_ms": round(duration_ms, 2),
            "status": status,
        }
        if error:
            entry["error"] = error[:MAX_ARG_LENGTH]  # Truncate long errors

        try:
            self.logger.info(json.dumps(entry, default=str))
        except Exception:
            # Don't let logging errors break tool execution
            pass

    def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize arguments for logging (truncate large values).

        Args:
            args: Original arguments dictionary.

        Returns:
            Sanitized arguments with large values truncated.
        """
        sanitized = {}
        for k, v in args.items():
            if isinstance(v, str) and len(v) > MAX_ARG_LENGTH:
                sanitized[k] = v[:MAX_ARG_LENGTH] + "...[truncated]"
            elif isinstance(v, (dict, list)):
                # Convert to string and truncate if needed
                v_str = json.dumps(v, default=str)
                if len(v_str) > MAX_ARG_LENGTH:
                    sanitized[k] = v_str[:MAX_ARG_LENGTH] + "...[truncated]"
                else:
                    sanitized[k] = v
            else:
                sanitized[k] = v
        return sanitized


# Singleton instance
_tool_logger: Optional[ToolCallLogger] = None


def get_tool_logger() -> ToolCallLogger:
    """Get the global tool logger instance.

    Returns:
        The singleton ToolCallLogger instance.
    """
    global _tool_logger
    if _tool_logger is None:
        _tool_logger = ToolCallLogger()
    return _tool_logger


def logged_tool(tool_name: str) -> Callable[[F], F]:
    """Decorator to add logging to a tool function.

    Usage:
        @logged_tool("qcodes_instrument_info")
        async def instrument_info(...):
            ...

    Args:
        tool_name: Name to use in log entries.

    Returns:
        Decorator function.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000
                get_tool_logger().log_call(
                    tool_name=tool_name,
                    args=kwargs,
                    duration_ms=duration,
                    status="success",
                )
                return result
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                get_tool_logger().log_call(
                    tool_name=tool_name,
                    args=kwargs,
                    duration_ms=duration,
                    status="error",
                    error=str(e),
                )
                raise

        return wrapper  # type: ignore

    return decorator


def log_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    duration_ms: float,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Convenience function to log a tool call.

    Args:
        tool_name: Name of the tool.
        args: Arguments passed to the tool.
        duration_ms: Execution time in milliseconds.
        status: "success" or "error".
        error: Error message if status is "error".
    """
    get_tool_logger().log_call(tool_name, args, duration_ms, status, error)
