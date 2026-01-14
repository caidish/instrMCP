"""InstrMCP Command Line Interface

Main CLI entry point for InstrMCP utilities.
"""

import argparse
import sys
from pathlib import Path


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
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
