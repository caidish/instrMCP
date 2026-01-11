"""Pre-AST scanner for IPython magic commands and shell escapes.

This module provides a FIRST line of defense against shell injection attacks
that bypass Python AST parsing. IPython magic commands like %%bash and shell
escapes like !command are processed by IPython before Python parsing, making
them invisible to the AST-based scanner.

Attack vectors detected:
1. Cell magics: %%bash, %%sh, %%script, %%ruby, %%perl, etc.
2. Shell escapes: !command, !!command
3. get_ipython().system() and similar IPython API calls
4. Dangerous shell commands: source of user config files, curl|bash, etc.

This scanner runs BEFORE the AST scanner and provides a hard security boundary
against shell-based injection attacks.
"""

import re
import logging
from typing import List, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IPythonRiskLevel(Enum):
    """Risk level for IPython-specific patterns."""

    MEDIUM = "medium"  # Warning, logged but not blocked by default
    HIGH = "high"  # Blocked by default
    CRITICAL = "critical"  # Always blocked, cannot be overridden


@dataclass
class IPythonSecurityIssue:
    """A detected IPython security issue."""

    rule_id: str
    description: str
    risk_level: IPythonRiskLevel
    line_number: int
    matched_code: str
    suggestion: str

    def to_dict(self) -> dict:
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
class IPythonScanResult:
    """Result of IPython magic scanning."""

    is_safe: bool
    issues: List[IPythonSecurityIssue]
    blocked: bool = False
    block_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_safe": self.is_safe,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "issue_count": len(self.issues),
            "issues": [i.to_dict() for i in self.issues],
        }


class IPythonScanner:
    """Scanner for IPython magic commands and shell escapes.

    This scanner uses regex-based detection (appropriate here since we're looking
    for specific syntactic patterns, not semantic analysis) to identify dangerous
    IPython-specific constructs that would bypass AST parsing.
    """

    # Cell magics that execute shell commands or other interpreters
    # These bypass Python entirely
    DANGEROUS_CELL_MAGICS: Set[str] = {
        "bash",
        "sh",
        "script",
        "ruby",
        "perl",
        "python",
        "python2",
        "python3",
        "pypy",
        "cmd",
        "powershell",
        "system",
    }

    # Cell magics that are suspicious but might have legitimate uses
    SUSPICIOUS_CELL_MAGICS: Set[str] = {
        "html",
        "javascript",
        "js",
        "svg",
        "latex",
    }

    # Dangerous shell commands that should never be executed
    DANGEROUS_SHELL_COMMANDS: Set[str] = {
        "source",  # Execute script in current shell
        "eval",  # Evaluate string as command
        "sudo",  # Privilege escalation
        "su",  # Switch user
        "chmod",  # Permission changes
        "chown",  # Ownership changes
        "rm -rf",  # Recursive forced deletion
    }

    # Patterns that indicate remote code execution or data exfiltration
    DANGEROUS_SHELL_PATTERNS: Set[str] = {
        "| bash",  # Pipe to bash (remote code execution)
        "| sh",  # Pipe to sh
        "|bash",  # No space variant
        "|sh",  # No space variant
        "curl ",  # curl command (data transfer)
        "wget ",  # wget command (data transfer)
        "/etc/passwd",  # Sensitive file access
        "/etc/shadow",  # Sensitive file access
        ".ssh/",  # SSH key access
    }

    # Dangerous config file patterns that should not be sourced
    DANGEROUS_SOURCE_PATTERNS: Set[str] = {
        ".bashrc",
        ".zshrc",
        ".profile",
        ".bash_profile",
        ".zprofile",
        "conda.sh",
        "activate",  # Virtual environment activation
        ".envrc",  # direnv config
        ".env",  # Environment files
    }

    def __init__(
        self,
        block_high_risk: bool = True,
        block_medium_risk: bool = False,
    ):
        """Initialize the IPython scanner.

        Args:
            block_high_risk: Whether to block HIGH risk patterns (default: True)
            block_medium_risk: Whether to block MEDIUM risk patterns (default: False)
        """
        self.block_high_risk = block_high_risk
        self.block_medium_risk = block_medium_risk

        # Compile regex patterns for efficiency
        self._cell_magic_pattern = re.compile(r"^\s*%%(\w+)", re.MULTILINE)
        self._line_magic_pattern = re.compile(r"^\s*%(\w+)", re.MULTILINE)
        self._shell_escape_pattern = re.compile(r"^\s*(!{1,2})\s*(.+)$", re.MULTILINE)
        self._get_ipython_pattern = re.compile(
            r"get_ipython\s*\(\s*\)\s*\.\s*(system|getoutput|run_line_magic|run_cell_magic)",
            re.IGNORECASE,
        )
        # Pattern for source command with path
        self._source_pattern = re.compile(
            r"(?:source|\.\s)\s+[\"']?([^\s\"']+)[\"']?", re.IGNORECASE
        )

        logger.debug(
            f"IPython Scanner initialized: "
            f"block_high={block_high_risk}, block_medium={block_medium_risk}"
        )

    def scan(self, code: str) -> IPythonScanResult:
        """Scan code for dangerous IPython patterns.

        Args:
            code: Code to scan (may include IPython magics)

        Returns:
            IPythonScanResult with detected issues and blocking decision
        """
        if not code or not code.strip():
            return IPythonScanResult(is_safe=True, issues=[])

        issues: List[IPythonSecurityIssue] = []

        # Check for dangerous cell magics
        issues.extend(self._check_cell_magics(code))

        # Check for shell escapes
        issues.extend(self._check_shell_escapes(code))

        # Check for get_ipython() bypass attempts
        issues.extend(self._check_get_ipython(code))

        # Log findings
        for issue in issues:
            logger.warning(
                f"[IPython] [{issue.risk_level.value.upper()}] {issue.rule_id}: "
                f"{issue.description} (line {issue.line_number})"
            )

        return self._build_result(issues)

    def _check_cell_magics(self, code: str) -> List[IPythonSecurityIssue]:
        """Check for dangerous cell magics."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            match = self._cell_magic_pattern.match(line)
            if match:
                magic_name = match.group(1).lower()

                if magic_name in self.DANGEROUS_CELL_MAGICS:
                    # Check the content of the cell magic for dangerous commands
                    cell_content = "\n".join(lines[i:])  # Content after the magic line

                    # Check for source commands in bash/sh cells
                    if magic_name in ("bash", "sh", "script"):
                        source_issues = self._check_source_commands(
                            cell_content, i, magic_name
                        )
                        issues.extend(source_issues)

                    # The cell magic itself is dangerous
                    issues.append(
                        IPythonSecurityIssue(
                            rule_id="IPYTHON001",
                            description=f"Dangerous cell magic: %%{magic_name}",
                            risk_level=IPythonRiskLevel.CRITICAL,
                            line_number=i,
                            matched_code=line.strip(),
                            suggestion=(
                                f"The %%{magic_name} cell magic executes shell commands "
                                f"directly, bypassing Python security controls. "
                                f"Use Python subprocess or os module instead."
                            ),
                        )
                    )

                elif magic_name in self.SUSPICIOUS_CELL_MAGICS:
                    issues.append(
                        IPythonSecurityIssue(
                            rule_id="IPYTHON002",
                            description=f"Suspicious cell magic: %%{magic_name}",
                            risk_level=IPythonRiskLevel.MEDIUM,
                            line_number=i,
                            matched_code=line.strip(),
                            suggestion=(
                                f"The %%{magic_name} magic can execute code in other "
                                f"contexts. Review carefully."
                            ),
                        )
                    )

        return issues

    def _check_source_commands(
        self, content: str, start_line: int, context: str
    ) -> List[IPythonSecurityIssue]:
        """Check for dangerous source commands within shell content."""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, start_line + 1):
            match = self._source_pattern.search(line)
            if match:
                source_path = match.group(1)

                # Check if sourcing a dangerous config file
                is_dangerous = any(
                    pattern in source_path for pattern in self.DANGEROUS_SOURCE_PATTERNS
                )

                # Also check for home directory patterns
                if source_path.startswith("~") or source_path.startswith("$HOME"):
                    is_dangerous = True

                if is_dangerous:
                    issues.append(
                        IPythonSecurityIssue(
                            rule_id="IPYTHON003",
                            description=(
                                f"Source command with config file in {context} context: "
                                f"{source_path}"
                            ),
                            risk_level=IPythonRiskLevel.CRITICAL,
                            line_number=i,
                            matched_code=line.strip(),
                            suggestion=(
                                f"Sourcing shell config files (like {source_path}) can "
                                f"execute arbitrary code. This is a common injection vector. "
                                f"Set environment variables directly in Python instead."
                            ),
                        )
                    )

        return issues

    def _check_shell_escapes(self, code: str) -> List[IPythonSecurityIssue]:
        """Check for shell escape commands (!command, !!command)."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            match = self._shell_escape_pattern.match(line)
            if match:
                escape_type = match.group(1)
                command = match.group(2).strip()

                # Check for source commands in shell escapes
                if self._source_pattern.search(command):
                    source_match = self._source_pattern.search(command)
                    if source_match:
                        source_path = source_match.group(1)
                        if any(
                            p in source_path for p in self.DANGEROUS_SOURCE_PATTERNS
                        ) or source_path.startswith(("~", "$HOME")):
                            issues.append(
                                IPythonSecurityIssue(
                                    rule_id="IPYTHON004",
                                    description=f"Source command via shell escape: {source_path}",
                                    risk_level=IPythonRiskLevel.CRITICAL,
                                    line_number=i,
                                    matched_code=line.strip(),
                                    suggestion=(
                                        "Shell escapes with source commands can execute "
                                        "arbitrary code from config files. Use Python "
                                        "os.environ directly."
                                    ),
                                )
                            )
                            continue

                # Check for other dangerous shell commands
                lower_command = command.lower()
                found_dangerous = False

                for dangerous_cmd in self.DANGEROUS_SHELL_COMMANDS:
                    if dangerous_cmd in lower_command:
                        issues.append(
                            IPythonSecurityIssue(
                                rule_id="IPYTHON005",
                                description=f"Dangerous shell command: {dangerous_cmd}",
                                risk_level=IPythonRiskLevel.HIGH,
                                line_number=i,
                                matched_code=line.strip(),
                                suggestion=(
                                    f"The command '{dangerous_cmd}' is potentially dangerous. "
                                    f"Consider using Python equivalents."
                                ),
                            )
                        )
                        found_dangerous = True
                        break

                # Check for dangerous patterns (RCE, data exfiltration)
                if not found_dangerous:
                    for pattern in self.DANGEROUS_SHELL_PATTERNS:
                        if pattern in lower_command:
                            issues.append(
                                IPythonSecurityIssue(
                                    rule_id="IPYTHON008",
                                    description=f"Dangerous shell pattern: {pattern.strip()}",
                                    risk_level=IPythonRiskLevel.CRITICAL,
                                    line_number=i,
                                    matched_code=line.strip()[:80],
                                    suggestion=(
                                        f"The pattern '{pattern.strip()}' indicates potential "
                                        f"remote code execution or data exfiltration. "
                                        f"Use Python libraries for network operations."
                                    ),
                                )
                            )
                            found_dangerous = True
                            break

                if not found_dangerous:
                    # General shell escape warning
                    issues.append(
                        IPythonSecurityIssue(
                            rule_id="IPYTHON006",
                            description=f"Shell escape: {escape_type}",
                            risk_level=IPythonRiskLevel.MEDIUM,
                            line_number=i,
                            matched_code=line.strip()[:60],
                            suggestion=(
                                "Shell escapes bypass Python security controls. "
                                "Use subprocess module for controlled execution."
                            ),
                        )
                    )

        return issues

    def _check_get_ipython(self, code: str) -> List[IPythonSecurityIssue]:
        """Check for get_ipython() bypass attempts."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            match = self._get_ipython_pattern.search(line)
            if match:
                method = match.group(1)
                issues.append(
                    IPythonSecurityIssue(
                        rule_id="IPYTHON007",
                        description=f"IPython API bypass: get_ipython().{method}()",
                        risk_level=IPythonRiskLevel.CRITICAL,
                        line_number=i,
                        matched_code=line.strip()[:80],
                        suggestion=(
                            f"Using get_ipython().{method}() bypasses security controls. "
                            f"Use standard Python APIs instead."
                        ),
                    )
                )

        return issues

    def _build_result(self, issues: List[IPythonSecurityIssue]) -> IPythonScanResult:
        """Build final result with blocking decision."""
        critical = [i for i in issues if i.risk_level == IPythonRiskLevel.CRITICAL]
        high = [i for i in issues if i.risk_level == IPythonRiskLevel.HIGH]
        medium = [i for i in issues if i.risk_level == IPythonRiskLevel.MEDIUM]

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

        result = IPythonScanResult(
            is_safe=is_safe,
            issues=issues,
            blocked=blocked,
            block_reason=block_reason,
        )

        if blocked:
            logger.error(f"[IPython] Code execution BLOCKED: {block_reason}")

        return result

    def get_rejection_message(self, result: IPythonScanResult) -> str:
        """Generate a clear rejection message for the AI agent."""
        if not result.blocked:
            return ""

        lines = [
            "EXECUTION BLOCKED - IPython Security Policy Violation",
            "",
            f"Reason: {result.block_reason}",
            "",
            "Detected issues:",
        ]

        for issue in result.issues:
            level_emoji = {
                IPythonRiskLevel.CRITICAL: "",
                IPythonRiskLevel.HIGH: "",
                IPythonRiskLevel.MEDIUM: "",
            }.get(issue.risk_level, "")

            lines.append(
                f"  {level_emoji} [{issue.risk_level.value.upper()}] {issue.description}"
            )
            lines.append(f"     Rule: {issue.rule_id}")
            lines.append(f"     Line {issue.line_number}: {issue.matched_code[:60]}")
            if issue.suggestion:
                lines.append(f"     {issue.suggestion}")
            lines.append("")

        lines.append(
            "This operation was rejected because it uses IPython features that "
            "bypass Python security controls. Please use standard Python code instead."
        )

        return "\n".join(lines)


# Global scanner instance
_default_ipython_scanner: Optional[IPythonScanner] = None


def get_default_ipython_scanner() -> IPythonScanner:
    """Get or create the default IPython scanner instance."""
    global _default_ipython_scanner
    if _default_ipython_scanner is None:
        _default_ipython_scanner = IPythonScanner()
    return _default_ipython_scanner


def scan_ipython(code: str) -> IPythonScanResult:
    """Convenience function to scan code with default scanner."""
    return get_default_ipython_scanner().scan(code)


def is_ipython_safe(code: str) -> bool:
    """Quick check if code has no dangerous IPython patterns."""
    result = scan_ipython(code)
    return not result.blocked
