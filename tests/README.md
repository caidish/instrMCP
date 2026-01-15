# InstrMCP Test Suite

Comprehensive test suite for the InstrMCP package with one-to-one coverage of all modules.

## Test Structure

```
tests/
├── conftest.py                           # Shared pytest fixtures
├── test_cli.py                          # CLI interface tests (47 tests)
├── test_config.py                       # Configuration tests (40 tests)
├── unit/                                # Unit tests (isolated components)
│   ├── test_cache.py                    # Cache & rate limiting (20 tests)
│   ├── test_stdio_proxy.py              # STDIO proxy (52 tests)
│   ├── servers/
│   │   ├── test_qcodes_tools.py         # QCodes registrar (11 tests)
│   │   ├── test_notebook_tools.py       # Notebook registrar (27 tests)
│   │   ├── test_database_tools.py       # Database registrar (16 tests)
│   │   ├── test_measureit_tools.py      # MeasureIt registrar (14 tests)
│   │   └── test_resources.py            # Resource registrar (14 tests)
│   └── extensions/
│       ├── test_measureit_templates.py  # MeasureIt templates (62 tests)
│       ├── test_database_resources.py   # Database resources (32 tests)
│       └── test_database_query_tools.py # Database queries (45 tests)
├── integration/                         # Integration tests (planned)
│   ├── test_mcp_server.py              # Full server lifecycle
│   ├── test_jupyter_extension.py       # Magic commands
│   ├── test_active_cell_bridge.py      # Cell capture
│   ├── test_tools_safe_mode.py         # Safe mode end-to-end
│   ├── test_tools_unsafe_mode.py       # Unsafe mode end-to-end
│   └── test_stdio_client.py            # STDIO proxy end-to-end
├── playwright/                          # Playwright-driven MCP metadata E2E
└── fixtures/                            # Test data and mocks
    ├── mock_instruments.py             # Mock QCodes instruments
    ├── mock_ipython.py                 # Mock IPython kernel
    ├── sample_notebooks.py             # Sample notebook cells
    └── sample_databases.py             # Mock database data
```

## Test Statistics

**Current Status:**
- **Total Tests:** 380+ tests
- **Unit Tests:** 380+ tests ✅
- **Integration Tests:** Planned (5 test files)
- **Coverage Target:** 80%+ for core modules

**Test Breakdown:**
- CLI & Config: 87 tests
- Core Components: 72 tests
- Server Registrars: 82 tests

## Important Testing Guidelines

### Avoid MagicMock File Artifacts

When mocking `Path` or file system operations, ensure mocks don't create actual files:

**❌ Bad - Creates files with MagicMock names:**
```python
@patch("some_module.Path")
def test_something(mock_path_cls):
    mock_path = MagicMock()
    mock_path_cls.return_value = mock_path
    # If code calls str(mock_path), it returns "<MagicMock...>"
    # QCodes or other libraries may create files with this name!
```

**✅ Good - Use spec and configure string representation:**
```python
@patch("some_module.Path")
def test_something(mock_path_cls, tmp_path):
    mock_path = MagicMock(spec=Path)
    mock_path.__str__.return_value = str(tmp_path / "test.db")
    mock_path.__fspath__.return_value = str(tmp_path / "test.db")
    mock_path_cls.return_value = mock_path
```

**✅ Better - Don't mock Path at all, use temp directories:**
```python
def test_something(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(test_db))
    # Test with real Path objects, just in temp location
```

Files with names like `<MagicMock name='...'>` are automatically ignored by `.gitignore`, but it's better to prevent their creation entirely.
- Extensions: 139 tests

## Running Tests

### Run All Tests
```bash
# Run all tests with coverage
pytest

# Run all tests verbosely
pytest -v

# Run with coverage report
pytest --cov=instrmcp --cov-report=html
```

### Run Specific Test Suites
```bash
# Unit tests only
pytest tests/unit/

# Specific module
pytest tests/test_cli.py
pytest tests/unit/test_cache.py

# Server registrar tests
pytest tests/unit/servers/

# Extension tests
pytest tests/unit/extensions/

# Integration tests (when available)
pytest tests/integration/
```

### Run Tests by Marker
```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run only async tests
pytest -m asyncio

# Skip hardware-dependent tests
pytest -m "not hardware"
```

### Run Specific Tests
```bash
# By test name pattern
pytest -k "test_cache"
pytest -k "TestReadCache"

# Single test function
pytest tests/unit/test_cache.py::TestReadCache::test_cache_initialization
```

## Test Markers

Tests are marked with the following pytest markers:

- **`@pytest.mark.slow`**: Tests taking >1 second (deselect with `-m "not slow"`)
- **`@pytest.mark.integration`**: Integration tests requiring multiple components
- **`@pytest.mark.hardware`**: Tests requiring physical hardware (skipped by default)
- **`@pytest.mark.asyncio`**: Async tests using pytest-asyncio

## Mock Components

The test suite uses comprehensive mocks to avoid hardware dependencies:

### Available Fixtures (from conftest.py)

**General:**
- `event_loop` - Async event loop for async tests
- `temp_dir` - Temporary directory for file operations

**IPython/Jupyter:**
- `mock_ipython` - Mock IPython kernel with event system
- `mock_ipython_namespace` - Mock user namespace with test variables
- `sample_cell_content` - Sample Jupyter cell content
- `sample_notebook_cells` - Complete notebook cell list

**QCodes:**
- `mock_qcodes_instrument` - Mock instrument with parameters
- `mock_qcodes_station` - Mock station with multiple instruments

**Database:**
- `mock_database_path` - Temporary database path
- `sample_experiment_data` - Experiment metadata
- `sample_dataset_data` - Dataset metadata

**MeasureIt:**
- `mock_measureit_sweep` - Mock sweep with configuration

### Mock Instruments (from fixtures/mock_instruments.py)

- **MockDAC**: Digital-to-Analog Converter with channels
- **MockDMM**: Digital Multimeter
- **MockVNA**: Vector Network Analyzer
- **MockParameter**: Generic QCodes parameter
- **MockChannel**: Instrument channel/submodule

## Writing New Tests

### Test File Template

```python
"""
Unit tests for <module_name>.py

Brief description of what is tested.
"""

import pytest
from instrmcp.path.to.module import ClassToTest


class TestClassName:
    """Test ClassName from module."""

    def test_feature_success(self):
        """Test that feature works correctly."""
        # Arrange
        obj = ClassToTest()

        # Act
        result = obj.method()

        # Assert
        assert result == expected_value

    @pytest.mark.asyncio
    async def test_async_feature(self):
        """Test async feature."""
        obj = ClassToTest()
        result = await obj.async_method()
        assert result is not None
```

### Best Practices

1. **Use Fixtures**: Leverage existing fixtures from `conftest.py` for common test data
2. **Mock External Dependencies**: Use `unittest.mock` or `pytest-mock` for external services
3. **Test Both Success and Failure**: Include tests for error conditions
4. **Clear Test Names**: Use descriptive names like `test_<feature>_<condition>`
5. **Docstrings**: Add docstrings explaining what each test verifies
6. **Arrange-Act-Assert**: Follow AAA pattern for test structure
7. **Async Tests**: Use `@pytest.mark.asyncio` for async functions
8. **Parametrize**: Use `@pytest.mark.parametrize` for testing multiple inputs

## Code Coverage

### Generate Coverage Report

```bash
# Terminal report
pytest --cov=instrmcp --cov-report=term-missing

# HTML report (browse to htmlcov/index.html)
pytest --cov=instrmcp --cov-report=html

# XML report (for CI/CD)
pytest --cov=instrmcp --cov-report=xml
```

### Coverage Configuration

Coverage settings in `pyproject.toml`:
- **Source:** `instrmcp/` package
- **Omitted:** Tests, __pycache__, site-packages
- **Target:** 80%+ coverage for core modules

## Continuous Integration

### GitHub Actions Workflow (Example)

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e .[dev]
      - run: pytest --cov=instrmcp --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Install package in development mode
pip install -e .

# Install test dependencies
pip install -e .[dev]
```

**Async Test Warnings:**
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Check asyncio_mode in pyproject.toml
asyncio_mode = "auto"
```

**Coverage Not Working:**
```bash
# Ensure coverage source is correct in pyproject.toml
[tool.coverage.run]
source = ["instrmcp"]
```

**Mock Not Found:**
```bash
# Check that conftest.py is in tests/ directory
# Fixtures are automatically discovered by pytest
```

## Development Workflow

1. **Write Tests First** (TDD approach recommended)
2. **Run Tests Frequently** during development
3. **Check Coverage** to ensure new code is tested
4. **Use Markers** to organize tests
5. **Mock External Dependencies** to keep tests fast and isolated
6. **Document Test Purpose** in docstrings

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [QCodes Testing Guide](https://qcodes.github.io/Qcodes/examples/writing_drivers/Testing-QCoDeS-instrument-drivers.html)

## Future Improvements

- [ ] Add integration tests for full MCP server lifecycle
- [ ] Add integration tests for Jupyter extension magic commands
- [ ] Add integration tests for active cell bridge
- [ ] Add end-to-end tests for safe/unsafe mode workflows
- [ ] Add STDIO proxy client-server integration tests
- [ ] Increase coverage to 90%+ for all modules
- [ ] Add performance benchmarks for critical paths
- [ ] Add mutation testing with `mutmut`
