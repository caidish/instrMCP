"""AST-based code pattern scanner for detecting dangerous operations.

This module scans Python code using Abstract Syntax Tree (AST) analysis to detect
potentially dangerous patterns before execution. Unlike regex-based scanning,
AST analysis can detect aliased imports, builtins access, and other obfuscation
techniques.

The scanner runs BEFORE consent dialogs - it's a hard security boundary that prevents
dangerous code from even reaching the user approval step.

Key features:
- Alias-aware detection (catches `from os import system as s; s(...)`)
- Builtins access detection (`getattr(__builtins__, "eval")`)
- Environment modification detection (original attack vector)
- Dangerous file operation detection
- IPython magic and shell escape detection (%%bash, !source, etc.)
- Optional Bandit integration for additional coverage

Security Architecture:
1. IPython Scanner (pre-AST) - catches %%bash, !command, get_ipython() bypasses
2. AST Scanner - catches Python-level dangerous patterns
Both must pass for code to be considered safe.
"""

import ast
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from .ipython_scanner import (
    IPythonScanner,
    IPythonScanResult,
    get_default_ipython_scanner,
)

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level for detected patterns."""

    LOW = "low"  # Informational, logged but not blocked
    MEDIUM = "medium"  # Warning, may be blocked based on configuration
    HIGH = "high"  # Blocked by default
    CRITICAL = "critical"  # Always blocked, cannot be overridden


@dataclass
class SecurityIssue:
    """A detected security issue in code."""

    rule_id: str
    description: str
    risk_level: RiskLevel
    line_number: int
    matched_code: str
    suggestion: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "level": self.risk_level.value,
            "line": self.line_number,
            "code": self.matched_code[:100]
            + ("..." if len(self.matched_code) > 100 else ""),
            "suggestion": self.suggestion,
        }


@dataclass
class ScanResult:
    """Result of scanning code for dangerous patterns."""

    is_safe: bool
    issues: List[SecurityIssue] = field(default_factory=list)
    blocked: bool = False
    block_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_safe": self.is_safe,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "issue_count": len(self.issues),
            "issues": [i.to_dict() for i in self.issues],
        }


class AliasTracker(ast.NodeVisitor):
    """Tracks import aliases throughout the AST.

    This visitor builds a mapping of aliases to their original module/name,
    allowing other visitors to resolve aliased references.
    """

    def __init__(self):
        self.aliases: Dict[str, str] = {}  # alias -> original
        self.module_aliases: Dict[str, str] = {}  # alias -> module

    def visit_Import(self, node: ast.Import):
        """Track `import x as y` aliases."""
        for alias in node.names:
            if alias.asname:
                self.module_aliases[alias.asname] = alias.name
            else:
                self.module_aliases[alias.name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track `from x import y as z` aliases."""
        module = node.module or ""
        for alias in node.names:
            full_name = f"{module}.{alias.name}" if module else alias.name
            if alias.asname:
                self.aliases[alias.asname] = full_name
            else:
                self.aliases[alias.name] = full_name
        self.generic_visit(node)

    def resolve(self, name: str) -> str:
        """Resolve an alias to its original name."""
        return self.aliases.get(name, self.module_aliases.get(name, name))

    def is_from_module(self, name: str, module: str) -> bool:
        """Check if a name is imported from a specific module."""
        resolved = self.resolve(name)
        return resolved.startswith(module + ".") or resolved == module


class BaseSecurityVisitor(ast.NodeVisitor):
    """Base class for security-focused AST visitors."""

    def __init__(self, alias_tracker: AliasTracker):
        self.alias_tracker = alias_tracker
        self.issues: List[SecurityIssue] = []

    def add_issue(
        self,
        rule_id: str,
        description: str,
        risk_level: RiskLevel,
        node: ast.AST,
        suggestion: str,
    ):
        """Add a security issue."""
        try:
            matched_code = ast.unparse(node)
        except Exception:
            matched_code = "<unparseable>"

        self.issues.append(
            SecurityIssue(
                rule_id=rule_id,
                description=description,
                risk_level=risk_level,
                line_number=getattr(node, "lineno", 0),
                matched_code=matched_code,
                suggestion=suggestion,
            )
        )

    def get_call_name(self, node: ast.Call) -> Tuple[Optional[str], Optional[str]]:
        """Get the (object, method) or (None, function) name from a Call node."""
        if isinstance(node.func, ast.Attribute):
            # obj.method()
            if isinstance(node.func.value, ast.Name):
                obj = self.alias_tracker.resolve(node.func.value.id)
                return (obj, node.func.attr)
            elif isinstance(node.func.value, ast.Attribute):
                # obj.attr.method() - e.g., os.environ.update()
                return (ast.unparse(node.func.value), node.func.attr)
        elif isinstance(node.func, ast.Name):
            # function()
            return (None, self.alias_tracker.resolve(node.func.id))
        return (None, None)


class ExecEvalVisitor(BaseSecurityVisitor):
    """Detect exec/eval calls including via builtins and getattr."""

    # Names that provide access to exec/eval
    DANGEROUS_NAMES = {"exec", "eval", "compile"}
    BUILTINS_NAMES = {"__builtins__", "builtins"}

    def visit_Call(self, node: ast.Call):
        """Detect direct and indirect exec/eval calls."""
        obj, method = self.get_call_name(node)

        # Direct exec()/eval() call
        if method in self.DANGEROUS_NAMES and obj is None:
            self.add_issue(
                "EXEC001",
                f"Direct {method}() call detected",
                RiskLevel.CRITICAL,
                node,
                f"Dynamic code execution with {method}() is not allowed.",
            )

        # builtins.exec() / builtins.eval()
        elif obj in self.BUILTINS_NAMES and method in self.DANGEROUS_NAMES:
            self.add_issue(
                "EXEC002",
                f"Builtins access to {method}() detected",
                RiskLevel.CRITICAL,
                node,
                f"Access to {method}() via builtins is not allowed.",
            )

        # Check for getattr(__builtins__, "exec") patterns
        if method == "getattr" and len(node.args) >= 2:
            # First arg should be __builtins__ or builtins
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Name) and first_arg.id in self.BUILTINS_NAMES:
                # Second arg should be a string containing dangerous name
                second_arg = node.args[1]
                if (
                    isinstance(second_arg, ast.Constant)
                    and second_arg.value in self.DANGEROUS_NAMES
                ):
                    self.add_issue(
                        "EXEC003",
                        f"getattr() access to {second_arg.value}() via builtins",
                        RiskLevel.CRITICAL,
                        node,
                        "Accessing exec/eval via getattr on builtins is not allowed.",
                    )

        # Check for globals()["exec"] or locals()["eval"]
        if isinstance(node.func, ast.Subscript):
            if isinstance(node.func.value, ast.Call):
                inner_obj, inner_method = self.get_call_name(node.func.value)
                if inner_method in ("globals", "locals"):
                    if isinstance(node.func.slice, ast.Constant):
                        if node.func.slice.value in self.DANGEROUS_NAMES:
                            self.add_issue(
                                "EXEC004",
                                f"{inner_method}()['{node.func.slice.value}'] access detected",
                                RiskLevel.CRITICAL,
                                node,
                                f"Accessing {node.func.slice.value} via {inner_method}() is not allowed.",
                            )

        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        """Detect __builtins__["exec"] patterns."""
        if isinstance(node.value, ast.Name) and node.value.id in self.BUILTINS_NAMES:
            if (
                isinstance(node.slice, ast.Constant)
                and node.slice.value in self.DANGEROUS_NAMES
            ):
                self.add_issue(
                    "EXEC005",
                    f"__builtins__['{node.slice.value}'] subscript access",
                    RiskLevel.CRITICAL,
                    node,
                    "Subscript access to exec/eval via __builtins__ is not allowed.",
                )
        self.generic_visit(node)


class EnvModificationVisitor(BaseSecurityVisitor):
    """Detect os.environ modifications - the original attack vector."""

    ENV_METHODS = {"update", "setdefault", "pop", "clear", "popitem"}

    def visit_Subscript(self, node: ast.Subscript):
        """Detect os.environ[...] = ... assignments."""
        if isinstance(node.ctx, ast.Store):
            if self._is_environ(node.value):
                self.add_issue(
                    "ENV001",
                    "Environment variable assignment detected",
                    RiskLevel.CRITICAL,
                    node,
                    "Environment variables should not be modified by AI agents. "
                    "This could redirect data paths or compromise system configuration.",
                )
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete):
        """Detect del os.environ[...] statements."""
        for target in node.targets:
            if isinstance(target, ast.Subscript) and self._is_environ(target.value):
                self.add_issue(
                    "ENV002",
                    "Environment variable deletion detected",
                    RiskLevel.CRITICAL,
                    target,
                    "Deleting environment variables is not allowed.",
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Detect os.environ.update(), os.putenv(), os.unsetenv(), etc."""
        obj, method = self.get_call_name(node)

        # os.environ.update/setdefault/pop/clear
        if method in self.ENV_METHODS:
            if isinstance(node.func, ast.Attribute):
                if self._is_environ(node.func.value):
                    self.add_issue(
                        "ENV003",
                        f"Environment modification via environ.{method}()",
                        RiskLevel.CRITICAL,
                        node,
                        f"Use of environ.{method}() is not allowed.",
                    )

        # os.putenv() / os.unsetenv()
        if method in ("putenv", "unsetenv"):
            if obj and ("os" in obj or self.alias_tracker.is_from_module(method, "os")):
                self.add_issue(
                    "ENV004",
                    f"Environment modification via {method}()",
                    RiskLevel.CRITICAL,
                    node,
                    f"Use of {method}() is not allowed.",
                )
            elif obj is None:
                # Might be `from os import putenv; putenv(...)`
                resolved = self.alias_tracker.resolve(method)
                if "os.putenv" in resolved or "os.unsetenv" in resolved:
                    self.add_issue(
                        "ENV004",
                        f"Environment modification via {method}()",
                        RiskLevel.CRITICAL,
                        node,
                        f"Use of {method}() is not allowed.",
                    )

        self.generic_visit(node)

    def _is_environ(self, node: ast.AST) -> bool:
        """Check if node refers to os.environ."""
        if isinstance(node, ast.Attribute):
            if node.attr == "environ":
                if isinstance(node.value, ast.Name):
                    resolved = self.alias_tracker.resolve(node.value.id)
                    return "os" in resolved
        elif isinstance(node, ast.Name):
            resolved = self.alias_tracker.resolve(node.id)
            return "environ" in resolved or resolved == "os.environ"
        return False


class SubprocessVisitor(BaseSecurityVisitor):
    """Detect subprocess and os.system calls."""

    OS_DANGEROUS = {
        "system",
        "popen",
        "spawn",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
    }
    SUBPROCESS_FUNCS = {"run", "call", "check_call", "check_output", "Popen"}

    def visit_Call(self, node: ast.Call):
        """Detect dangerous process execution calls."""
        obj, method = self.get_call_name(node)

        # Resolve alias if method is aliased (e.g., from os import system as s)
        resolved_method = self.alias_tracker.resolve(method) if method else method

        # os.system(), os.popen(), os.spawn*(), os.exec*()
        # Check both direct method name and resolved alias
        method_to_check = method
        if resolved_method and resolved_method.startswith("os."):
            # Extract the actual function name from os.xxx
            method_to_check = resolved_method.split(".")[-1]

        if method_to_check in self.OS_DANGEROUS:
            if obj and "os" in obj:
                self.add_issue(
                    "PROC001",
                    f"System command execution via os.{method_to_check}()",
                    RiskLevel.CRITICAL,
                    node,
                    "Direct system command execution is not allowed.",
                )
            elif obj is None:
                # Either direct call or aliased import
                self.add_issue(
                    "PROC001",
                    f"System command execution via {method}() (resolved: {resolved_method})",
                    RiskLevel.CRITICAL,
                    node,
                    "Direct system command execution is not allowed.",
                )

        # subprocess.run(), subprocess.Popen(), etc.
        if method in self.SUBPROCESS_FUNCS:
            if obj and "subprocess" in obj:
                # Check for shell=True
                shell_true = self._has_shell_true(node)
                if shell_true:
                    self.add_issue(
                        "PROC002",
                        f"Subprocess with shell=True: subprocess.{method}()",
                        RiskLevel.CRITICAL,
                        node,
                        "Subprocess with shell=True is a shell injection risk.",
                    )
                else:
                    self.add_issue(
                        "PROC003",
                        f"Subprocess execution: subprocess.{method}()",
                        RiskLevel.HIGH,
                        node,
                        "Subprocess execution requires careful review.",
                    )

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Warn on subprocess import."""
        for alias in node.names:
            if alias.name == "subprocess":
                self.add_issue(
                    "PROC004",
                    "subprocess module imported",
                    RiskLevel.MEDIUM,
                    node,
                    "subprocess module import detected - use with caution.",
                )
        self.generic_visit(node)

    def _has_shell_true(self, node: ast.Call) -> bool:
        """Check if a Call node has shell=True."""
        for keyword in node.keywords:
            if keyword.arg == "shell":
                if (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    return True
                elif (
                    isinstance(keyword.value, ast.NameConstant)
                    and keyword.value.value is True
                ):
                    return True
        return False


class DangerousFileOpsVisitor(BaseSecurityVisitor):
    """Detect dangerous file operations."""

    PROTECTED_PATHS = {"/etc/", "/var/", "/usr/", "/bin/", "/sbin/"}
    HOME_CONFIG_PATTERNS = {
        ".bashrc",
        ".zshrc",
        ".profile",
        ".bash_profile",
        ".config/",
        ".local/",
        ".ssh/",
    }
    WRITE_MODES = {"w", "a", "x", "w+", "a+", "x+", "wb", "ab", "xb", "r+", "rb+"}

    def visit_Call(self, node: ast.Call):
        """Detect dangerous file operation calls."""
        obj, method = self.get_call_name(node)

        # shutil.rmtree()
        if method == "rmtree" and obj and "shutil" in obj:
            self.add_issue(
                "FILE001",
                "Recursive directory deletion: shutil.rmtree()",
                RiskLevel.CRITICAL,
                node,
                "Recursive deletion is too dangerous.",
            )

        # shutil.move/copy to protected paths
        if method in ("move", "copy", "copy2", "copytree") and obj and "shutil" in obj:
            if len(node.args) >= 2:
                dst = node.args[1]
                if self._is_protected_path(dst):
                    self.add_issue(
                        "FILE002",
                        f"File operation to protected path: shutil.{method}()",
                        RiskLevel.HIGH,
                        node,
                        "File operations to system paths are restricted.",
                    )

        # open() with write mode to protected paths
        if method == "open" or (obj is None and method == "open"):
            if node.args:
                path_arg = node.args[0]
                mode = self._get_open_mode(node)
                if mode and any(m in mode for m in self.WRITE_MODES):
                    if self._is_protected_path(path_arg):
                        self.add_issue(
                            "FILE003",
                            "Write to protected path via open()",
                            RiskLevel.CRITICAL,
                            node,
                            "Writing to system/config paths is not allowed.",
                        )

        # Path.write_text/write_bytes
        if method in ("write_text", "write_bytes"):
            if isinstance(node.func, ast.Attribute):
                path_node = node.func.value
                if self._is_protected_path(path_node):
                    self.add_issue(
                        "FILE004",
                        f"Write to protected path via Path.{method}()",
                        RiskLevel.CRITICAL,
                        node,
                        "Writing to system/config paths is not allowed.",
                    )

        # Path.unlink/rmdir
        if method in ("unlink", "rmdir"):
            self.add_issue(
                "FILE005",
                f"File/directory deletion via Path.{method}()",
                RiskLevel.MEDIUM,
                node,
                "File deletion detected - verify this is intentional.",
            )

        # os.chmod/chown on protected paths
        if method in ("chmod", "chown") and obj and "os" in obj:
            if node.args:
                if self._is_protected_path(node.args[0]):
                    self.add_issue(
                        "FILE006",
                        f"Permission change on protected path: os.{method}()",
                        RiskLevel.HIGH,
                        node,
                        "Changing permissions on system paths is restricted.",
                    )

        self.generic_visit(node)

    def _get_open_mode(self, node: ast.Call) -> Optional[str]:
        """Extract the mode argument from an open() call."""
        # Check positional arg
        if len(node.args) >= 2:
            mode_arg = node.args[1]
            if isinstance(mode_arg, ast.Constant):
                return str(mode_arg.value)
        # Check keyword arg
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
        return None

    def _is_protected_path(self, node: ast.AST) -> bool:
        """Check if a node represents a protected path."""
        try:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                path = node.value
                # Check system paths
                for protected in self.PROTECTED_PATHS:
                    if path.startswith(protected):
                        return True
                # Check home config patterns
                for pattern in self.HOME_CONFIG_PATTERNS:
                    if pattern in path:
                        return True
                # Check for ~ expansion
                if path.startswith("~"):
                    for pattern in self.HOME_CONFIG_PATTERNS:
                        if pattern in path:
                            return True
            elif isinstance(node, ast.JoinedStr):
                # f-string - check parts
                for value in node.values:
                    if isinstance(value, ast.Constant):
                        if any(p in str(value.value) for p in self.PROTECTED_PATHS):
                            return True
                        if any(
                            p in str(value.value) for p in self.HOME_CONFIG_PATTERNS
                        ):
                            return True
        except Exception:
            pass
        return False


class PersistenceVisitor(BaseSecurityVisitor):
    """Detect persistence mechanisms (crontab, systemd, etc.)."""

    PERSISTENCE_PATTERNS = {"crontab", "systemctl", "launchctl", "at", "schtasks"}

    def visit_Call(self, node: ast.Call):
        """Detect persistence-related calls."""
        obj, method = self.get_call_name(node)

        # subprocess calls with persistence commands
        if method in ("run", "call", "check_call", "check_output", "Popen", "system"):
            if node.args:
                first_arg = node.args[0]
                if self._contains_persistence_command(first_arg):
                    self.add_issue(
                        "PERSIST001",
                        "Persistence mechanism detected",
                        RiskLevel.CRITICAL,
                        node,
                        "Setting up scheduled tasks or services is not allowed.",
                    )

        self.generic_visit(node)

    def _contains_persistence_command(self, node: ast.AST) -> bool:
        """Check if node contains persistence commands."""
        try:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for pattern in self.PERSISTENCE_PATTERNS:
                    if pattern in node.value:
                        return True
            elif isinstance(node, ast.List):
                for elt in node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        for pattern in self.PERSISTENCE_PATTERNS:
                            if pattern in elt.value:
                                return True
        except Exception:
            pass
        return False


class ThreadingVisitor(BaseSecurityVisitor):
    """Detect Python threading usage which crashes Qt/MeasureIt.

    MeasureIt uses Qt internally. Qt objects cannot be safely used across
    Python threads created with threading.Thread, threading.Timer, or
    concurrent.futures.ThreadPoolExecutor. This causes Qt threading
    violations that crash the Jupyter kernel.

    CORRECT usage:
        sweep.start()  # Already non-blocking, runs in Qt's thread internally
        # Then use measureit_wait_for_sweep() to monitor completion

    WRONG usage (crashes kernel):
        t = threading.Thread(target=sweep.start)
        t.start()

        # Also wrong:
        timer = threading.Timer(1.0, sweep.start)
        executor = ThreadPoolExecutor(); executor.submit(sweep.start)
    """

    # Thread-creating classes that crash Qt/MeasureIt
    THREAD_CREATORS = {"Thread", "Timer"}  # threading module
    EXECUTOR_CLASSES = {"ThreadPoolExecutor"}  # concurrent.futures

    def visit_Call(self, node: ast.Call):
        """Detect thread-creating class instantiation."""
        obj, method = self.get_call_name(node)

        # Detect threading.Thread(...) or threading.Timer(...)
        if method in self.THREAD_CREATORS:
            is_threading = False

            # threading.Thread() or threading.Timer() - resolve aliases first
            if obj:
                resolved_obj = self.alias_tracker.resolve(obj)
                if "threading" in resolved_obj:
                    is_threading = True
            # from threading import Thread/Timer; Thread()/Timer()
            else:
                resolved = self.alias_tracker.resolve(method)
                if "threading" in resolved:
                    is_threading = True

            if is_threading:
                self.add_issue(
                    "THREAD001",
                    f"threading.{method}() usage detected - crashes Qt/MeasureIt",
                    RiskLevel.CRITICAL,
                    node,
                    f"NEVER use threading.{method} with MeasureIt. "
                    "sweep.start() is already non-blocking. "
                    "Use measureit_wait_for_sweep() to monitor completion.",
                )

        # Detect concurrent.futures.ThreadPoolExecutor(...)
        if method in self.EXECUTOR_CLASSES:
            is_executor = False

            # concurrent.futures.ThreadPoolExecutor() - resolve aliases first
            if obj:
                resolved_obj = self.alias_tracker.resolve(obj)
                if "concurrent" in resolved_obj or "futures" in resolved_obj:
                    is_executor = True
            # from concurrent.futures import ThreadPoolExecutor; ThreadPoolExecutor()
            else:
                resolved = self.alias_tracker.resolve(method)
                if "concurrent" in resolved or "futures" in resolved:
                    is_executor = True

            if is_executor:
                self.add_issue(
                    "THREAD004",
                    "ThreadPoolExecutor usage detected - crashes Qt/MeasureIt",
                    RiskLevel.CRITICAL,
                    node,
                    "NEVER use ThreadPoolExecutor with MeasureIt. "
                    "sweep.start() is already non-blocking. "
                    "Use measureit_wait_for_sweep() to monitor completion.",
                )

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Warn on threading and concurrent.futures imports."""
        for alias in node.names:
            if alias.name == "threading":
                self.add_issue(
                    "THREAD002",
                    "threading module imported - may crash Qt/MeasureIt if misused",
                    RiskLevel.HIGH,
                    node,
                    "Do NOT use threading.Thread/Timer with MeasureIt sweeps. "
                    "sweep.start() is already non-blocking.",
                )
            # Also warn on concurrent.futures import
            elif alias.name in ("concurrent.futures", "concurrent"):
                self.add_issue(
                    "THREAD006",
                    "concurrent.futures module imported - may crash Qt/MeasureIt",
                    RiskLevel.HIGH,
                    node,
                    "Do NOT use ThreadPoolExecutor with MeasureIt sweeps. "
                    "sweep.start() is already non-blocking.",
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Warn on from threading/concurrent.futures import dangerous classes."""
        if node.module == "threading":
            for alias in node.names:
                # Handle star import: from threading import *
                if alias.name == "*":
                    self.add_issue(
                        "THREAD007",
                        "Star import from threading - crashes Qt/MeasureIt",
                        RiskLevel.HIGH,
                        node,
                        "Do NOT use 'from threading import *'. "
                        "This imports Thread/Timer which crash with MeasureIt.",
                    )
                elif alias.name in self.THREAD_CREATORS:
                    self.add_issue(
                        "THREAD003",
                        f"{alias.name} imported from threading - crashes Qt/MeasureIt",
                        RiskLevel.HIGH,
                        node,
                        f"Do NOT use {alias.name} with MeasureIt sweeps. "
                        "sweep.start() is already non-blocking.",
                    )
        # concurrent.futures.ThreadPoolExecutor
        if node.module == "concurrent.futures":
            for alias in node.names:
                # Handle star import: from concurrent.futures import *
                if alias.name == "*":
                    self.add_issue(
                        "THREAD008",
                        "Star import from concurrent.futures - crashes Qt/MeasureIt",
                        RiskLevel.HIGH,
                        node,
                        "Do NOT use 'from concurrent.futures import *'. "
                        "This imports ThreadPoolExecutor which crashes with MeasureIt.",
                    )
                elif alias.name in self.EXECUTOR_CLASSES:
                    self.add_issue(
                        "THREAD005",
                        "ThreadPoolExecutor imported - crashes Qt/MeasureIt",
                        RiskLevel.HIGH,
                        node,
                        "Do NOT use ThreadPoolExecutor with MeasureIt sweeps. "
                        "sweep.start() is already non-blocking.",
                    )
        self.generic_visit(node)


class PickleVisitor(BaseSecurityVisitor):
    """Detect pickle deserialization (arbitrary code execution risk)."""

    DANGEROUS_FUNCS = {"load", "loads", "Unpickler"}

    def visit_Call(self, node: ast.Call):
        """Detect pickle.load/loads calls."""
        obj, method = self.get_call_name(node)

        if method in self.DANGEROUS_FUNCS:
            if obj and any(m in obj for m in ("pickle", "cPickle", "dill", "shelve")):
                self.add_issue(
                    "PICKLE001",
                    f"Pickle deserialization: {obj}.{method}()",
                    RiskLevel.CRITICAL,
                    node,
                    "Pickle deserialization can execute arbitrary code.",
                )

        # yaml.load without Loader
        if method == "load" and obj and "yaml" in obj:
            # Check if Loader is specified
            has_loader = any(kw.arg == "Loader" for kw in node.keywords)
            if not has_loader and len(node.args) < 2:
                self.add_issue(
                    "PICKLE002",
                    "yaml.load() without explicit Loader",
                    RiskLevel.HIGH,
                    node,
                    "Use yaml.safe_load() or specify Loader explicitly.",
                )

        self.generic_visit(node)


class CodeScanner:
    """Combined security scanner for Python and IPython code.

    This scanner combines two layers of defense:
    1. IPython Scanner (pre-AST) - Detects %%bash, !command, get_ipython() bypasses
    2. AST Scanner - Detects Python-level dangerous patterns

    Both scanners must pass for code to be considered safe.
    """

    def __init__(
        self,
        block_high_risk: bool = True,
        block_medium_risk: bool = False,
        ipython_scanner: Optional[IPythonScanner] = None,
    ):
        """Initialize the code scanner.

        Args:
            block_high_risk: Whether to block HIGH risk patterns (default: True)
            block_medium_risk: Whether to block MEDIUM risk patterns (default: False)
            ipython_scanner: Optional IPython scanner. If None, uses default scanner.
        """
        self.block_high_risk = block_high_risk
        self.block_medium_risk = block_medium_risk
        self.ipython_scanner = ipython_scanner or get_default_ipython_scanner()

        logger.debug(
            f"CodeScanner initialized (AST + IPython): "
            f"block_high={block_high_risk}, block_medium={block_medium_risk}"
        )

    def scan(self, code: str) -> ScanResult:
        """Scan code for security issues using IPython and AST analysis.

        This method runs TWO layers of security scanning:
        1. IPython Scanner - Detects %%bash, !command, get_ipython() bypasses
        2. AST Scanner - Detects Python-level dangerous patterns

        Args:
            code: Python/IPython code to scan

        Returns:
            ScanResult with detected issues and blocking decision
        """
        if not code or not code.strip():
            return ScanResult(is_safe=True)

        # LAYER 1: IPython Scanner - Run FIRST to catch shell injection attacks
        # This catches %%bash, !source ~/.zshrc, get_ipython().system(), etc.
        ipython_result = self.ipython_scanner.scan(code)
        if ipython_result.blocked:
            # Convert IPython result to ScanResult format
            logger.error(f"IPython scan BLOCKED: {ipython_result.block_reason}")
            ipython_issues = [
                SecurityIssue(
                    rule_id=issue.rule_id,
                    description=issue.description,
                    risk_level=RiskLevel.CRITICAL,  # IPython bypasses are always critical
                    line_number=issue.line_number,
                    matched_code=issue.matched_code,
                    suggestion=issue.suggestion,
                )
                for issue in ipython_result.issues
            ]
            return ScanResult(
                is_safe=False,
                issues=ipython_issues,
                blocked=True,
                block_reason=f"[IPython] {ipython_result.block_reason}",
            )

        # LAYER 2: AST Scanner - Parse Python code
        # Note: Code with IPython magics (%%bash) may fail to parse as Python,
        # but we've already checked for dangerous magics above.
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            # Code may contain non-Python syntax (like %%bash content after the magic).
            # If IPython scanner passed, we check if this is just a cell magic body.
            # If the code starts with %% it's a cell magic and the "body" isn't Python.
            if code.strip().startswith("%%"):
                # IPython scanner already approved - the magic itself is safe
                # The body content is shell/other language, not Python to analyze
                logger.debug(
                    f"Non-Python cell magic body, IPython scanner approved: {e.msg}"
                )
                return ScanResult(is_safe=True)
            # Regular Python syntax error - can't execute anyway
            logger.debug(f"Syntax error in code (line {e.lineno}): {e.msg}")
            return ScanResult(is_safe=True)

        # Build alias tracker first
        alias_tracker = AliasTracker()
        alias_tracker.visit(tree)

        # Run all security visitors
        all_issues: List[SecurityIssue] = []
        visitors = [
            ExecEvalVisitor(alias_tracker),
            EnvModificationVisitor(alias_tracker),
            SubprocessVisitor(alias_tracker),
            DangerousFileOpsVisitor(alias_tracker),
            PersistenceVisitor(alias_tracker),
            PickleVisitor(alias_tracker),
            ThreadingVisitor(alias_tracker),
        ]

        for visitor in visitors:
            visitor.visit(tree)
            all_issues.extend(visitor.issues)

        # Log findings
        for issue in all_issues:
            logger.warning(
                f"⚠️  [{issue.risk_level.value.upper()}] {issue.rule_id}: "
                f"{issue.description} (line {issue.line_number})"
            )

        # Build result with blocking decision
        return self._build_result(all_issues)

    def _build_result(self, issues: List[SecurityIssue]) -> ScanResult:
        """Build final result with blocking decision."""
        critical = [i for i in issues if i.risk_level == RiskLevel.CRITICAL]
        high = [i for i in issues if i.risk_level == RiskLevel.HIGH]
        medium = [i for i in issues if i.risk_level == RiskLevel.MEDIUM]

        blocked = False
        block_reason = None

        if critical:
            blocked = True
            block_reason = (
                f"CRITICAL: {critical[0].description}. {critical[0].suggestion}"
            )
        elif high and self.block_high_risk:
            blocked = True
            block_reason = f"HIGH: {high[0].description}. {high[0].suggestion}"
        elif medium and self.block_medium_risk:
            blocked = True
            block_reason = f"MEDIUM: {medium[0].description}. {medium[0].suggestion}"

        is_safe = len(issues) == 0

        result = ScanResult(
            is_safe=is_safe,
            issues=issues,
            blocked=blocked,
            block_reason=block_reason,
        )

        if blocked:
            logger.error(f"🚫 Code execution BLOCKED: {block_reason}")

        return result

    def get_rejection_message(self, scan_result: ScanResult) -> str:
        """Generate a clear rejection message for the AI agent.

        Args:
            scan_result: Result from scan()

        Returns:
            Human-readable rejection message
        """
        if not scan_result.blocked:
            return ""

        lines = [
            "🚫 EXECUTION BLOCKED - Security Policy Violation",
            "",
            f"Reason: {scan_result.block_reason}",
            "",
            "Detected issues:",
        ]

        for issue in scan_result.issues:
            level_emoji = {
                RiskLevel.CRITICAL: "🔴",
                RiskLevel.HIGH: "🟠",
                RiskLevel.MEDIUM: "🟡",
                RiskLevel.LOW: "🟢",
            }.get(issue.risk_level, "⚪")

            lines.append(
                f"  {level_emoji} [{issue.risk_level.value.upper()}] {issue.description}"
            )
            lines.append(f"     Rule: {issue.rule_id}")
            lines.append(f"     Line {issue.line_number}: {issue.matched_code[:60]}")
            if issue.suggestion:
                lines.append(f"     💡 {issue.suggestion}")
            lines.append("")

        lines.append(
            "This operation was rejected by the MCP server security policy. "
            "Please modify your approach to avoid these patterns."
        )

        return "\n".join(lines)


# Global scanner instance with default settings
_default_scanner: Optional[CodeScanner] = None


def get_default_scanner() -> CodeScanner:
    """Get or create the default code scanner instance."""
    global _default_scanner
    if _default_scanner is None:
        _default_scanner = CodeScanner()
    return _default_scanner


def scan_code(code: str) -> ScanResult:
    """Convenience function to scan code with default scanner."""
    return get_default_scanner().scan(code)


def is_code_safe(code: str) -> bool:
    """Quick check if code is safe to execute."""
    result = scan_code(code)
    return not result.blocked
