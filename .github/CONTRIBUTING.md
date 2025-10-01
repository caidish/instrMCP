# Contributing to InstrMCP

Thank you for your interest in contributing to InstrMCP! This document provides guidelines for contributing.

## Development Setup

1. **Fork and clone the repository:**
```bash
git clone https://github.com/YOUR_USERNAME/instrMCP.git
cd instrMCP
```

2. **Create a conda environment:**
```bash
conda create -n instrMCPdev python=3.11 -y
conda activate instrMCPdev
```

3. **Install in development mode:**
```bash
pip install -e .[dev]
```

4. **Set environment variable:**
```bash
export instrMCP_PATH="$(pwd)"
echo 'export instrMCP_PATH="'$(pwd)'"' >> ~/.zshrc  # or ~/.bashrc
```

## Running Tests

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

Before submitting a PR, ensure your code passes all checks:

```bash
# Format code
black instrmcp/ tests/

# Run linter
flake8 instrmcp/ tests/

# Type checking
mypy instrmcp/ --ignore-missing-imports

# Run all checks
black instrmcp/ tests/ && \
flake8 instrmcp/ tests/ && \
mypy instrmcp/ --ignore-missing-imports && \
pytest tests/
```

## Pull Request Process

1. **Create a feature branch:**
```bash
git checkout -b feature/amazing-feature
```

2. **Make your changes:**
   - Write tests for new features
   - Update documentation as needed
   - Follow existing code style

3. **Commit your changes:**
```bash
git add .
git commit -m "Add amazing feature"
```

4. **Push to your fork:**
```bash
git push origin feature/amazing-feature
```

5. **Open a Pull Request:**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your branch
   - Fill in the PR template

## Coding Standards

- **Python Style**: Follow PEP 8, enforced by Black formatter
- **Line Length**: 88 characters (Black default)
- **Type Hints**: Use type hints where possible
- **Docstrings**: Use Google-style docstrings
- **Tests**: Write tests for all new functionality (aim for 80%+ coverage)

## Testing Guidelines

- Place tests in appropriate directory (`tests/unit/` or `tests/integration/`)
- Use fixtures from `conftest.py` for common test data
- Mock external dependencies (instruments, IPython, etc.)
- Follow the Arrange-Act-Assert pattern
- Use descriptive test names: `test_<feature>_<condition>`

## Documentation

- Update `CLAUDE.md` for significant architectural changes
- Update `tests/README.md` if adding new test patterns
- Update main `README.md` for user-facing changes
- Add docstrings to all public functions and classes

## CI/CD

All PRs automatically run:
- ✅ Tests on Python 3.9, 3.10, 3.11, 3.12
- ✅ Tests on Ubuntu and macOS
- ✅ Code formatting check (Black)
- ✅ Linting (Flake8)
- ✅ Type checking (MyPy)

Make sure all checks pass before requesting review.

## Release Process

Releases are managed by maintainers:
1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create GitHub release
4. Package is automatically published to PyPI

## Questions?

- Open an issue for bugs or feature requests
- Join discussions for questions
- Check existing issues before creating new ones

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
