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

## Threading Architecture & Qt Integration

### System Structure

When running as a Jupyter extension, the system involves multiple threads and event loops:

```
┌─────────────────────────────────────────────────────────────────┐
│                     IPython Kernel (Main Thread)                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Tornado IOLoop (wraps asyncio)                           │  │
│  │    └── Qt Event Loop (integrated via %gui qt)             │  │
│  │          └── MeasureIt Sweeps (QThread workers)           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                    spawns    │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  MCP Server Thread (_server_thread)                       │  │
│  │    └── asyncio event loop (separate from kernel)          │  │
│  │          └── HTTP/SSE handlers                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **IPython Kernel (Main Thread)**
   - Runs Tornado's `AsyncIOMainLoop` which wraps an asyncio event loop
   - When Qt GUI is enabled (`%gui qt`), Qt's event loop is integrated
   - MeasureIt sweeps run on `QThread` workers but UI operations must happen on the main thread

2. **MCP Server Thread**
   - Started by `load_ipython_extension()` in a separate daemon thread
   - Runs its own asyncio event loop for handling MCP protocol
   - Cannot directly call Qt/MeasureIt methods due to thread-safety requirements

3. **MeasureIt Sweeps**
   - Each sweep runs in a `QThread` (Qt's threading)
   - The `sweep.kill()` method must be called from the sweep's Qt thread
   - Uses Qt signals/slots for cross-thread communication

### Cross-Thread Communication Challenges

**What DOES NOT work** when MCP server needs to call MeasureIt from its thread:

| Approach | Why It Fails |
|----------|--------------|
| `asyncio.call_soon_threadsafe()` | When Qt event loop is integrated with IPython, asyncio callbacks don't run while Qt is processing events |
| `tornado.ioloop.add_callback()` | Same issue - Tornado wraps asyncio, so callbacks are blocked |
| `asyncio.run_coroutine_threadsafe()` | Also blocked by Qt event loop integration |
| `QTimer.singleShot(0, callback)` | Not thread-safe when called from non-Qt thread |

**What DOES work:**

| Approach | Why It Works |
|----------|--------------|
| `QMetaObject.invokeMethod(..., Qt.QueuedConnection)` | Thread-safe Qt mechanism that posts to the target object's event queue |
| Proxy QObject on target thread | Create a `QObject` on the sweep's thread, use `moveToThread()`, then invoke its slot |

### Current Implementation: Qt Proxy Pattern

For `kill_sweep`, we use a Qt proxy pattern that bypasses asyncio entirely:

```python
class _KillProxy(QObject):
    def __init__(self, target_sweep):
        super().__init__()
        self._sweep = target_sweep

    @pyqtSlot()
    def do_kill(self):
        self._sweep.kill()

# Create proxy and move to sweep's thread
proxy = _KillProxy(sweep)
proxy.moveToThread(sweep.thread())

# Queue kill on sweep's Qt thread (thread-safe!)
QMetaObject.invokeMethod(proxy, "do_kill", Qt.QueuedConnection)
```

This works because:
1. The proxy `QObject` is moved to the sweep's Qt thread
2. `invokeMethod` with `QueuedConnection` posts an event to that thread's event queue
3. When the sweep's thread processes events, it calls `do_kill()` on the correct thread
4. This is the same mechanism MeasureIt uses internally for cross-thread operations

### Debugging Thread Issues

When debugging cross-thread issues:

1. **Check which event loop is active**: IPython with Qt GUI uses Qt's event loop, not pure asyncio
2. **Verify thread affinity**: Qt objects belong to specific threads; check with `obj.thread()`
3. **Use file-based logging**: Console logging may not work reliably across threads
4. **Test with kernel idle**: Some approaches work when kernel is busy but fail when idle

### References

- [ipykernel eventloops.py](https://github.com/ipython/ipykernel/blob/main/ipykernel/eventloops.py) - How IPython integrates with Qt
- [Qt Thread Safety](https://doc.qt.io/qt-5/threads-qobject.html) - Qt's threading model and `invokeMethod`
- [ipywidgets threading issues](https://github.com/jupyter-widgets/ipywidgets/issues/1349) - Similar challenges with widget callbacks

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

- Environment variable: `instrMCP_PATH` can be set for custom paths
- View configuration: `instrmcp config`

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
- Whenever delete or create a tool in mcp_server.py, update the hook in instrmcp.utils.stdio_proxy
- When removing features, update README.md

See [.github/CONTRIBUTING.md](../.github/CONTRIBUTING.md) for detailed contribution guidelines.
