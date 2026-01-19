"""
Unit tests for Jupyter notebook tool registrar.

Tests NotebookToolRegistrar for registering notebook interaction tools with FastMCP.
"""

import pytest
import json
import sys
from unittest.mock import MagicMock, AsyncMock, patch

from instrmcp.servers.jupyter_qcodes.core.notebook_tools import (
    NotebookToolRegistrar,
)


class TestNotebookToolRegistrar:
    """Test NotebookToolRegistrar class for registering notebook tools."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock FastMCP server."""
        mcp = MagicMock()
        mcp._tools = {}

        # Mock the @mcp.tool decorator
        def tool_decorator(name=None, annotations=None):
            def wrapper(func):
                tool_name = name or func.__name__
                mcp._tools[tool_name] = func
                return func

            return wrapper

        mcp.tool = tool_decorator
        return mcp

    @pytest.fixture
    def mock_tools(self):
        """Create a mock QCodesReadOnlyTools instance."""
        tools = MagicMock()
        tools.list_variables = AsyncMock()
        tools.get_variable_info = AsyncMock()
        tools.get_editing_cell = AsyncMock()
        tools.update_editing_cell = AsyncMock()
        tools.move_cursor = AsyncMock()
        return tools

    @pytest.fixture
    def mock_ipython(self):
        """Create a mock IPython instance."""
        ipython = MagicMock()
        ipython.user_ns = {
            "In": ["", "import numpy as np", "x = 5"],
            "Out": {1: None, 2: 5},
        }
        ipython.execution_count = 2
        return ipython

    @pytest.fixture
    def registrar(self, mock_mcp_server, mock_tools, mock_ipython):
        """Create a NotebookToolRegistrar instance."""
        return NotebookToolRegistrar(mock_mcp_server, mock_tools, mock_ipython)

    def test_initialization(self, mock_mcp_server, mock_tools, mock_ipython):
        """Test registrar initialization."""
        registrar = NotebookToolRegistrar(mock_mcp_server, mock_tools, mock_ipython)
        assert registrar.mcp == mock_mcp_server
        assert registrar.tools == mock_tools
        assert registrar.ipython == mock_ipython

    def test_register_all(self, registrar, mock_mcp_server):
        """Test registering all notebook tools."""
        registrar.register_all()

        expected_tools = [
            "notebook_list_variables",
            "notebook_read_variable",
            "notebook_read_active_cell",
            "notebook_read_active_cell_output",
            "notebook_read_content",
            "notebook_move_cursor",
            "notebook_server_status",
        ]

        for tool_name in expected_tools:
            assert tool_name in mock_mcp_server._tools

        # update_editing_cell is now in UnsafeToolRegistrar, not here
        assert "notebook_update_editing_cell" not in mock_mcp_server._tools

    @pytest.mark.asyncio
    async def test_list_variables_no_filter(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test listing variables without filter."""
        mock_vars = [
            {"name": "x", "type": "int", "value": "5"},
            {"name": "y", "type": "str", "value": "hello"},
        ]
        mock_tools.list_variables.return_value = mock_vars

        registrar.register_all()
        list_vars_func = mock_mcp_server._tools["notebook_list_variables"]
        result = await list_vars_func(type_filter=None)

        response_data = json.loads(result[0].text)
        assert response_data == mock_vars
        mock_tools.list_variables.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_list_variables_with_filter(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test listing variables with type filter."""
        mock_vars = [{"name": "arr", "type": "ndarray", "shape": "(10,)"}]
        mock_tools.list_variables.return_value = mock_vars

        registrar.register_all()
        list_vars_func = mock_mcp_server._tools["notebook_list_variables"]
        result = await list_vars_func(type_filter="array")

        response_data = json.loads(result[0].text)
        assert response_data == mock_vars
        mock_tools.list_variables.assert_called_once_with("array")

    @pytest.mark.asyncio
    async def test_list_variables_error(self, registrar, mock_tools, mock_mcp_server):
        """Test listing variables with error."""
        mock_tools.list_variables.side_effect = Exception("Namespace error")

        registrar.register_all()
        list_vars_func = mock_mcp_server._tools["notebook_list_variables"]
        result = await list_vars_func(type_filter=None)

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "Namespace error" in response_data["error"]

    @pytest.mark.asyncio
    async def test_get_variable_info_success(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting variable info successfully."""
        mock_info = {"name": "x", "type": "int", "value": 5, "size": "28 bytes"}
        mock_tools.get_variable_info.return_value = mock_info

        registrar.register_all()
        get_var_func = mock_mcp_server._tools["notebook_read_variable"]
        result = await get_var_func(name="x", detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data == mock_info
        mock_tools.get_variable_info.assert_called_once_with("x")

    @pytest.mark.asyncio
    async def test_get_variable_info_not_found(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting info for non-existent variable."""
        mock_tools.get_variable_info.side_effect = KeyError("Variable not found")

        registrar.register_all()
        get_var_func = mock_mcp_server._tools["notebook_read_variable"]
        result = await get_var_func(name="nonexistent")

        response_data = json.loads(result[0].text)
        assert "error" in response_data

    @pytest.mark.asyncio
    async def test_get_editing_cell_success(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting editing cell content."""
        mock_cell = {
            "content": "import numpy as np",
            "cell_id": "abc123",  # This will be filtered out in detailed mode
            "timestamp": 1234567890,
        }
        mock_tools.get_editing_cell.return_value = mock_cell

        registrar.register_all()
        get_cell_func = mock_mcp_server._tools["notebook_read_active_cell"]
        result = await get_cell_func(fresh_ms=1000, detailed=True)

        response_data = json.loads(result[0].text)
        # cell_id is filtered out in detailed mode
        expected = {"content": "import numpy as np", "timestamp": 1234567890}
        assert response_data == expected
        mock_tools.get_editing_cell.assert_called_once_with(
            fresh_ms=1000, line_start=None, line_end=None, max_lines=200
        )

    @pytest.mark.asyncio
    async def test_get_editing_cell_default_fresh_ms(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting editing cell with default fresh_ms."""
        mock_cell = {"content": "x = 5", "cell_id": "xyz789"}
        mock_tools.get_editing_cell.return_value = mock_cell

        registrar.register_all()
        get_cell_func = mock_mcp_server._tools["notebook_read_active_cell"]
        await get_cell_func(fresh_ms=1000)

        mock_tools.get_editing_cell.assert_called_once_with(
            fresh_ms=1000, line_start=None, line_end=None, max_lines=200
        )

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_with_output(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Test getting cell output when output exists."""
        # Setup IPython with output
        mock_ipython.user_ns = {"In": ["", "x = 5", "print(x)"], "Out": {1: None, 2: 5}}
        mock_ipython.execution_count = 2

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func(detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["cell_number"] == 2
        assert response_data["status"] == "completed"
        assert response_data["output"] == "5"
        assert response_data["has_output"] is True

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_no_output(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Test getting cell output when cell has no output."""
        # Setup IPython with no output for last cell
        mock_ipython.user_ns = {"In": ["", "import numpy", "x = 5"], "Out": {}}
        mock_ipython.execution_count = 3

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func()

        response_data = json.loads(result[0].text)
        assert response_data["has_output"] is False
        assert response_data["status"] == "completed_no_output"

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_running(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Test getting cell output when cell is running."""
        # Setup IPython with running cell
        mock_ipython.user_ns = {"In": ["", "import time; time.sleep(10)"], "Out": {}}
        mock_ipython.execution_count = 1

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func(detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["status"] == "running"
        assert response_data["has_output"] is False

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_running_concise(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Ensure concise output preserves running status."""
        mock_ipython.user_ns = {"In": ["", "import time; time.sleep(10)"], "Out": {}}
        mock_ipython.execution_count = 1

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func()

        response_data = json.loads(result[0].text)
        assert response_data["status"] == "running"
        assert (
            response_data["message"]
            == "Cell is currently executing - no output available yet"
        )
        assert response_data["has_output"] is False

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_with_error(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Test getting cell output when cell raised an error."""
        # Setup IPython with error
        mock_ipython.user_ns = {"In": ["", 'raise ValueError("test error")'], "Out": {}}
        mock_ipython.execution_count = 2

        # Mock sys.last_* for error tracking
        with (
            patch.object(sys, "last_type", ValueError, create=True),
            patch.object(sys, "last_value", ValueError("test error"), create=True),
            patch.object(sys, "last_traceback", None, create=True),
        ):
            registrar.register_all()
            get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
            result = await get_output_func(detailed=True)

            response_data = json.loads(result[0].text)
            assert response_data["has_error"] is True
            assert response_data["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_notebook_cells_with_output(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Test getting notebook cells with output."""
        mock_ipython.user_ns = {
            "In": ["", "x = 5", "y = 10", "z = x + y"],
            "Out": {1: None, 2: None, 3: 15},
        }
        mock_ipython.execution_count = 3

        registrar.register_all()
        get_cells_func = mock_mcp_server._tools["notebook_read_content"]
        result = await get_cells_func(num_cells=2, include_output=True, detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["count"] == 2
        assert len(response_data["cells"]) == 2
        assert response_data["cells"][-1]["output"] == "15"

    @pytest.mark.asyncio
    async def test_get_notebook_cells_without_output(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Test getting notebook cells without output."""
        mock_ipython.user_ns = {"In": ["", "x = 5", "y = 10"], "Out": {}}

        registrar.register_all()
        get_cells_func = mock_mcp_server._tools["notebook_read_content"]
        result = await get_cells_func(num_cells=2, include_output=False)

        response_data = json.loads(result[0].text)
        assert response_data["count"] == 2
        # When include_output=False, has_output field is not included
        for cell in response_data["cells"]:
            assert "has_output" not in cell

    @pytest.mark.asyncio
    async def test_move_cursor_success(self, registrar, mock_tools, mock_mcp_server):
        """Test moving cursor successfully."""
        mock_result = {"status": "success", "old_index": 5, "new_index": 6}
        mock_tools.move_cursor.return_value = mock_result

        registrar.register_all()
        move_cursor_func = mock_mcp_server._tools["notebook_move_cursor"]
        result = await move_cursor_func(target="below", detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data == mock_result
        mock_tools.move_cursor.assert_called_once_with("below")

    @pytest.mark.asyncio
    async def test_move_cursor_by_index(self, registrar, mock_tools, mock_mcp_server):
        """Test moving cursor to specific cell by position index."""
        mock_result = {"status": "success", "old_index": 10, "new_index": 5}
        mock_tools.move_cursor.return_value = mock_result

        registrar.register_all()
        move_cursor_func = mock_mcp_server._tools["notebook_move_cursor"]
        await move_cursor_func(target="index:5")

        mock_tools.move_cursor.assert_called_once_with("index:5")

    @pytest.mark.asyncio
    async def test_move_cursor_error(self, registrar, mock_tools, mock_mcp_server):
        """Test moving cursor with error."""
        mock_tools.move_cursor.side_effect = Exception("Invalid target")

        registrar.register_all()
        move_cursor_func = mock_mcp_server._tools["notebook_move_cursor"]
        result = await move_cursor_func(target="invalid")

        response_data = json.loads(result[0].text)
        assert "error" in response_data

    @pytest.mark.asyncio
    async def test_server_status(self, registrar, mock_mcp_server):
        """Test getting server status."""
        registrar.register_all()
        status_func = mock_mcp_server._tools["notebook_server_status"]
        result = await status_func()

        response_data = json.loads(result[0].text)
        assert response_data["status"] == "running"
        assert "dynamic_tools_count" in response_data
        assert "tools" in response_data

    @pytest.mark.asyncio
    async def test_server_status_with_safe_mode(self, registrar, mock_mcp_server):
        """Test server status showing safe mode."""
        registrar.safe_mode = True
        registrar.register_all()
        status_func = mock_mcp_server._tools["notebook_server_status"]
        result = await status_func()

        response_data = json.loads(result[0].text)
        assert response_data["mode"] == "safe"

    @pytest.mark.asyncio
    async def test_get_notebook_cells_with_errors(
        self, registrar, mock_ipython, mock_mcp_server
    ):
        """Test getting notebook cells with error tracking."""
        mock_ipython.user_ns = {
            "In": ["", "x = 5", 'raise ValueError("test")'],
            "Out": {1: None},
        }
        mock_ipython.execution_count = 3

        with (
            patch.object(sys, "last_type", ValueError, create=True),
            patch.object(sys, "last_value", ValueError("test"), create=True),
            patch.object(sys, "last_traceback", None, create=True),
        ):
            registrar.register_all()
            get_cells_func = mock_mcp_server._tools["notebook_read_content"]
            result = await get_cells_func(
                num_cells=2, include_output=True, detailed=True
            )

            response_data = json.loads(result[0].text)
            assert response_data["error_count"] >= 0

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_with_stdout_capture(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test getting cell output with captured stdout from print statements."""
        # Setup IPython with no Out dict entry (print returns None)
        # Note: status will be "completed_no_output" because Out is empty
        # (print() returns None, not a value)
        mock_ipython.user_ns = {"In": ["", 'print("hello world")'], "Out": {}}
        mock_ipython.execution_count = 2

        # Mock the frontend output response
        def mock_get_frontend_output(cell_number):
            if cell_number == 1:
                return {
                    "has_output": True,
                    "outputs": [
                        {"type": "stream", "name": "stdout", "text": "hello world\n"}
                    ],
                }
            return None

        monkeypatch.setattr(registrar, "_get_frontend_output", mock_get_frontend_output)

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func(detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["cell_number"] == 1
        # status is "completed_no_output" because print() returns None (no Out dict entry)
        assert response_data["status"] == "completed_no_output"
        assert response_data["has_error"] is False

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_with_stderr_capture(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test getting cell output with captured stderr."""
        # Setup IPython with no Out dict entry (print to stderr returns None)
        # Note: status will be "completed_no_output" because Out is empty
        mock_ipython.user_ns = {
            "In": ["", 'print("error", file=sys.stderr)'],
            "Out": {},
        }
        mock_ipython.execution_count = 2

        # Mock the frontend output response
        def mock_get_frontend_output(cell_number):
            if cell_number == 1:
                return {
                    "has_output": True,
                    "outputs": [
                        {"type": "stream", "name": "stderr", "text": "error\n"}
                    ],
                }
            return None

        monkeypatch.setattr(registrar, "_get_frontend_output", mock_get_frontend_output)

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func(detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["cell_number"] == 1
        # status is "completed_no_output" because stderr print returns None
        assert response_data["status"] == "completed_no_output"
        assert response_data["has_error"] is False

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_with_frontend_error(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test that frontend error outputs are correctly detected and flagged.

        This tests the fix for the critical bug where frontend outputs with
        output_type='error' were incorrectly treated as success (has_error=False).
        """
        # Setup IPython with no Out dict entry
        mock_ipython.user_ns = {
            "In": ["", "1/0"],  # Division by zero
            "Out": {},
        }
        mock_ipython.execution_count = 2

        # Mock the get_active_cell_output response from active_cell_bridge
        # Note: implementation checks for "type" == "error", not "output_type"
        def mock_get_active_cell_output(timeout_s=2.0):
            return {
                "success": True,
                "cell_type": "code",
                "cell_index": 0,
                "execution_count": 1,
                "has_output": True,
                "has_error": True,
                "outputs": [
                    {
                        "type": "error",
                        "ename": "ZeroDivisionError",
                        "evalue": "division by zero",
                        "traceback": [
                            "---------------------------------------------------------------------------",
                            "ZeroDivisionError                         Traceback (most recent call last)",
                            "Cell In[1], line 1\n----> 1 1/0",
                            "ZeroDivisionError: division by zero",
                        ],
                    }
                ],
            }

        monkeypatch.setattr(
            "instrmcp.servers.jupyter_qcodes.core.notebook_tools.get_active_cell_output",
            mock_get_active_cell_output,
        )

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func(detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["cell_id_notebook"] == 0  # Changed from cell_number
        assert response_data["executed"] is True  # New field
        assert response_data["status"] == "error"
        assert response_data["has_error"] is True
        assert response_data["has_output"] is True
        assert "error" in response_data
        assert response_data["error"]["type"] == "ZeroDivisionError"
        assert response_data["error"]["message"] == "division by zero"

    @pytest.mark.asyncio
    async def test_get_editing_cell_output_with_type_error_format(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test that type='error' format (alternative to output_type) is also detected."""
        # Setup IPython with no Out dict entry
        mock_ipython.user_ns = {
            "In": ["", "raise ValueError('test')"],
            "Out": {},
        }
        mock_ipython.execution_count = 2

        # Mock the get_active_cell_output response with type='error'
        def mock_get_active_cell_output(timeout_s=2.0):
            return {
                "success": True,
                "cell_type": "code",
                "cell_index": 0,
                "execution_count": 1,
                "has_output": True,
                "has_error": True,
                "outputs": [
                    {
                        "type": "error",
                        "ename": "ValueError",
                        "evalue": "test",
                        "traceback": ["ValueError: test"],
                    }
                ],
            }

        monkeypatch.setattr(
            "instrmcp.servers.jupyter_qcodes.core.notebook_tools.get_active_cell_output",
            mock_get_active_cell_output,
        )

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func(detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert response_data["has_error"] is True
        assert response_data["error"]["type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_get_notebook_cells_with_stdout_capture(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test getting notebook cells with captured stdout via frontend two-phase approach."""
        # Setup IPython with print statements (used as fallback)
        mock_ipython.user_ns = {
            "In": ["", 'print("first")', 'print("second")'],
            "Out": {},
        }
        mock_ipython.execution_count = 3

        # Mock the new two-phase frontend functions
        def mock_get_notebook_structure(timeout_s=2.0):
            return {
                "success": True,
                "total_cells": 2,
                "active_cell_index": 1,
                "cells": [
                    {
                        "cell_id_notebook": 0,
                        "cell_type": "code",
                        "cell_execution_number": 1,
                    },
                    {
                        "cell_id_notebook": 1,
                        "cell_type": "code",
                        "cell_execution_number": 2,
                    },
                ],
            }

        def mock_get_cells_by_index(indices, timeout_s=2.0):
            cells = []
            if 0 in indices:
                cells.append(
                    {
                        "cell_id_notebook": 0,
                        "cell_type": "code",
                        "cell_execution_number": 1,
                        "source": 'print("first")',
                    }
                )
            if 1 in indices:
                cells.append(
                    {
                        "cell_id_notebook": 1,
                        "cell_type": "code",
                        "cell_execution_number": 2,
                        "source": 'print("second")',
                    }
                )
            return {"success": True, "cells": cells}

        # Mock the frontend output response
        def mock_get_frontend_output(cell_number):
            if cell_number == 1:
                return {
                    "has_output": True,
                    "outputs": [
                        {"type": "stream", "name": "stdout", "text": "first\n"}
                    ],
                }
            elif cell_number == 2:
                return {
                    "has_output": True,
                    "outputs": [
                        {"type": "stream", "name": "stdout", "text": "second\n"}
                    ],
                }
            return None

        monkeypatch.setattr(
            "instrmcp.servers.jupyter_qcodes.core.notebook_tools.get_notebook_structure",
            mock_get_notebook_structure,
        )
        monkeypatch.setattr(
            "instrmcp.servers.jupyter_qcodes.core.notebook_tools.get_cells_by_index",
            mock_get_cells_by_index,
        )
        monkeypatch.setattr(registrar, "_get_frontend_output", mock_get_frontend_output)

        registrar.register_all()
        get_cells_func = mock_mcp_server._tools["notebook_read_content"]
        result = await get_cells_func(num_cells=2, include_output=True, detailed=True)

        response_data = json.loads(result[0].text)
        cells = response_data["cells"]

        assert len(cells) == 2
        assert cells[0]["outputs"][0]["text"] == "first\n"
        assert cells[0]["has_output"] is True
        assert cells[1]["outputs"][0]["text"] == "second\n"
        assert cells[1]["has_output"] is True
        # Verify new field names
        assert cells[0]["cell_id_notebook"] == 0
        assert (
            cells[0]["executed"] is True
        )  # Replaced cell_execution_number with executed
        assert "source" in cells[0]

    @pytest.mark.asyncio
    async def test_get_notebook_cells_cell_id_notebooks_requires_frontend(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test that cell_id_notebooks returns explicit error when frontend unavailable."""
        # Setup IPython fallback data
        mock_ipython.user_ns = {
            "In": ["", 'print("first")', 'print("second")'],
            "Out": {},
        }
        mock_ipython.execution_count = 3

        # Mock frontend as unavailable
        def mock_get_notebook_structure(timeout_s=2.0):
            return {
                "success": False,
                "error": "No active notebook",
            }

        monkeypatch.setattr(
            "instrmcp.servers.jupyter_qcodes.core.notebook_tools.get_notebook_structure",
            mock_get_notebook_structure,
        )

        registrar.register_all()
        get_cells_func = mock_mcp_server._tools["notebook_read_content"]

        # Request specific cells by position - should fail with explicit error
        result = await get_cells_func(cell_id_notebooks="[0, 1]", detailed=True)

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert (
            "cell_id_notebooks requires JupyterLab frontend" in response_data["error"]
        )
        assert "detail" in response_data
        assert "frontend_error" in response_data

    @pytest.mark.asyncio
    async def test_get_notebook_cells_num_cells_fallback_works(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test that num_cells mode falls back to IPython when frontend unavailable."""
        # Setup IPython fallback data
        mock_ipython.user_ns = {
            "In": ["", "x = 1", "y = 2"],
            "Out": {1: None, 2: 2},
        }
        mock_ipython.execution_count = 3

        # Mock frontend as unavailable
        def mock_get_notebook_structure(timeout_s=2.0):
            return {
                "success": False,
                "error": "No active notebook",
            }

        monkeypatch.setattr(
            "instrmcp.servers.jupyter_qcodes.core.notebook_tools.get_notebook_structure",
            mock_get_notebook_structure,
        )

        registrar.register_all()
        get_cells_func = mock_mcp_server._tools["notebook_read_content"]

        # Request with num_cells (no cell_id_notebooks) - should fallback to IPython
        result = await get_cells_func(num_cells=2, detailed=True)

        response_data = json.loads(result[0].text)
        # Should succeed with IPython fallback
        assert "error" not in response_data
        assert "cells" in response_data
        assert "note" in response_data
        assert "IPython fallback" in response_data["note"]

    @pytest.mark.asyncio
    async def test_frontend_output_priority_over_out_dict(
        self, registrar, mock_ipython, mock_tools, mock_mcp_server, monkeypatch
    ):
        """Test that frontend output takes priority over Out dictionary."""
        # Setup IPython with both Out entry and frontend output
        mock_ipython.user_ns = {
            "In": ["", 'print("stdout"); 42'],
            "Out": {1: 42},  # Out has return value
        }
        mock_ipython.execution_count = 2

        # Mock get_active_cell_output - frontend output takes priority
        def mock_get_active_cell_output(timeout_s=2.0):
            return {
                "success": True,
                "cell_type": "code",
                "cell_index": 0,
                "execution_count": 1,
                "has_output": True,
                "has_error": False,
                "outputs": [
                    {"type": "stream", "name": "stdout", "text": "stdout\n"},
                    {"type": "execute_result", "data": {"text/plain": "42"}},
                ],
            }

        monkeypatch.setattr(
            "instrmcp.servers.jupyter_qcodes.core.notebook_tools.get_active_cell_output",
            mock_get_active_cell_output,
        )

        registrar.register_all()
        get_output_func = mock_mcp_server._tools["notebook_read_active_cell_output"]
        result = await get_output_func(detailed=True)

        response_data = json.loads(result[0].text)
        # Should return outputs from frontend, not just Out value
        assert len(response_data["outputs"]) == 2
        assert response_data["outputs"][0]["text"] == "stdout\n"
        assert response_data["has_output"] is True

    def test_all_tools_are_async(self, registrar, mock_mcp_server):
        """Test that all registered tools are async functions."""
        import asyncio

        registrar.register_all()

        for tool_name, tool_func in mock_mcp_server._tools.items():
            assert asyncio.iscoroutinefunction(
                tool_func
            ), f"Tool {tool_name} should be an async function"


class TestUnsafeToolRegistrarUpdateCell:
    """Test UnsafeToolRegistrar consent functionality for update_editing_cell."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock FastMCP server."""
        mcp = MagicMock()
        mcp._tools = {}

        def tool_decorator(name=None, annotations=None):
            def wrapper(func):
                tool_name = name or func.__name__
                mcp._tools[tool_name] = func
                return func

            return wrapper

        mcp.tool = tool_decorator
        return mcp

    @pytest.fixture
    def mock_tools(self):
        """Create a mock QCodesReadOnlyTools instance."""
        from instrmcp.servers.jupyter_qcodes.core.notebook_unsafe_tools import (
            UnsafeToolRegistrar,
        )

        tools = MagicMock()
        tools.get_editing_cell = AsyncMock()
        tools.update_editing_cell = AsyncMock()
        tools.execute_editing_cell = AsyncMock()
        tools.add_new_cell = AsyncMock()
        tools.delete_editing_cell = AsyncMock()
        tools.delete_cells_by_number = AsyncMock()
        tools.delete_cells_by_index = AsyncMock()
        tools.apply_patch = AsyncMock()
        return tools

    @pytest.fixture
    def mock_consent_manager(self):
        """Create a mock ConsentManager instance."""
        consent_manager = MagicMock()
        consent_manager.request_consent = AsyncMock()
        return consent_manager

    def test_update_editing_cell_registered_in_unsafe(
        self, mock_mcp_server, mock_tools, mock_consent_manager
    ):
        """Test update_editing_cell is registered in UnsafeToolRegistrar."""
        from instrmcp.servers.jupyter_qcodes.core.notebook_unsafe_tools import (
            UnsafeToolRegistrar,
        )

        registrar = UnsafeToolRegistrar(
            mock_mcp_server, mock_tools, mock_consent_manager
        )
        registrar.register_all()

    @pytest.mark.asyncio
    async def test_execute_cell_blocked_by_scanner(
        self, mock_mcp_server, mock_tools, mock_consent_manager
    ):
        """Test execute_editing_cell is blocked by unsafe code scanner."""
        from instrmcp.servers.jupyter_qcodes.core.notebook_unsafe_tools import (
            UnsafeToolRegistrar,
        )

        mock_tools.get_editing_cell.return_value = {
            "cell_content": "eval('1')",
            "cell_type": "code",
        }

        registrar = UnsafeToolRegistrar(
            mock_mcp_server, mock_tools, mock_consent_manager
        )
        registrar.register_all()

        execute_cell_func = mock_mcp_server._tools["notebook_execute_active_cell"]
        result = await execute_cell_func(timeout=1.0, detailed=True)

        response_data = json.loads(result[0].text)
        assert response_data["success"] is False
        assert response_data["blocked"] is True
        assert "block_reason" in response_data
        mock_consent_manager.request_consent.assert_not_called()
        mock_tools.execute_editing_cell.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_new_cell_blocked_by_scanner(
        self, mock_mcp_server, mock_tools, mock_consent_manager
    ):
        """Test add_new_cell is blocked by unsafe code scanner."""
        from instrmcp.servers.jupyter_qcodes.core.notebook_unsafe_tools import (
            UnsafeToolRegistrar,
        )

        registrar = UnsafeToolRegistrar(
            mock_mcp_server, mock_tools, mock_consent_manager
        )
        registrar.register_all()

        add_cell_func = mock_mcp_server._tools["notebook_add_cell"]
        result = await add_cell_func(
            cell_type="code", position="below", content="eval('1')"
        )

        response_data = json.loads(result[0].text)
        assert response_data["success"] is False
        assert response_data["blocked"] is True
        assert "block_reason" in response_data
        mock_tools.add_new_cell.assert_not_called()
