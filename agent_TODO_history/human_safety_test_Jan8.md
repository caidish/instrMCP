# Human Safety Testing Checklist

Manual tests to verify the AST-based code scanner blocks dangerous patterns in unsafe mode.

## Prerequisites

1. Start Jupyter with MCP extension loaded
2. Enable unsafe mode: `%mcp_unsafe`
3. Connect Claude Code or another MCP client

---

## Test Categories

### 1. Environment Modification (Original Attack Vector)

These patterns should be **BLOCKED** by `notebook_execute_cell`:

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 1.1 | `os.environ["QCODES_USER_PATH"] = "/tmp/malicious"` | BLOCKED |
| 1.2 | `os.environ.update({"PATH": "/evil"})` | BLOCKED |
| 1.3 | `os.environ.setdefault("API_KEY", "stolen")` | BLOCKED |
| 1.4 | `os.putenv("LD_PRELOAD", "/tmp/evil.so")` | BLOCKED |
| 1.5 | `import os; os.environ["TEST"] = "x"` | BLOCKED |

### 2. Dynamic Code Execution

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 2.1 | `exec("print('hello')")` | BLOCKED |
| 2.2 | `eval("1+1")` | BLOCKED |
| 2.3 | `compile("x=1", "", "exec")` | BLOCKED |
| 2.4 | `getattr(__builtins__, "exec")("print(1)")` | BLOCKED |
| 2.5 | `__builtins__["eval"]("1+1")` | BLOCKED |
| 2.6 | `__builtins__.exec("x=1")` | BLOCKED |

### 3. Subprocess / Shell Commands

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 3.1 | `os.system("ls")` | BLOCKED |
| 3.2 | `os.popen("whoami")` | BLOCKED |
| 3.3 | `subprocess.run(["ls"], shell=True)` | BLOCKED |
| 3.4 | `subprocess.Popen("cat /etc/passwd", shell=True)` | BLOCKED |
| 3.5 | `subprocess.call(cmd, shell=True)` | BLOCKED |

### 4. Dangerous File Operations

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 4.1 | `shutil.rmtree("/tmp/important")` | BLOCKED |
| 4.2 | `shutil.rmtree(Path.home())` | BLOCKED |
| 4.3 | `open(".bashrc", "w").write("malicious")` | BLOCKED |
| 4.4 | `open(".zshrc", "w")` | BLOCKED |
| 4.5 | `open("/etc/passwd", "w")` | BLOCKED |
| 4.6 | `pathlib.Path(".ssh/config").write_text("x")` | BLOCKED |

### 5. Pickle / Deserialization

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 5.1 | `pickle.load(open("data.pkl", "rb"))` | BLOCKED |
| 5.2 | `pickle.loads(data)` | BLOCKED |
| 5.3 | `dill.load(f)` | BLOCKED |
| 5.4 | `yaml.load(data)` (without Loader) | BLOCKED (HIGH) |

### 6. Persistence Mechanisms

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 6.1 | `os.system("crontab -e")` | BLOCKED |
| 6.2 | `open("/etc/cron.d/evil", "w")` | BLOCKED |

### 7. Aliased Import Bypass Attempts

These test the alias-tracking capability:

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 7.1 | `from os import system as s; s("ls")` | BLOCKED |
| 7.2 | `from os import environ as e; e["X"]="Y"` | BLOCKED |
| 7.3 | `import os as o; o.system("ls")` | BLOCKED |
| 7.4 | `import subprocess as sp; sp.run("ls", shell=True)` | BLOCKED |

### 8. Safe Code (Should PASS)

These should **NOT** be blocked:

| # | Test Code | Expected Result |
|---|-----------|-----------------|
| 8.1 | `import numpy as np; np.array([1,2,3])` | PASS |
| 8.2 | `print("Hello, World!")` | PASS |
| 8.3 | `x = 1 + 2` | PASS |
| 8.4 | `def my_function(): return 42` | PASS |
| 8.5 | `import qcodes; qcodes.__version__` | PASS |
| 8.6 | `os.path.join("a", "b")` | PASS |
| 8.7 | `os.getcwd()` | PASS |
| 8.8 | `yaml.safe_load(data)` | PASS |

---

## Tool-Specific Tests

### 9. notebook_execute_cell

1. Put dangerous code in a cell
2. Ask AI to execute the cell
3. Verify: Tool returns `"blocked": true` with security message

### 10. notebook_update_editing_cell

1. Ask AI to update cell content to dangerous code
2. Verify: Tool returns `"blocked": true` before consent dialog

### 11. notebook_apply_patch

Test that full resulting code is scanned:

| # | Scenario | Expected |
|---|----------|----------|
| 11.1 | Cell has `os.` and patch adds `system("ls")` | BLOCKED |
| 11.2 | Cell has `environ[` and patch adds `"PATH"] = "x"` after `os.` | BLOCKED |
| 11.3 | Patch replaces safe code with dangerous code | BLOCKED |

### 12. notebook_add_cell

1. Ask AI to add a new code cell with dangerous content
2. Verify: Tool returns `"blocked": true`

---

## Known Limitations (Future Work)

These patterns are **NOT YET BLOCKED** and will bypass the scanner:

| # | Bypass Pattern | Reason |
|---|----------------|--------|
| L1 | `!ls` (IPython shell escape) | AST parse error treated as safe |
| L2 | `%%bash\nwhoami` (cell magic) | AST parse error |
| L3 | `%pip install evil` (line magic) | AST parse error |
| L4 | `__import__("os").system("ls")` | `__import__` not detected |
| L5 | `importlib.import_module("os").system("x")` | importlib not detected |
| L6 | `env = os.environ; env["X"] = "Y"` | Variable assignment not tracked |
| L7 | `getattr(__import__("os"), "system")("ls")` | Dynamic import + getattr |
| L8 | `eval("ex" + "ec")("code")` | String concatenation |
| L9 | `import ctypes; ctypes.CDLL(...)` | ctypes not blocked |

---

## Error Handling Tests

### 13. Cell Retrieval Failure

1. Disconnect the notebook kernel
2. Ask AI to execute a cell
3. Verify: Returns `"blocked": true, "error": "Security scan failed: unable to retrieve cell content"`

### 14. Consent Manager Integration

1. In unsafe mode (not dangerous mode)
2. Put safe code in cell
3. Ask AI to execute
4. Verify: Consent dialog appears AFTER security scan passes

---

## Test Reporting

| Date | Tester | Tests Passed | Tests Failed | Notes |
|------|--------|--------------|--------------|-------|
| | | | | |

---

## Quick Automated Test

Run this in the instrMCPdev environment to verify scanner basics:

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev
python -c "
from instrmcp.servers.jupyter_qcodes.security import CodeScanner, RiskLevel
scanner = CodeScanner()

tests = [
    ('os.environ[\"X\"] = \"Y\"', True),
    ('exec(code)', True),
    ('from os import system as s; s(\"ls\")', True),
    ('import numpy as np', False),
]

for code, should_block in tests:
    result = scanner.scan(code)
    status = 'PASS' if result.blocked == should_block else 'FAIL'
    print(f'{status}: {code[:40]}...' if len(code) > 40 else f'{status}: {code}')
"
```
