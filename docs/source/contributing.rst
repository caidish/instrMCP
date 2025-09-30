Contributing
============

Thank you for your interest in contributing to InstrMCP!

Getting Started
---------------

1. **Fork the repository** on GitHub
2. **Clone your fork**:

.. code-block:: bash

   git clone https://github.com/YOUR_USERNAME/instrMCP.git
   cd instrMCP

3. **Set up development environment**:

.. code-block:: bash

   conda create -n instrMCPdev python=3.11
   conda activate instrMCPdev
   pip install -e .[dev]

4. **Create a branch** for your changes:

.. code-block:: bash

   git checkout -b feature/my-new-feature

Development Workflow
--------------------

Code Changes
~~~~~~~~~~~~

1. Make your changes in a feature branch
2. Follow the existing code style
3. Add tests for new functionality
4. Update documentation as needed

Testing
~~~~~~~

Run tests before submitting:

.. code-block:: bash

   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=instrmcp

   # Run specific test file
   pytest tests/test_tools.py

Code Quality
~~~~~~~~~~~~

Format code with Black:

.. code-block:: bash

   black instrmcp/ tests/

Check types with mypy:

.. code-block:: bash

   mypy instrmcp/

Lint with flake8:

.. code-block:: bash

   flake8 instrmcp/

Documentation
~~~~~~~~~~~~~

Build documentation locally:

.. code-block:: bash

   cd docs
   make html

   # View in browser
   open build/html/index.html

JupyterLab Extension
~~~~~~~~~~~~~~~~~~~~

After modifying TypeScript:

.. code-block:: bash

   cd instrmcp/extensions/jupyterlab
   jlpm run build
   pip install -e . --force-reinstall --no-deps

Guidelines
----------

Code Style
~~~~~~~~~~

- Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Keep functions focused and small
- Prefer explicit over implicit

Example:

.. code-block:: python

   def get_parameter_value(name: str, cache: bool = True) -> Dict[str, Any]:
       """Get parameter value from QCodes instrument.

       Args:
           name: Parameter name in format "instrument.parameter"
           cache: Whether to use cached value

       Returns:
           Dictionary with value, timestamp, and unit

       Raises:
           ValueError: If parameter name is invalid
       """
       # Implementation
       pass

Docstring Format
~~~~~~~~~~~~~~~~

Use Google style docstrings:

.. code-block:: python

   def my_function(arg1: str, arg2: int = 0) -> bool:
       """Short description.

       Longer description with more details about what the
       function does and how to use it.

       Args:
           arg1: Description of arg1
           arg2: Description of arg2

       Returns:
           Description of return value

       Raises:
           ValueError: Description of when this is raised
           TypeError: Description of when this is raised

       Example:
           >>> result = my_function("test", 42)
           >>> print(result)
           True
       """
       pass

Commit Messages
~~~~~~~~~~~~~~~

Follow conventional commits:

.. code-block:: text

   feat: Add database query caching
   fix: Resolve cell content sync issue
   docs: Update API reference for new tools
   refactor: Simplify tool registration
   test: Add tests for cursor movement
   chore: Update dependencies

Format:

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation only
- **refactor**: Code change that neither fixes bug nor adds feature
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

Pull Request Process
---------------------

1. **Update documentation** if needed
2. **Add tests** for new features
3. **Run test suite** and ensure all pass
4. **Update changelog** in ``CHANGELOG.md``
5. **Submit pull request** with clear description

Pull Request Template:

.. code-block:: markdown

   ## Description
   Brief description of changes

   ## Motivation
   Why is this change needed?

   ## Changes
   - List of specific changes
   - Another change

   ## Testing
   How was this tested?

   ## Checklist
   - [ ] Tests pass
   - [ ] Documentation updated
   - [ ] Changelog updated
   - [ ] Code formatted with Black
   - [ ] Type hints added

Areas for Contribution
----------------------

High Priority
~~~~~~~~~~~~~

- Additional instrument drivers
- More measurement templates
- Better error messages
- Performance improvements
- Test coverage

Medium Priority
~~~~~~~~~~~~~~~

- Documentation improvements
- Example notebooks
- Tutorial videos
- Blog posts
- Translation

Low Priority (but welcome!)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Logo design
- Website improvements
- Social media presence
- Conference presentations

Specific Contribution Ideas
----------------------------

New MCP Tools
~~~~~~~~~~~~~

Add tools in appropriate registrar:

.. code-block:: python

   # In registrars/qcodes_tools.py
   @mcp.tool(name="qcodes/set_parameter")
   async def set_parameter(name: str, value: float) -> List[TextContent]:
       """Set a QCodes parameter value (unsafe mode only)."""
       # Implementation
       pass

New Resources
~~~~~~~~~~~~~

Add resources for LLM context:

.. code-block:: python

   # In registrars/resources.py
   @mcp.resource("instrument_manual")
   async def instrument_manual() -> List[TextContent]:
       """Provide instrument documentation."""
       manual_text = load_manual()
       return [TextContent(type="text", text=manual_text)]

JupyterLab Extension Features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extend TypeScript functionality:

.. code-block:: typescript

   // In src/index.ts
   const handleNewFeature = async (
     kernel: Kernel.IKernelConnection,
     comm: any,
     data: any
   ) => {
     // Implementation
   }

Database Queries
~~~~~~~~~~~~~~~~

Add specialized database queries:

.. code-block:: python

   # In extensions/database/query_tools.py
   def find_by_pattern(pattern: str) -> List[Dict]:
       """Find measurements matching pattern."""
       # Implementation
       pass

Testing Guidelines
------------------

Test Structure
~~~~~~~~~~~~~~

.. code-block:: python

   def test_feature_name():
       """Test description."""
       # Arrange
       setup = create_test_setup()

       # Act
       result = perform_action(setup)

       # Assert
       assert result == expected_value

Mock Instruments
~~~~~~~~~~~~~~~~

Use QCodes mock instruments:

.. code-block:: python

   from qcodes.tests.instrument_mocks import DummyInstrument

   def test_instrument_reading():
       instrument = DummyInstrument("mock")
       # Test with mock
       instrument.close()

Async Testing
~~~~~~~~~~~~~

For async functions:

.. code-block:: python

   import pytest

   @pytest.mark.asyncio
   async def test_async_feature():
       result = await async_function()
       assert result is not None

Documentation Contributions
----------------------------

Documentation Types
~~~~~~~~~~~~~~~~~~~

- **Tutorials**: Step-by-step guides
- **How-to guides**: Solutions to specific problems
- **Reference**: Technical descriptions
- **Explanations**: Understanding concepts

Writing Style
~~~~~~~~~~~~~

- Clear and concise
- Use examples
- Include code snippets
- Link to related content
- Test all commands

Adding Examples
~~~~~~~~~~~~~~~

Place example notebooks in ``examples/``:

.. code-block:: text

   examples/
   ├── basic_usage.ipynb
   ├── advanced_measurements.ipynb
   └── custom_tools.ipynb

Code of Conduct
---------------

Be Respectful
~~~~~~~~~~~~~

- Treat everyone with respect
- Welcome newcomers
- Be patient with questions
- Give constructive feedback

Be Professional
~~~~~~~~~~~~~~~

- Keep discussions on-topic
- Avoid inflammatory language
- Respect different viewpoints
- Acknowledge contributions

Community
---------

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Pull Requests**: Code contributions

Getting Help
------------

If you need help:

1. Check existing documentation
2. Search GitHub issues
3. Ask in GitHub Discussions
4. Open a new issue with details

Questions?
----------

Feel free to open an issue or discussion on GitHub!

Thank you for contributing to InstrMCP! 🎉