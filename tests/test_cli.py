"""
Unit tests for cli.py module.

Tests all CLI commands (jupyter, qcodes, config, version), argument parsing,
and error handling for the InstrMCP command-line interface.
"""

import pytest
import sys
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call
from io import StringIO

from instrmcp import cli, __version__


class TestCLIArgumentParsing:
    """Test CLI argument parsing for all commands."""

    def test_no_command_shows_help(self):
        """Test that running without a command shows help and exits."""
        with patch("sys.argv", ["instrmcp"]):
            with patch("sys.stdout", new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    cli.main()
                assert exc_info.value.code == 1

    def test_invalid_command(self):
        """Test that an invalid command shows help and exits."""
        with patch("sys.argv", ["instrmcp", "invalid_command"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_jupyter_command_default_args(self):
        """Test jupyter command with default arguments."""
        with patch("sys.argv", ["instrmcp", "jupyter"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                # Should call with default port=3000, safe_mode=True
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                # The coroutine is passed, we can't inspect args directly

    def test_jupyter_command_custom_port(self):
        """Test jupyter command with custom port."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "5000"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_jupyter_command_unsafe_flag(self):
        """Test jupyter command with unsafe flag."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--unsafe"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_jupyter_command_custom_port_and_unsafe(self):
        """Test jupyter command with both custom port and unsafe flag."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "4000", "--unsafe"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_qcodes_command_default_port(self):
        """Test qcodes command with default port."""
        with patch("sys.argv", ["instrmcp", "qcodes"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_qcodes_command_custom_port(self):
        """Test qcodes command with custom port."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--port", "6000"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_config_command(self):
        """Test config command prints configuration."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch.object(
                    cli.config, "get_package_path", return_value="/fake/path"
                ):
                    with patch.object(
                        cli.config, "get_config_file", return_value="/fake/config"
                    ):
                        with patch.object(
                            cli.config, "get_user_config_dir", return_value="/fake/user"
                        ):
                            cli.main()
                            output = mock_stdout.getvalue()
                            assert "InstrMCP Configuration:" in output
                            assert "/fake/path" in output
                            assert "/fake/config" in output
                            assert "/fake/user" in output

    def test_version_command(self):
        """Test version command prints version."""
        with patch("sys.argv", ["instrmcp", "version"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.main()
                output = mock_stdout.getvalue()
                assert "InstrMCP version" in output
                assert __version__ in output

    def test_help_flag(self):
        """Test that --help flag shows help."""
        with patch("sys.argv", ["instrmcp", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
            # argparse exits with code 0 for --help
            assert exc_info.value.code == 0

    def test_jupyter_help_flag(self):
        """Test that --help flag works for jupyter subcommand."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
            assert exc_info.value.code == 0

    def test_qcodes_help_flag(self):
        """Test that --help flag works for qcodes subcommand."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
            assert exc_info.value.code == 0


class TestJupyterServerFunction:
    """Test run_jupyter_server async function."""

    @pytest.mark.asyncio
    async def test_jupyter_server_default_args(self):
        """Test jupyter server with default arguments."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch(
            "instrmcp.cli.JupyterMCPServer", return_value=mock_server
        ) as mock_class:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                await cli.run_jupyter_server()

                # Should create server with default args
                mock_class.assert_called_once_with(port=3000, safe_mode=True)
                mock_server.run.assert_called_once()

                # Check output messages
                output = mock_stdout.getvalue()
                assert "Starting Jupyter QCodes MCP server on port 3000" in output
                assert "Safe mode: enabled" in output

    @pytest.mark.asyncio
    async def test_jupyter_server_custom_port(self):
        """Test jupyter server with custom port."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch(
            "instrmcp.cli.JupyterMCPServer", return_value=mock_server
        ) as mock_class:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                await cli.run_jupyter_server(port=5000)

                mock_class.assert_called_once_with(port=5000, safe_mode=True)
                output = mock_stdout.getvalue()
                assert "5000" in output

    @pytest.mark.asyncio
    async def test_jupyter_server_unsafe_mode(self):
        """Test jupyter server with unsafe mode."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch(
            "instrmcp.cli.JupyterMCPServer", return_value=mock_server
        ) as mock_class:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                await cli.run_jupyter_server(safe_mode=False)

                mock_class.assert_called_once_with(port=3000, safe_mode=False)
                output = mock_stdout.getvalue()
                assert "Safe mode: disabled" in output

    @pytest.mark.asyncio
    async def test_jupyter_server_exception_handling(self):
        """Test jupyter server handles exceptions properly."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock(side_effect=RuntimeError("Server error"))

        with patch("instrmcp.cli.JupyterMCPServer", return_value=mock_server):
            with pytest.raises(RuntimeError, match="Server error"):
                await cli.run_jupyter_server()


class TestQCodesServerFunction:
    """Test run_qcodes_server async function."""

    @pytest.mark.asyncio
    async def test_qcodes_server_default_port(self):
        """Test qcodes server with default port."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch(
            "instrmcp.cli.QCodesStationServer", return_value=mock_server
        ) as mock_class:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                await cli.run_qcodes_server()

                mock_class.assert_called_once_with(port=3001)
                mock_server.run.assert_called_once()

                output = mock_stdout.getvalue()
                assert "Starting QCodes station MCP server on port 3001" in output

    @pytest.mark.asyncio
    async def test_qcodes_server_custom_port(self):
        """Test qcodes server with custom port."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch(
            "instrmcp.cli.QCodesStationServer", return_value=mock_server
        ) as mock_class:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                await cli.run_qcodes_server(port=6000)

                mock_class.assert_called_once_with(port=6000)
                output = mock_stdout.getvalue()
                assert "6000" in output

    @pytest.mark.asyncio
    async def test_qcodes_server_exception_handling(self):
        """Test qcodes server handles exceptions properly."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock(side_effect=ConnectionError("Connection failed"))

        with patch("instrmcp.cli.QCodesStationServer", return_value=mock_server):
            with pytest.raises(ConnectionError, match="Connection failed"):
                await cli.run_qcodes_server()


class TestCLIIntegration:
    """Test CLI integration with asyncio.run."""

    def test_jupyter_command_calls_asyncio_run(self):
        """Test that jupyter command calls asyncio.run with correct coroutine."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "3500"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()

                # Should call asyncio.run once
                assert mock_run.call_count == 1

                # The first argument should be a coroutine
                called_coro = mock_run.call_args[0][0]
                assert asyncio.iscoroutine(called_coro)
                # Clean up the coroutine
                called_coro.close()

    def test_qcodes_command_calls_asyncio_run(self):
        """Test that qcodes command calls asyncio.run with correct coroutine."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--port", "3500"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()

                assert mock_run.call_count == 1
                called_coro = mock_run.call_args[0][0]
                assert asyncio.iscoroutine(called_coro)
                called_coro.close()

    def test_config_command_no_asyncio_run(self):
        """Test that config command does not call asyncio.run."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                with patch.object(
                    cli.config, "get_package_path", return_value="/fake/path"
                ):
                    with patch.object(
                        cli.config, "get_config_file", return_value="/fake/config"
                    ):
                        with patch.object(
                            cli.config, "get_user_config_dir", return_value="/fake/user"
                        ):
                            with patch("sys.stdout", new_callable=StringIO):
                                cli.main()

                # Config should not use asyncio
                mock_run.assert_not_called()

    def test_version_command_no_asyncio_run(self):
        """Test that version command does not call asyncio.run."""
        with patch("sys.argv", ["instrmcp", "version"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                with patch("sys.stdout", new_callable=StringIO):
                    cli.main()

                # Version should not use asyncio
                mock_run.assert_not_called()


class TestCLIErrorHandling:
    """Test CLI error handling for invalid arguments."""

    def test_jupyter_invalid_port_type(self):
        """Test jupyter command with invalid port type."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "not_a_number"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_qcodes_invalid_port_type(self):
        """Test qcodes command with invalid port type."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--port", "invalid"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_jupyter_negative_port(self):
        """Test jupyter command with negative port number."""
        # Note: argparse doesn't validate port range, but we test it accepts the value
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "-1"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_jupyter_unknown_flag(self):
        """Test jupyter command with unknown flag."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--unknown-flag"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_qcodes_unknown_flag(self):
        """Test qcodes command with unknown flag."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--verbose"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_config_unknown_flag(self):
        """Test config command with unknown flag."""
        with patch("sys.argv", ["instrmcp", "config", "--unknown"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_version_unknown_flag(self):
        """Test version command with unknown flag."""
        with patch("sys.argv", ["instrmcp", "version", "--unknown"]):
            with pytest.raises(SystemExit):
                cli.main()


class TestCLIEdgeCases:
    """Test CLI edge cases and boundary conditions."""

    def test_jupyter_port_zero(self):
        """Test jupyter command with port 0 (OS assigns port)."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "0"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_jupyter_high_port_number(self):
        """Test jupyter command with high port number."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "65535"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_qcodes_port_zero(self):
        """Test qcodes command with port 0."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--port", "0"]):
            with patch.object(cli.asyncio, "run") as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_multiple_flags_order(self):
        """Test jupyter command with flags in different orders."""
        test_cases = [
            ["instrmcp", "jupyter", "--port", "4000", "--unsafe"],
            ["instrmcp", "jupyter", "--unsafe", "--port", "4000"],
        ]

        for argv in test_cases:
            with patch("sys.argv", argv):
                with patch.object(cli.asyncio, "run") as mock_run:
                    cli.main()
                    mock_run.assert_called_once()

    def test_config_with_none_values(self):
        """Test config command when some config values are None."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch.object(cli.config, "get_package_path", return_value="/path"):
                    with patch.object(cli.config, "get_config_file", return_value=None):
                        with patch.object(
                            cli.config, "get_user_config_dir", return_value="/user"
                        ):
                            cli.main()
                            output = mock_stdout.getvalue()
                            assert (
                                "None" in output or "InstrMCP Configuration:" in output
                            )


class TestMainFunction:
    """Test the main() entry point function."""

    def test_main_can_be_called_directly(self):
        """Test that main() can be called directly."""
        with patch("sys.argv", ["instrmcp", "version"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.main()
                output = mock_stdout.getvalue()
                assert "InstrMCP version" in output

    def test_main_exits_on_no_command(self):
        """Test that main() exits when no command is provided."""
        with patch("sys.argv", ["instrmcp"]):
            with pytest.raises(SystemExit) as exc_info:
                with patch("sys.stdout", new_callable=StringIO):
                    cli.main()
            assert exc_info.value.code == 1

    def test_main_module_execution(self):
        """Test that module can be executed with python -m."""
        # This tests the if __name__ == "__main__": block
        with patch("sys.argv", ["cli.py", "version"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                # We can't directly test __name__ == "__main__", but we can test main()
                cli.main()
                output = mock_stdout.getvalue()
                assert __version__ in output


class TestAsyncServerFunctions:
    """Test async server initialization and execution."""

    @pytest.mark.asyncio
    async def test_jupyter_server_initialization_params(self):
        """Test that JupyterMCPServer receives correct initialization parameters."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch(
            "instrmcp.cli.JupyterMCPServer", return_value=mock_server
        ) as mock_class:
            # Test various parameter combinations
            test_cases = [
                {"port": 3000, "safe_mode": True},
                {"port": 4000, "safe_mode": False},
                {"port": 8080, "safe_mode": True},
            ]

            for params in test_cases:
                await cli.run_jupyter_server(**params)
                mock_class.assert_called_with(**params)

    @pytest.mark.asyncio
    async def test_qcodes_server_initialization_params(self):
        """Test that QCodesStationServer receives correct initialization parameters."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch(
            "instrmcp.cli.QCodesStationServer", return_value=mock_server
        ) as mock_class:
            test_ports = [3001, 5000, 9000]

            for port in test_ports:
                await cli.run_qcodes_server(port=port)
                mock_class.assert_called_with(port=port)

    @pytest.mark.asyncio
    async def test_server_run_called_once(self):
        """Test that server.run() is called exactly once."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch("instrmcp.cli.JupyterMCPServer", return_value=mock_server):
            await cli.run_jupyter_server()
            mock_server.run.assert_called_once()

        mock_server.run.reset_mock()

        with patch("instrmcp.cli.QCodesStationServer", return_value=mock_server):
            await cli.run_qcodes_server()
            mock_server.run.assert_called_once()


class TestCLIOutput:
    """Test CLI output messages and formatting."""

    def test_jupyter_safe_mode_message(self):
        """Test that safe mode message is displayed correctly."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch("instrmcp.cli.JupyterMCPServer", return_value=mock_server):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                asyncio.run(cli.run_jupyter_server(safe_mode=True))
                output = mock_stdout.getvalue()
                assert "Safe mode: enabled" in output

    def test_jupyter_unsafe_mode_message(self):
        """Test that unsafe mode message is displayed correctly."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch("instrmcp.cli.JupyterMCPServer", return_value=mock_server):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                asyncio.run(cli.run_jupyter_server(safe_mode=False))
                output = mock_stdout.getvalue()
                assert "Safe mode: disabled" in output

    def test_server_port_in_output(self):
        """Test that server port is displayed in output."""
        mock_server = MagicMock()
        mock_server.run = AsyncMock()

        with patch("instrmcp.cli.JupyterMCPServer", return_value=mock_server):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                asyncio.run(cli.run_jupyter_server(port=7777))
                output = mock_stdout.getvalue()
                assert "7777" in output

    def test_config_output_format(self):
        """Test config command output format."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch.object(
                    cli.config, "get_package_path", return_value="/test/package"
                ):
                    with patch.object(
                        cli.config, "get_config_file", return_value="/test/config.yaml"
                    ):
                        with patch.object(
                            cli.config, "get_user_config_dir", return_value="/test/user"
                        ):
                            cli.main()
                            output = mock_stdout.getvalue()

                            # Check all expected lines are present
                            assert "InstrMCP Configuration:" in output
                            assert "Package path:" in output
                            assert "Config file:" in output
                            assert "User config directory:" in output
                            assert "/test/package" in output
                            assert "/test/config.yaml" in output
                            assert "/test/user" in output

    def test_version_output_format(self):
        """Test version command output format."""
        with patch("sys.argv", ["instrmcp", "version"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.main()
                output = mock_stdout.getvalue()

                # Check version string format
                assert "InstrMCP version" in output
                assert __version__ in output
                # Should be on a single line
                lines = output.strip().split("\n")
                assert len(lines) == 1
