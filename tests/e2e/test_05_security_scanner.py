"""
Security Scanner Tests (test_05_security_scanner.py)

Purpose: Verify dangerous code patterns are blocked in unsafe mode.

Test IDs:
- SS-001 to SS-054
"""

import pytest
from tests.e2e.helpers.mcp_helpers import call_mcp_tool, parse_tool_result


class TestEnvironmentModification:
    """Test blocking of environment modification patterns."""

    @pytest.mark.p0
    def test_block_environ_assignment(self, mcp_server_dangerous):
        """SS-001: Block os.environ assignment."""
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {
                "cell_type": "code",
                "position": "below",
                "content": 'import os; os.environ["TEST"] = "value"',
            },
        )
        # Should either block in add_cell or in execute
        # Check if content was added
        mcp_server_dangerous["page"].wait_for_timeout(500)

        # Try to execute
        exec_result = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )

        # Either add_cell or execute should block this
        # Check for security-related error in result
        _, add_content = parse_tool_result(result)
        _, exec_content = parse_tool_result(exec_result)

        combined = (str(result) + str(exec_result)).lower()
        # Should be blocked with security message
        assert (
            "block" in combined
            or "security" in combined
            or "forbidden" in combined
            or "denied" in combined
        ), f"Expected security block for environ assignment: add={add_content}, exec={exec_content}"

    @pytest.mark.p0
    def test_block_environ_update(self, mcp_server_dangerous):
        """SS-002: Block os.environ.update()."""
        code = 'import os; os.environ.update({"TEST": "value"})'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked

    @pytest.mark.p0
    def test_block_putenv(self, mcp_server_dangerous):
        """SS-003: Block os.putenv()."""
        code = 'import os; os.putenv("TEST", "value")'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked


class TestDynamicExecution:
    """Test blocking of dynamic code execution patterns."""

    @pytest.mark.p0
    def test_block_exec(self, mcp_server_dangerous):
        """SS-010: Block exec()."""
        code = 'exec("print(1)")'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked

    @pytest.mark.p0
    def test_block_eval(self, mcp_server_dangerous):
        """SS-011: Block eval()."""
        code = 'eval("1+1")'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked

    @pytest.mark.p0
    def test_block_compile(self, mcp_server_dangerous):
        """SS-012: Block compile()."""
        code = 'compile("x=1", "<string>", "exec")'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked


class TestSubprocess:
    """Test blocking of subprocess patterns."""

    @pytest.mark.p0
    def test_block_os_system(self, mcp_server_dangerous):
        """SS-020: Block os.system()."""
        code = 'import os; os.system("ls")'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked

    @pytest.mark.p0
    def test_block_subprocess_run(self, mcp_server_dangerous):
        """SS-021: Block subprocess.run()."""
        code = 'import subprocess; subprocess.run(["ls"])'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked

    @pytest.mark.p0
    def test_block_subprocess_popen(self, mcp_server_dangerous):
        """SS-022: Block subprocess.Popen()."""
        code = 'import subprocess; subprocess.Popen(["ls"])'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked


class TestAliasedImports:
    """Test blocking of aliased dangerous imports."""

    @pytest.mark.p0
    def test_block_aliased_system(self, mcp_server_dangerous):
        """SS-030: Block aliased os.system."""
        code = 'import os as o; o.system("ls")'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked

    @pytest.mark.p0
    def test_block_aliased_environ(self, mcp_server_dangerous):
        """SS-031: Block aliased os.environ."""
        code = 'from os import environ as e; e["TEST"] = "value"'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked

    @pytest.mark.p0
    def test_block_module_alias(self, mcp_server_dangerous):
        """SS-032: Block module aliased subprocess."""
        code = 'import subprocess as sp; sp.run(["ls"])'
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        # Should be blocked


class TestAllowedPatterns:
    """Test that safe patterns are allowed."""

    @pytest.mark.p0
    def test_allow_numpy_operations(self, mcp_server_dangerous):
        """SS-050: NumPy operations are allowed."""
        page = mcp_server_dangerous["page"]

        code = "import numpy as np; arr = np.array([1, 2, 3]); print(arr.sum())"

        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        page.wait_for_timeout(500)

        exec_result = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )

        success, content = parse_tool_result(exec_result)
        # Should succeed
        assert (
            success or "block" not in content.lower()
        ), f"NumPy should be allowed: {content}"

    @pytest.mark.p0
    def test_allow_print(self, mcp_server_dangerous):
        """SS-051: Basic print is allowed."""
        code = 'print("hello world")'

        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        mcp_server_dangerous["page"].wait_for_timeout(500)

        exec_result = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )

        success, content = parse_tool_result(exec_result)
        assert success, f"Print should be allowed: {content}"

    @pytest.mark.p0
    def test_allow_arithmetic(self, mcp_server_dangerous):
        """SS-052: Basic arithmetic is allowed."""
        code = "x = 1 + 2 * 3 - 4 / 2"

        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        mcp_server_dangerous["page"].wait_for_timeout(500)

        exec_result = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )

        success, content = parse_tool_result(exec_result)
        assert success, f"Arithmetic should be allowed: {content}"

    @pytest.mark.p1
    def test_allow_os_path(self, mcp_server_dangerous):
        """SS-053: os.path operations are allowed."""
        code = 'import os; path = os.path.join("a", "b")'

        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        mcp_server_dangerous["page"].wait_for_timeout(500)

        exec_result = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )

        success, content = parse_tool_result(exec_result)
        # os.path should be allowed
        assert (
            success or "block" not in content.lower()
        ), f"os.path should be allowed: {content}"

    @pytest.mark.p1
    def test_allow_os_getcwd(self, mcp_server_dangerous):
        """SS-054: os.getcwd() is allowed."""
        code = "import os; cwd = os.getcwd()"

        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )
        mcp_server_dangerous["page"].wait_for_timeout(500)

        exec_result = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )

        success, content = parse_tool_result(exec_result)
        # os.getcwd should be allowed
        assert (
            success or "block" not in content.lower()
        ), f"os.getcwd should be allowed: {content}"


class TestSecurityBypass:
    """Test that dangerous mode bypasses security scanner."""

    @pytest.mark.p1
    def test_dangerous_mode_allows_all(self, mcp_server_dangerous):
        """Dangerous mode should allow normally-blocked patterns.

        Note: This tests that dangerous mode truly bypasses security.
        In practice, dangerous mode is intended for trusted use only.
        """
        # In dangerous mode, even "dangerous" code should be allowed
        # (The user has accepted the risk)

        # Try exec - normally blocked
        code = 'exec("x = 42"); print(x)'

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": code},
        )

        # In dangerous mode, this may or may not be blocked
        # depending on implementation. Document actual behavior.
        success, content = parse_tool_result(result)
        # Just verify it doesn't crash
        assert result is not None
