"""
Unit tests for cli.py module.

Tests all CLI commands (jupyter, qcodes, config, version), argument parsing,
and error handling for the InstrMCP command-line interface.
"""

import pytest
from unittest.mock import MagicMock, patch
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
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_asyncio_run:
                with pytest.raises(SystemExit):  # run_jupyter_server calls sys.exit(1)
                    cli.main()
                mock_asyncio_run.assert_called_once()

    def test_jupyter_command_custom_port(self):
        """Test jupyter command with custom port."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "5000"]):
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_asyncio_run:
                with pytest.raises(SystemExit):
                    cli.main()
                mock_asyncio_run.assert_called_once()

    def test_jupyter_command_unsafe_flag(self):
        """Test jupyter command with unsafe flag."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--unsafe"]):
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_asyncio_run:
                with pytest.raises(SystemExit):
                    cli.main()
                mock_asyncio_run.assert_called_once()

    def test_jupyter_command_custom_port_and_unsafe(self):
        """Test jupyter command with both custom port and unsafe flag."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "4000", "--unsafe"]):
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_asyncio_run:
                with pytest.raises(SystemExit):
                    cli.main()
                mock_asyncio_run.assert_called_once()

    def test_qcodes_command_default_port(self):
        """Test qcodes command with default port."""
        with patch("sys.argv", ["instrmcp", "qcodes"]):
            with patch("instrmcp.cli.QCodesStationServer") as mock_server_class:
                mock_server = MagicMock()
                mock_server_class.return_value = mock_server
                with patch("sys.stdout", new_callable=StringIO):
                    cli.main()
                mock_server_class.assert_called_once_with(port=3001)
                mock_server.start.assert_called_once()

    def test_qcodes_command_custom_port(self):
        """Test qcodes command with custom port."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--port", "6000"]):
            with patch("instrmcp.cli.QCodesStationServer") as mock_server_class:
                mock_server = MagicMock()
                mock_server_class.return_value = mock_server
                with patch("sys.stdout", new_callable=StringIO):
                    cli.main()
                mock_server_class.assert_called_once_with(port=6000)

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
                            with patch("importlib.util.find_spec", return_value=None):
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
    async def test_jupyter_server_exits_with_message(self):
        """Test jupyter server shows standalone mode message and exits."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as exc_info:
                await cli.run_jupyter_server()

            assert exc_info.value.code == 1
            output = mock_stdout.getvalue()
            assert "STANDALONE MODE" in output
            assert "not fully implemented" in output


class TestQCodesServerFunction:
    """Test run_qcodes_server function."""

    def test_qcodes_server_default_port(self):
        """Test qcodes server with default port."""
        mock_server = MagicMock()

        with patch(
            "instrmcp.cli.QCodesStationServer", return_value=mock_server
        ) as mock_class:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.run_qcodes_server()

                mock_class.assert_called_once_with(port=3001)
                mock_server.start.assert_called_once()

                output = mock_stdout.getvalue()
                assert "Starting QCodes station MCP server on port 3001" in output

    def test_qcodes_server_custom_port(self):
        """Test qcodes server with custom port."""
        mock_server = MagicMock()

        with patch(
            "instrmcp.cli.QCodesStationServer", return_value=mock_server
        ) as mock_class:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.run_qcodes_server(port=6000)

                mock_class.assert_called_once_with(port=6000)
                output = mock_stdout.getvalue()
                assert "6000" in output

    def test_qcodes_server_exception_handling(self):
        """Test qcodes server handles exceptions properly."""
        mock_server = MagicMock()
        mock_server.start.side_effect = ConnectionError("Connection failed")

        with patch("instrmcp.cli.QCodesStationServer", return_value=mock_server):
            with pytest.raises(ConnectionError, match="Connection failed"):
                cli.run_qcodes_server()


class TestCLIIntegration:
    """Test CLI integration."""

    def test_jupyter_command_calls_asyncio_run(self):
        """Test that jupyter command calls asyncio.run."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "3500"]):
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_run:
                with pytest.raises(SystemExit):
                    cli.main()
                mock_run.assert_called_once()

    def test_qcodes_command_calls_function(self):
        """Test that qcodes command calls run_qcodes_server."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--port", "3500"]):
            with patch("instrmcp.cli.run_qcodes_server") as mock_run:
                cli.main()
                mock_run.assert_called_once_with(port=3500)

    def test_config_command_no_asyncio_run(self):
        """Test that config command does not use asyncio."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch("asyncio.run") as mock_run:
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
                                with patch(
                                    "importlib.util.find_spec", return_value=None
                                ):
                                    cli.main()

                # Config should not use asyncio
                mock_run.assert_not_called()

    def test_version_command_no_asyncio_run(self):
        """Test that version command does not use asyncio."""
        with patch("sys.argv", ["instrmcp", "version"]):
            with patch("asyncio.run") as mock_run:
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
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "-1"]):
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_run:
                with pytest.raises(SystemExit):
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
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_run:
                with pytest.raises(SystemExit):
                    cli.main()
                mock_run.assert_called_once()

    def test_jupyter_high_port_number(self):
        """Test jupyter command with high port number."""
        with patch("sys.argv", ["instrmcp", "jupyter", "--port", "65535"]):
            with patch("asyncio.run", side_effect=SystemExit(1)) as mock_run:
                with pytest.raises(SystemExit):
                    cli.main()
                mock_run.assert_called_once()

    def test_qcodes_port_zero(self):
        """Test qcodes command with port 0."""
        with patch("sys.argv", ["instrmcp", "qcodes", "--port", "0"]):
            with patch("instrmcp.cli.run_qcodes_server") as mock_run:
                cli.main()
                mock_run.assert_called_once_with(port=0)

    def test_multiple_flags_order(self):
        """Test jupyter command with flags in different orders."""
        test_cases = [
            ["instrmcp", "jupyter", "--port", "4000", "--unsafe"],
            ["instrmcp", "jupyter", "--unsafe", "--port", "4000"],
        ]

        for argv in test_cases:
            with patch("sys.argv", argv):
                with patch("asyncio.run", side_effect=SystemExit(1)) as mock_run:
                    with pytest.raises(SystemExit):
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
                            with patch("importlib.util.find_spec", return_value=None):
                                cli.main()
                                output = mock_stdout.getvalue()
                                assert (
                                    "None" in output
                                    or "InstrMCP Configuration:" in output
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
        with patch("sys.argv", ["cli.py", "version"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.main()
                output = mock_stdout.getvalue()
                assert __version__ in output


class TestCLIOutput:
    """Test CLI output messages and formatting."""

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
                            with patch("importlib.util.find_spec", return_value=None):
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
                # First line should have the version
                lines = [ln for ln in output.strip().split("\n") if ln]
                assert lines[0].startswith("InstrMCP version")
                # May include version management hint
                assert "version" in output.lower()
