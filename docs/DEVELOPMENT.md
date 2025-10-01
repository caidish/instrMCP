# Development Guide

This guide covers development setup, testing, code quality, and contribution guidelines for InstrMCP.

## Setup Development Environment

```bash
# Clone repository
git clone https://github.com/caidish/instrMCP.git
cd instrMCP

# Create conda environment
conda create -n instrMCPdev python=3.11 -y
conda activate instrMCPdev

# Install in development mode with dev dependencies
pip install -e .[dev]

# Set environment variable
export instrMCP_PATH="$(pwd)"
```

## Run Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=instrmcp --cov-report=html

# Run specific test file
pytest tests/unit/test_cache.py -v

# Skip slow tests
pytest tests/ -m "not slow"
```

## Code Quality

```bash
# Format code
black instrmcp/ tests/

# Check formatting
black --check instrmcp/ tests/

# Linting
flake8 instrmcp/ tests/

# Type checking
mypy instrmcp/ --ignore-missing-imports

# Run all checks
black instrmcp/ tests/ && \
flake8 instrmcp/ tests/ --extend-ignore=F824 && \
pytest tests/ -v
```

## Testing

The project includes a comprehensive test suite with 377+ tests covering all major components.

### Test Structure

- **Unit tests**: `tests/unit/` - Isolated component tests
- **Integration tests**: `tests/integration/` - End-to-end workflows (planned)
- **Fixtures**: `tests/fixtures/` - Mock instruments, IPython, notebooks, databases
- All tests use mocks - no hardware required!

### Run Locally

```bash
pytest tests/                                    # All tests
pytest tests/ --cov=instrmcp --cov-report=html  # With coverage
```

### CI/CD

- ✅ Automated testing on Python 3.10, 3.11, 3.12
- ✅ Tests run on Ubuntu & macOS
- ✅ Code quality checks (Black, Flake8, MyPy)
- ✅ Coverage reports uploaded to Codecov

See [tests/README.md](../tests/README.md) for detailed testing guide.

## Development Workflow

### Critical Dependencies

When making changes to MCP tools:

1. **Update `stdio_proxy.py`**: Add/remove tool proxies in `instrmcp/tools/stdio_proxy.py`
2. **Check `requirements.txt`**: Ensure new Python dependencies are listed
3. **Update `pyproject.toml`**: Add dependencies and entry points as needed
4. **Update README.md**: Document new features or removed functionality

### Safe vs Unsafe Mode

The server operates in two modes:
- **Safe Mode**: Read-only access to instruments and notebooks
- **Unsafe Mode**: Allows code execution in Jupyter cells

This is controlled via the `safe_mode` parameter in server initialization and the `--unsafe` CLI flag.

### JupyterLab Extension Development

The package includes a JupyterLab extension for active cell bridging:
- Located in `instrmcp/extensions/jupyterlab/`
- **Build workflow:**
  ```bash
  cd instrmcp/extensions/jupyterlab
  jlpm run build
  ```
  - The build automatically copies files to `mcp_active_cell_bridge/labextension/`
  - This ensures `pip install -e .` will find the latest built files
- Automatically installed with the main package
- Enables real-time cell content access for MCP tools

**Important for development:** After modifying TypeScript files, you must:
1. Run `jlpm run build` in the extension directory
2. The postbuild script automatically copies files to the correct location
3. Reinstall: `pip install -e . --force-reinstall --no-deps`
4. Restart JupyterLab completely

### Configuration

- Station configuration: YAML files in `instrmcp/config/data/`
- Environment variable: `instrMCP_PATH` must be set for proper operation
- Auto-detection of installation paths via `instrmcp config`

## Contributing

### Guidelines

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Important Notes

- Always test MCP tool changes with both safe and unsafe modes
- The caching system (`cache.py`) prevents excessive instrument reads
- Rate limiting protects instruments from command flooding
- The system supports hierarchical parameter access (e.g., `ch01.voltage`)
- Jupyter cell tracking happens via IPython event hooks for real-time access
- **Always use conda environment instrMCPdev for testing**
- Remember to update stdio_proxy.py whenever we change the tools for mcp server
- Check requirements.txt when new python file is created
- Don't forget to update pyproject.toml
- Whenever delete or create a tool in mcp_server.py, update the hook in instrmcp.tools.stdio_proxy
- When removing features, update README.md

See [.github/CONTRIBUTING.md](../.github/CONTRIBUTING.md) for detailed contribution guidelines.
