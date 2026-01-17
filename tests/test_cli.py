"""
Unit tests for cli.py module.

Tests CLI commands (config, version), argument parsing,
and error handling for the InstrMCP command-line interface.
"""

import pytest
from unittest.mock import patch
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

    def test_config_command(self):
        """Test config command prints configuration."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("importlib.util.find_spec", return_value=None):
                    cli.main()
                    output = mock_stdout.getvalue()
                    assert "InstrMCP Configuration:" in output
                    assert "Version:" in output
                    assert "Package path:" in output

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


class TestCLIIntegration:
    """Test CLI integration."""

    def test_config_command_no_asyncio_run(self):
        """Test that config command does not use asyncio."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch("asyncio.run") as mock_run:
                with patch("sys.stdout", new_callable=StringIO):
                    with patch("importlib.util.find_spec", return_value=None):
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

    def test_config_shows_version(self):
        """Test config command shows version."""
        with patch("sys.argv", ["instrmcp", "config"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("importlib.util.find_spec", return_value=None):
                    cli.main()
                    output = mock_stdout.getvalue()
                    assert "InstrMCP Configuration:" in output
                    assert "Version:" in output


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
                with patch("importlib.util.find_spec", return_value=None):
                    cli.main()
                    output = mock_stdout.getvalue()

                    # Check all expected lines are present
                    assert "InstrMCP Configuration:" in output
                    assert "Version:" in output
                    assert "Package path:" in output
                    assert "Optional Extensions:" in output

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
