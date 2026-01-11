"""Security components for dynamic tool system."""

from .audit import (
    AuditLogger,
    log_tool_registration,
    log_tool_update,
    log_tool_revocation,
)
from .consent import ConsentManager
from .code_scanner import (
    CodeScanner,
    ScanResult,
    SecurityIssue,
    RiskLevel,
    scan_code,
    is_code_safe,
    get_default_scanner,
)
from .ipython_scanner import (
    IPythonScanner,
    IPythonScanResult,
    IPythonSecurityIssue,
    IPythonRiskLevel,
    scan_ipython,
    is_ipython_safe,
    get_default_ipython_scanner,
)

__all__ = [
    # Audit
    "AuditLogger",
    "log_tool_registration",
    "log_tool_update",
    "log_tool_revocation",
    # Consent
    "ConsentManager",
    # Code Scanner (combined AST + IPython)
    "CodeScanner",
    "ScanResult",
    "SecurityIssue",
    "RiskLevel",
    "scan_code",
    "is_code_safe",
    "get_default_scanner",
    # IPython Scanner (for direct access if needed)
    "IPythonScanner",
    "IPythonScanResult",
    "IPythonSecurityIssue",
    "IPythonRiskLevel",
    "scan_ipython",
    "is_ipython_safe",
    "get_default_ipython_scanner",
]
