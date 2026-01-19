# Security Scanner Refactoring Plan

## Overview

This document outlines the plan to refactor the instrMCP code security scanner from regex-based detection to AST-based detection using Bandit and custom AST visitors.

## Problem Statement

The current regex-based scanner in `instrmcp/servers/jupyter_qcodes/security/code_scanner.py` has critical vulnerabilities:

1. **Bypass via aliasing**: `from os import system; system(...)` evades detection
2. **Bypass via builtins**: `getattr(__builtins__, "eval")(...)` evades detection
3. **False positives**: Comments and docstrings trigger false matches
4. **Integration flaws**: `execute_cell` continues if cell retrieval fails; `apply_patch` only scans fragments

## Current State vs. Proposed State

| Aspect | Current (Regex) | Proposed (AST + Bandit) |
|--------|-----------------|-------------------------|
| Detection method | String matching | AST node analysis |
| Aliased imports | Bypassable | Detected |
| Comments/strings | False positives | Ignored |
| Maintenance | Manual patterns | Bandit's proven rules |

---

## Phase 1: Bandit Rules to Apply

### CRITICAL - Always Block (B6xx Injection)

| Bandit ID | What it Detects | Our Use Case |
|-----------|-----------------|--------------|
| **B102** | `exec()` used | Block dynamic code execution |
| **B307** | `eval()` used | Block dynamic evaluation |
| **B602** | `subprocess.Popen(shell=True)` | Block shell injection |
| **B603** | `subprocess` without shell | Warn (less dangerous) |
| **B605** | `os.system()`, `os.popen()` | Block system commands |
| **B606** | `os.spawn*`, `os.exec*` | Block process spawning |
| **B607** | Subprocess with partial path | Block path injection |

### HIGH - Block by Default (Deserialization & Network)

| Bandit ID | What it Detects | Our Use Case |
|-----------|-----------------|--------------|
| **B301** | `pickle.loads()` | Block arbitrary code via pickle |
| **B403** | `import pickle` | Warn about pickle usage |
| **B401** | `import telnetlib` | Block insecure protocols |
| **B402** | `import ftplib` | Block insecure protocols |
| **B506** | `yaml.load()` without Loader | Block YAML code execution |

### MEDIUM - Warn Only (Potential Issues)

| Bandit ID | What it Detects | Our Use Case |
|-----------|-----------------|--------------|
| **B404** | `import subprocess` | Warn (context-dependent) |
| **B108** | Hardcoded `/tmp` paths | Warn about temp file risks |
| **B110** | `try: ... except: pass` | Warn (swallowing errors) |

---

## Phase 2: Custom AST Rules (Bandit Doesn't Cover)

These require custom implementation because Bandit doesn't detect them.

### CRITICAL - Custom Rules

| Rule Name | Detection Pattern | Reason |
|-----------|-------------------|--------|
| `env_modification` | `os.environ[x] = y`, `os.environ.update()`, `os.putenv()` | Redirect measurement paths (original attack vector) |
| `env_deletion` | `del os.environ[x]`, `os.unsetenv()` | Can break application state |
| `rmtree` | `shutil.rmtree()` | Recursive deletion too dangerous |
| `shell_config` | Writes to `.bashrc`, `.zshrc`, `.profile` | Persistence mechanism |

### HIGH - Custom Rules

| Rule Name | Detection Pattern | Reason |
|-----------|-------------------|--------|
| `system_paths` | Access to `/etc/`, `/var/`, `/usr/` | System modification |
| `home_config` | Writes to `~/.config/`, `~/.local/` | User config modification |
| `crontab_systemd` | `crontab`, `systemctl`, `launchctl` | Scheduled task persistence |

### MEDIUM - Custom Rules

| Rule Name | Detection Pattern | Reason |
|-----------|-------------------|--------|
| `path_unlink` | `Path.unlink()`, `Path.rmdir()` | File deletion (pathlib) |
| `network_requests` | `requests.*`, `httpx.*`, `aiohttp.*` | Data exfiltration risk |
| `dynamic_import` | `__import__()`, `importlib.import_module()` | Obfuscation technique |

---

## Phase 3: Architecture

### Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    CodeScanner                          │
├─────────────────────────────────────────────────────────┤
│  1. Parse code → AST (catch syntax errors)              │
│  2. Run Bandit checks on AST                            │
│  3. Run custom AST visitors for env/file/network        │
│  4. Aggregate results with risk levels                  │
│  5. Return ScanResult with blocking decision            │
└─────────────────────────────────────────────────────────┘
```

### Proposed Code Structure

```python
# code_scanner.py (refactored)

import ast
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityIssue:
    rule_id: str
    description: str
    risk_level: RiskLevel
    line_number: int
    matched_code: str
    suggestion: str

class CodeScanner:
    def __init__(
        self,
        block_high_risk: bool = True,
        block_medium_risk: bool = False,
    ):
        # Bandit rules to apply
        self.bandit_rules = [
            "B102", "B307",  # exec/eval
            "B602", "B605", "B606", "B607",  # subprocess/os.system
            "B301", "B506",  # pickle/yaml
            "B401", "B402",  # telnet/ftp
        ]

        # Custom AST visitors for rules Bandit doesn't cover
        self.custom_visitors = [
            EnvModificationVisitor(),  # os.environ changes
            DangerousFileOpsVisitor(), # rmtree, system paths
            ShellConfigVisitor(),      # .bashrc, etc.
            NetworkExfiltrationVisitor(), # requests, httpx, etc.
        ]

        self.block_high_risk = block_high_risk
        self.block_medium_risk = block_medium_risk

    def scan(self, code: str) -> ScanResult:
        """Scan code for security issues using AST analysis."""

        # 1. Parse to AST
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Can't execute invalid Python code
            return ScanResult(is_safe=True)

        issues: List[SecurityIssue] = []

        # 2. Run Bandit checks
        bandit_issues = self._run_bandit_checks(code, tree)
        issues.extend(bandit_issues)

        # 3. Run custom AST visitors
        for visitor in self.custom_visitors:
            visitor_issues = visitor.visit(tree)
            issues.extend(visitor_issues)

        # 4. Determine blocking decision
        return self._build_result(issues)

    def _run_bandit_checks(self, code: str, tree: ast.AST) -> List[SecurityIssue]:
        """Run Bandit security checks against the AST."""
        # Implementation uses bandit.core APIs
        pass

    def _build_result(self, issues: List[SecurityIssue]) -> ScanResult:
        """Build final result with blocking decision."""
        critical = [i for i in issues if i.risk_level == RiskLevel.CRITICAL]
        high = [i for i in issues if i.risk_level == RiskLevel.HIGH]
        medium = [i for i in issues if i.risk_level == RiskLevel.MEDIUM]

        blocked = False
        block_reason = None

        if critical:
            blocked = True
            block_reason = f"CRITICAL: {critical[0].description}"
        elif high and self.block_high_risk:
            blocked = True
            block_reason = f"HIGH: {high[0].description}"
        elif medium and self.block_medium_risk:
            blocked = True
            block_reason = f"MEDIUM: {medium[0].description}"

        return ScanResult(
            is_safe=len(issues) == 0,
            blocked=blocked,
            block_reason=block_reason,
            issues=issues,
        )
```

### Custom AST Visitor Example

```python
class EnvModificationVisitor(ast.NodeVisitor):
    """Detect os.environ modifications."""

    def __init__(self):
        self.issues: List[SecurityIssue] = []

    def visit_Subscript(self, node: ast.Subscript):
        """Detect os.environ[...] = ..."""
        # Check if this is os.environ[x] = y
        if self._is_environ_subscript(node):
            # Check if it's being assigned to
            if isinstance(node.ctx, ast.Store):
                self.issues.append(SecurityIssue(
                    rule_id="ENV001",
                    description="Environment variable modification detected",
                    risk_level=RiskLevel.CRITICAL,
                    line_number=node.lineno,
                    matched_code=ast.unparse(node),
                    suggestion="Environment variables should not be modified by AI agents.",
                ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Detect os.environ.update(), os.putenv(), etc."""
        if self._is_environ_update(node) or self._is_putenv(node):
            self.issues.append(SecurityIssue(
                rule_id="ENV002",
                description="Environment modification via function call",
                risk_level=RiskLevel.CRITICAL,
                line_number=node.lineno,
                matched_code=ast.unparse(node),
                suggestion="Use of os.putenv/environ.update is not allowed.",
            ))
        self.generic_visit(node)

    def _is_environ_subscript(self, node: ast.Subscript) -> bool:
        """Check if node is os.environ[...]"""
        if isinstance(node.value, ast.Attribute):
            if node.value.attr == "environ":
                # Could be os.environ or imported environ
                return True
        elif isinstance(node.value, ast.Name):
            if node.value.id == "environ":
                return True
        return False

    def _is_environ_update(self, node: ast.Call) -> bool:
        """Check if node is os.environ.update(...)"""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "update":
                if isinstance(node.func.value, ast.Attribute):
                    return node.func.value.attr == "environ"
        return False

    def _is_putenv(self, node: ast.Call) -> bool:
        """Check if node is os.putenv(...)"""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr == "putenv"
        elif isinstance(node.func, ast.Name):
            return node.func.id == "putenv"
        return False

    def visit(self, tree: ast.AST) -> List[SecurityIssue]:
        """Visit tree and return all issues found."""
        self.issues = []
        super().visit(tree)
        return self.issues
```

---

## Phase 4: Fix Integration Issues

### Issue 1: `execute_cell` Bypass on Exception

**Current (vulnerable):**
```python
try:
    cell_info = await self.tools.get_editing_cell()
    cell_content = cell_info.get("text", "")
    rejection = self._scan_and_reject(cell_content, "notebook_execute_cell")
    if rejection:
        return rejection
except Exception as e:
    logger.error(f"Error getting cell content for security scan: {e}")
    # BUG: Continues execution without scan!
    cell_content = ""
    cell_info = {}
```

**Fixed:**
```python
try:
    cell_info = await self.tools.get_editing_cell()
    cell_content = cell_info.get("text", "")
except Exception as e:
    logger.error(f"CRITICAL: Cannot retrieve cell for security scan: {e}")
    return [TextContent(
        type="text",
        text=json.dumps({
            "success": False,
            "error": "Security scan failed: unable to retrieve cell content",
        }, indent=2)
    )]

# Scan runs only after successful retrieval
rejection = self._scan_and_reject(cell_content, "notebook_execute_cell")
if rejection:
    return rejection
```

### Issue 2: `apply_patch` Scans Fragment Only

**Current (vulnerable):**
```python
# Only scans new_text, not the resulting code!
rejection = self._scan_and_reject(new_text, "notebook_apply_patch")
```

**Fixed:**
```python
# Get current cell content
try:
    cell_info = await self.tools.get_editing_cell()
    current_content = cell_info.get("text", "")
except Exception as e:
    return [TextContent(type="text", text=json.dumps({
        "success": False, "error": "Cannot retrieve cell for patch"
    }, indent=2))]

# Apply patch in memory to get resulting code
patched_content = current_content.replace(old_text, new_text, 1)

# Scan the FULL resulting code
rejection = self._scan_and_reject(patched_content, "notebook_apply_patch")
if rejection:
    return rejection
```

---

## Phase 5: Rule Coverage Summary

| Category | Bandit Rules | Custom Rules | Total |
|----------|-------------|--------------|-------|
| Code Execution | 6 | 0 | 6 |
| Environment Modification | 0 | 3 | 3 |
| File System Dangers | 1 | 4 | 5 |
| Network/Exfiltration | 2 | 2 | 4 |
| Deserialization | 3 | 0 | 3 |
| Persistence Mechanisms | 0 | 2 | 2 |
| **Total** | **12** | **11** | **23** |

---

## Dependencies

```toml
# pyproject.toml additions
[project.optional-dependencies]
security = [
    "bandit>=1.7.0",
]
```

---

## Open Questions

1. **Blocking defaults**: Should MEDIUM risks (like `import subprocess`) be blocked or just warned?

2. **Network blocking**: Should we block all `requests.*` calls, or only in certain contexts?

3. **File operations**: Should `open(..., 'w')` be blocked, or is that too restrictive for normal notebook use?

4. **Bandit dependency**: Is adding `bandit` as a dependency acceptable?

---

## Implementation Checklist

- [ ] Add `bandit` to optional dependencies
- [ ] Refactor `code_scanner.py` to use AST parsing
- [ ] Implement Bandit integration for standard rules
- [ ] Implement `EnvModificationVisitor` (CRITICAL - original attack vector)
- [ ] Implement `DangerousFileOpsVisitor` (rmtree, system paths)
- [ ] Implement `ShellConfigVisitor` (.bashrc, .profile, etc.)
- [ ] Implement `NetworkExfiltrationVisitor` (requests, httpx, etc.)
- [ ] Fix `execute_cell` exception handling bypass
- [ ] Fix `apply_patch` to scan full resulting code
- [ ] Add comprehensive unit tests
- [ ] Update ARCHITECTURE.md documentation
- [ ] Update README.md with security features

---

## Codex Review Findings (2025-01-08)

### Critical Issues Identified

| Severity | Issue | Recommendation |
|----------|-------|----------------|
| **CRITICAL** | Bandit B102/B307 won't catch `getattr(__builtins__, "eval")`, `builtins.exec`, or aliased imports like `from builtins import eval as e` | Add custom visitor that resolves `__builtins__`, `builtins`, `getattr`/`.__getattribute__`, and import aliases for `eval`/`exec` |
| **HIGH** | Shell invocation incomplete: missing B604 ("any function with shell=True"), also need to cover `subprocess.run/call/check_output` with `shell=True` and aliasing | Add B604 to Bandit rules; add custom visitor to enforce `shell=False` |
| **HIGH** | Env/file custom rules miss aliases: `from os import environ as env`, `os.environ.setdefault/clear/pop`, `putenv` via alias, `os.unsetenv`, `pathlib.Path(...).write_text/write_bytes` | Expand alias tracking for imports/attributes; include common write/delete APIs |
| **HIGH** | System/home path protection underspecified: detecting "access to /etc" should focus on *writes* not just attribute access | Focus on write operations: `open()` with write mode, `Path.write_*`, `chmod`, `chown`, `mkdir`, `symlink` |
| **MEDIUM** | Network rule likely noisy/weak: import-based detection floods results; calls via aliases (`from requests import post as p`) not covered | Use call-level detection with alias resolution; consider optional allowlist (e.g., localhost) |
| **MEDIUM** | `apply_patch` reconstruction: `str.replace()` can target wrong span (duplicates, whitespace); may miss patches that don't apply | Reuse actual patch application logic (difflib or notebook server's helper) to produce post-patch buffer |
| **MEDIUM** | Bandit integration needs explicit config: limit tests to allowed list to avoid unexpected rules; use pseudo-filename for consistent line numbers | Instantiate `BanditManager` with explicit config; map Bandit severities correctly |
| **LOW** | Risk policy clarity: `is_safe=False` for any issue even if not blocked | Clarify whether "warn-only" findings should mark cells unsafe or just surface in UI |

### Additional Rules Required

Based on review, add these to the plan:

#### Bandit Rules to Add

| Bandit ID | What it Detects | Priority |
|-----------|-----------------|----------|
| **B604** | Any function with `shell=True` | HIGH |

#### Custom Visitors to Add

| Visitor | Purpose | Priority |
|---------|---------|----------|
| `BuiltinsExecEvalVisitor` | Detect `builtins.exec`, `getattr(__builtins__, "eval")`, import aliases | CRITICAL |
| `AliasTrackingVisitor` | Track import aliases across all rules | CRITICAL |
| `WriteOperationVisitor` | Detect writes to protected paths (not just access) | HIGH |

### Expanded Detection Patterns

#### Environment Modification (Complete List)

```python
# Must detect ALL of these:
os.environ["KEY"] = "value"           # Direct assignment
os.environ.update({"KEY": "value"})   # Bulk update
os.environ.setdefault("KEY", "value") # Conditional set
os.environ.pop("KEY")                 # Remove
os.environ.clear()                    # Clear all
del os.environ["KEY"]                 # Delete
os.putenv("KEY", "value")             # C-level set
os.unsetenv("KEY")                    # C-level unset

# ALSO with aliases:
from os import environ as env
env["KEY"] = "value"

from os import putenv
putenv("KEY", "value")
```

#### Builtins Access (New - CRITICAL)

```python
# Must detect ALL of these:
exec("code")                          # Direct
eval("expr")                          # Direct
builtins.exec("code")                 # Via builtins module
builtins.eval("expr")                 # Via builtins module
__builtins__["exec"]("code")          # Via __builtins__ dict
__builtins__.exec("code")             # Via __builtins__ attr
getattr(__builtins__, "exec")("code") # Via getattr
getattr(builtins, "eval")("expr")     # Via getattr on module
globals()["exec"]("code")             # Via globals
locals()["eval"]("expr")              # Via locals

# With aliases:
from builtins import exec as e
e("code")
```

#### Write Operations to Protected Paths

```python
# Must detect writes (not reads) to:
# - /etc/*, /var/*, /usr/*
# - ~/.bashrc, ~/.zshrc, ~/.profile, ~/.bash_profile
# - ~/.config/*, ~/.local/*

# Detection patterns:
open("/etc/passwd", "w")              # open with write mode
open("/etc/passwd", "a")              # open with append mode
Path("/etc/hosts").write_text(...)    # pathlib write
Path("/etc/hosts").write_bytes(...)   # pathlib write bytes
Path("~/.bashrc").expanduser().write_text(...)  # home expansion
shutil.copy(src, "/etc/target")       # copy to protected
shutil.move(src, "/etc/target")       # move to protected
os.chmod("/etc/file", 0o777)          # permission change
os.chown("/etc/file", uid, gid)       # ownership change
os.symlink(src, "/etc/link")          # symlink creation
os.mkdir("/etc/newdir")               # directory creation
```

---

## Updated Implementation Checklist

- [ ] Add `bandit` to optional dependencies
- [ ] Refactor `code_scanner.py` to use AST parsing
- [ ] Implement Bandit integration with explicit config (limit to allowed rules)
- [ ] **NEW**: Add B604 to Bandit rules (shell=True detection)
- [ ] **NEW**: Implement `AliasTrackingVisitor` (track import aliases)
- [ ] **NEW**: Implement `BuiltinsExecEvalVisitor` (builtins/getattr bypass)
- [ ] Implement `EnvModificationVisitor` (CRITICAL - expand to all patterns)
- [ ] Implement `DangerousFileOpsVisitor` (rmtree, system paths)
- [ ] **NEW**: Implement `WriteOperationVisitor` (focus on writes, not access)
- [ ] Implement `ShellConfigVisitor` (.bashrc, .profile, etc.)
- [ ] Implement `NetworkExfiltrationVisitor` (call-level, not import-level)
- [ ] Fix `execute_cell` exception handling bypass
- [ ] Fix `apply_patch` to use proper patch reconstruction (not str.replace)
- [ ] Add comprehensive unit tests
- [ ] Update ARCHITECTURE.md documentation
- [ ] Update README.md with security features

---

## References

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Bandit GitHub](https://github.com/PyCQA/bandit)
- [Python AST Documentation](https://docs.python.org/3/library/ast.html)
- [OWASP Code Injection](https://owasp.org/www-community/attacks/Code_Injection)
