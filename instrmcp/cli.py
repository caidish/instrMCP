"""InstrMCP Command Line Interface

Main CLI entry point for InstrMCP utilities.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _setup_metadata_subcommands(subparsers):
    """Setup metadata subcommand group."""
    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Manage tool/resource metadata configuration",
    )
    metadata_subparsers = metadata_parser.add_subparsers(
        dest="metadata_command",
        help="Metadata commands",
    )

    # init - Create default config
    metadata_subparsers.add_parser(
        "init",
        help="Create default ~/.instrmcp/metadata.yaml with examples",
    )

    # edit - Open config in editor
    metadata_subparsers.add_parser(
        "edit",
        help="Open config in $EDITOR",
    )

    # list - Show all overrides
    metadata_subparsers.add_parser(
        "list",
        help="Show all configured overrides",
    )

    # show - Show specific override
    show_parser = metadata_subparsers.add_parser(
        "show",
        help="Show specific tool or resource override",
    )
    show_parser.add_argument(
        "name",
        help="Tool name or resource URI to show",
    )

    # path - Show config file path
    metadata_subparsers.add_parser(
        "path",
        help="Show config file path",
    )

    # validate - Validate config against running server (via stdio proxy)
    validate_parser = metadata_subparsers.add_parser(
        "validate",
        help="Validate config against running server (via stdio proxy)",
    )
    validate_parser.add_argument(
        "--mcp-url",
        default="http://127.0.0.1:8123",
        help="MCP server URL (default: http://127.0.0.1:8123)",
    )
    validate_parser.add_argument(
        "--launcher-path",
        type=Path,
        help="Path to claude_launcher.py (auto-detected if not specified)",
    )
    validate_parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Timeout for proxy communication in seconds (default: 15)",
    )

    return metadata_parser


def _handle_metadata_command(args):
    """Handle metadata subcommands."""
    from instrmcp.utils.metadata_config import (
        DEFAULT_CONFIG_PATH,
        generate_default_config_yaml,
        load_config,
    )

    if args.metadata_command == "init":
        if DEFAULT_CONFIG_PATH.exists():
            print(f"Config file already exists: {DEFAULT_CONFIG_PATH}")
            print("Use 'instrmcp metadata edit' to modify it.")
            return 1

        # Create default config with examples
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(generate_default_config_yaml())
        os.chmod(DEFAULT_CONFIG_PATH, 0o600)
        print(f"Created config file: {DEFAULT_CONFIG_PATH}")
        print("Edit this file to customize tool/resource metadata.")
        print("Server restart required for changes to take effect.")
        return 0

    elif args.metadata_command == "edit":
        if not DEFAULT_CONFIG_PATH.exists():
            print(f"Config file not found: {DEFAULT_CONFIG_PATH}")
            print("Run 'instrmcp metadata init' to create it first.")
            return 1

        editor = os.environ.get("EDITOR", "vi")
        try:
            subprocess.run([editor, str(DEFAULT_CONFIG_PATH)])
            print("\nServer restart required for changes to take effect.")
            return 0
        except FileNotFoundError:
            print(f"Editor not found: {editor}")
            print("Set $EDITOR environment variable to your preferred editor.")
            return 1

    elif args.metadata_command == "list":
        try:
            config = load_config()
        except ImportError:
            print("PyYAML not installed. Install with: pip install pyyaml")
            return 1
        except ValueError as e:
            print(f"Invalid config: {e}")
            return 1

        if not config.tools and not config.resources and not config.resource_templates:
            print("No metadata overrides configured.")
            print(f"Config file: {DEFAULT_CONFIG_PATH}")
            if not DEFAULT_CONFIG_PATH.exists():
                print("Run 'instrmcp metadata init' to create a config file.")
            return 0

        print(f"Metadata Configuration ({DEFAULT_CONFIG_PATH})")
        print(f"Version: {config.version}, Strict: {config.strict}")
        print()

        if config.tools:
            print(f"Tools ({len(config.tools)}):")
            for tool_name, override in sorted(config.tools.items()):
                title_str = f" (title: {override.title})" if override.title else ""
                desc_str = " [has description]" if override.description else ""
                args_str = (
                    f" [{len(override.arguments)} args]" if override.arguments else ""
                )
                print(f"  - {tool_name}{title_str}{desc_str}{args_str}")
            print()

        if config.resources:
            print(f"Resources ({len(config.resources)}):")
            for uri, override in sorted(config.resources.items()):
                name_str = f" (name: {override.name})" if override.name else ""
                desc_str = " [has description]" if override.description else ""
                print(f"  - {uri}{name_str}{desc_str}")
            print()

        if config.resource_templates:
            print(f"Resource Templates ({len(config.resource_templates)}):")
            for uri, override in sorted(config.resource_templates.items()):
                name_str = f" (name: {override.name})" if override.name else ""
                desc_str = " [has description]" if override.description else ""
                print(f"  - {uri}{name_str}{desc_str}")

        return 0

    elif args.metadata_command == "show":
        try:
            config = load_config()
        except ImportError:
            print("PyYAML not installed. Install with: pip install pyyaml")
            return 1
        except ValueError as e:
            print(f"Invalid config: {e}")
            return 1

        name = args.name

        # Check tools
        if name in config.tools:
            override = config.tools[name]
            print(f"Tool: {name}")
            if override.title:
                print(f"  Title: {override.title}")
            if override.description:
                print(f"  Description: {override.description[:100]}...")
            if override.arguments:
                print(f"  Arguments ({len(override.arguments)}):")
                for arg_name, arg_override in override.arguments.items():
                    if arg_override.description:
                        print(f"    - {arg_name}: {arg_override.description[:50]}...")
            return 0

        # Check resources
        if name in config.resources:
            override = config.resources[name]
            print(f"Resource: {name}")
            if override.name:
                print(f"  Name: {override.name}")
            if override.description:
                print(f"  Description: {override.description[:100]}...")
            if override.use_when:
                print(f"  Use when: {override.use_when}")
            if override.example:
                print(f"  Example: {override.example}")
            return 0

        # Check resource templates
        if name in config.resource_templates:
            override = config.resource_templates[name]
            print(f"Resource Template: {name}")
            if override.name:
                print(f"  Name: {override.name}")
            if override.description:
                print(f"  Description: {override.description[:100]}...")
            return 0

        print(f"Not found: {name}")
        print("Available items:")
        if config.tools:
            print(f"  Tools: {', '.join(sorted(config.tools.keys()))}")
        if config.resources:
            print(f"  Resources: {', '.join(sorted(config.resources.keys()))}")
        if config.resource_templates:
            print(f"  Templates: {', '.join(sorted(config.resource_templates.keys()))}")
        return 1

    elif args.metadata_command == "path":
        print(DEFAULT_CONFIG_PATH)
        if DEFAULT_CONFIG_PATH.exists():
            print("(exists)")
        else:
            print("(not found - run 'instrmcp metadata init' to create)")
        return 0

    elif args.metadata_command == "validate":
        return _handle_metadata_validate(args)

    else:
        print("Usage: instrmcp metadata <command>")
        print("Commands: init, edit, list, show, path, validate")
        return 1


def _handle_metadata_validate(args):
    """Handle metadata validate subcommand.

    Validates the user's metadata config against the running server schema
    by communicating through the STDIO proxy. This tests the full path:

    CLI → STDIO → stdio_proxy → HTTP → MCP Server (8123)
    """
    from instrmcp.utils.metadata_config import (
        DEFAULT_CONFIG_PATH,
        load_config,
        validate_config_against_server,
    )
    from instrmcp.utils.stdio_proxy import StdioMCPClient

    print("InstrMCP Metadata Validator")
    print("=" * 40)
    print()

    # Load user config
    print(f"Loading config from: {DEFAULT_CONFIG_PATH}")
    try:
        config = load_config()
    except ImportError:
        print("ERROR: PyYAML not installed. Install with: pip install pyyaml")
        return 1
    except ValueError as e:
        print(f"ERROR: Invalid config file: {e}")
        return 1

    if not DEFAULT_CONFIG_PATH.exists():
        print("Note: No user config found, validating baseline config only.")
    else:
        print(
            f"Config loaded: {len(config.tools)} tools, {len(config.resources)} resources"
        )
    print()

    # Connect to server via STDIO proxy
    print("Connecting to MCP server via STDIO proxy...")
    print(f"  MCP URL: {args.mcp_url}")

    launcher_path = str(args.launcher_path) if args.launcher_path else None
    client = StdioMCPClient(launcher_path=launcher_path, mcp_url=args.mcp_url)

    try:
        client.start(timeout=args.timeout)
        print("  STDIO proxy connected successfully")
        print()

        # Get tools and resources
        print("Fetching registered tools and resources...")
        tools_list = client.list_tools(timeout=args.timeout)
        resources_list = client.list_resources(timeout=args.timeout)

        print(f"  Found {len(tools_list)} tools")
        print(f"  Found {len(resources_list)} resources")
        print()

        # Convert to dicts for validation
        registered_tools = {t["name"]: t for t in tools_list if "name" in t}
        registered_resources = {r["uri"]: r for r in resources_list if "uri" in r}

        # Validate config
        print("Validating config against server schema...")
        messages = validate_config_against_server(
            config, registered_tools, registered_resources
        )

        if not messages:
            print()
            print("✅ Validation passed! Config is valid.")
            return 0

        print()
        print("Validation issues found:")
        errors = [m for m in messages if m.startswith("ERROR:")]
        warnings = [m for m in messages if m.startswith("WARNING:")]

        for msg in errors:
            print(f"  ❌ {msg}")
        for msg in warnings:
            print(f"  ⚠️  {msg}")

        print()
        if errors:
            print(
                f"❌ Validation failed: {len(errors)} error(s), {len(warnings)} warning(s)"
            )
            if config.strict:
                print("   Tip: Set 'strict: false' in config to ignore unknown items.")
            return 1
        else:
            print(f"⚠️  Validation passed with {len(warnings)} warning(s)")
            return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print()
        print("Make sure the MCP server is running:")
        print("  1. Start JupyterLab with the instrMCP extension")
        print("  2. Run %mcp_start in a notebook cell")
        return 1
    except RuntimeError as e:
        print(f"ERROR: Communication failed: {e}")
        print()
        print("Make sure the MCP server is running at", args.mcp_url)
        return 1
    finally:
        client.stop()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="InstrMCP: Instrumentation Control MCP Server Suite",
        prog="instrmcp",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Config command
    subparsers.add_parser("config", help="Show configuration information")

    # Version command
    subparsers.add_parser("version", help="Show version information")

    # Metadata command group
    _setup_metadata_subcommands(subparsers)

    args = parser.parse_args()

    if args.command == "config":
        from . import __version__

        package_path = Path(__file__).parent
        print("InstrMCP Configuration:")
        print(f"Version: {__version__}")
        print(f"Package path: {package_path}")
        print()

        # Check for optional dependencies
        print("Optional Extensions:")

        # Check MeasureIt using importlib to avoid full import crash
        import importlib.util
        import subprocess

        measureit_spec = importlib.util.find_spec("measureit")
        if measureit_spec is not None:
            # Try to import in subprocess to avoid crashing main process
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import measureit; print(getattr(measureit, '__version__', 'unknown'))",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,  # Reduced timeout since imports should be fast
                )
                if result.returncode == 0:
                    measureit_version = result.stdout.strip()
                    print(f"  ✅ measureit: {measureit_version}")
                else:
                    print("  ⚠️  measureit: Installed but failed to import")
                    # Extract first meaningful error line
                    errors = [
                        line
                        for line in result.stderr.split("\n")
                        if line.strip() and not line.startswith(" ")
                    ]
                    error_msg = errors[-1] if errors else "Unknown error"
                    if len(error_msg) > 70:
                        error_msg = error_msg[:70] + "..."
                    print(f"     Error: {error_msg}")
            except subprocess.TimeoutExpired:
                print("  ⚠️  measureit: Installed but import timed out")
                print("     Possible dependency issue (e.g., NumPy compatibility)")
            except Exception as e:
                print("  ⚠️  measureit: Installed but check failed")
                print(f"     Error: {str(e)[:70]}")
        else:
            print("  ❌ measureit: Not installed")
            print("     Install from: https://github.com/nanophys/MeasureIt")
    elif args.command == "version":
        from . import __version__

        print(f"InstrMCP version {__version__}")
        print("\nFor version management, use: python tools/version.py --help")
    elif args.command == "metadata":
        result = _handle_metadata_command(args)
        sys.exit(result)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
