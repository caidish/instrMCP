#!/bin/bash
# InstrMCP Claude Desktop Setup Script
# This script automatically configures Claude Desktop with the correct paths

set -e  # Exit on any error

echo "🚀 Setting up InstrMCP for Claude Desktop..."

# Get current directory (should be instrMCP root)
INSTRMCP_PATH=$(pwd)

# Find Python executable
PYTHON_PATH=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON_PATH" ]; then
    echo "❌ Error: Python not found in PATH"
    echo "   Please install Python 3 or ensure it's in your PATH"
    exit 1
fi

echo "📍 Detected paths:"
echo "   InstrMCP: $INSTRMCP_PATH"
echo "   Python:   $PYTHON_PATH"

# Check if we're in the right directory
if [ ! -f "$INSTRMCP_PATH/agentsetting/claudedesktopsetting/claude_launcher.py" ]; then
    echo "❌ Error: Please run this script from the instrMCP root directory"
    echo "   Expected to find: agentsetting/claudedesktopsetting/claude_launcher.py"
    exit 1
fi

# Determine Claude Desktop config path based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_PATH="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    CONFIG_PATH="$APPDATA/Claude/claude_desktop_config.json"
else
    echo "❌ Error: Unsupported operating system: $OSTYPE"
    exit 1
fi

# Create Claude config directory if it doesn't exist
CONFIG_DIR=$(dirname "$CONFIG_PATH")
if [ ! -d "$CONFIG_DIR" ]; then
    echo "📁 Creating Claude config directory: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR"
fi

# Backup existing config if it exists
if [ -f "$CONFIG_PATH" ]; then
    BACKUP_PATH="${CONFIG_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "💾 Backing up existing config to: $(basename "$BACKUP_PATH")"
    cp "$CONFIG_PATH" "$BACKUP_PATH"
fi

# Generate the configuration
echo "⚙️ Generating Claude Desktop configuration..."

cat > "$CONFIG_PATH" <<EOF
{
  "mcpServers": {
    "instrmcp-jupyter": {
      "command": "$PYTHON_PATH",
      "args": [
        "$INSTRMCP_PATH/agentsetting/claudedesktopsetting/claude_launcher.py"
      ],
      "env": {
        "PYTHONPATH": "$INSTRMCP_PATH",
        "instrMCP_PATH": "$INSTRMCP_PATH",
        "JUPYTER_MCP_HOST": "127.0.0.1",
        "JUPYTER_MCP_PORT": "8123"
      }
    }
  }
}
EOF

echo "✅ Configuration written to: $CONFIG_PATH"

# Set environment variable for current session
export instrMCP_PATH="$INSTRMCP_PATH"

# Add to shell profile for persistence
SHELL_CONFIG=""
if [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

if [ -n "$SHELL_CONFIG" ]; then
    if ! grep -q "instrMCP_PATH" "$SHELL_CONFIG" 2>/dev/null; then
        echo "" >> "$SHELL_CONFIG"
        echo "# InstrMCP Environment Variable" >> "$SHELL_CONFIG"
        echo "export instrMCP_PATH=\"$INSTRMCP_PATH\"" >> "$SHELL_CONFIG"
        echo "🔧 Added instrMCP_PATH to $SHELL_CONFIG"
    else
        echo "🔧 instrMCP_PATH already exists in $SHELL_CONFIG"
    fi
fi

echo ""
echo "🎉 Setup complete! Next steps:"
echo "   1. Restart Claude Desktop completely"
echo "   2. Restart your terminal (to load environment variables)"
echo "   3. Test the connection by asking Claude: 'What MCP tools are available?'"
echo ""
echo "💡 For full functionality:"
echo "   • Start Jupyter: jupyter lab"
echo "   • Load extension: %load_ext instrmcp.extensions" 
echo "   • Start server: %mcp_start"
echo ""
echo "🐛 Troubleshooting:"
echo "   • Configuration file: $CONFIG_PATH"
echo "   • Check Claude Desktop logs if connection fails"
echo "   • Ensure Python packages are installed: pip install -e ."