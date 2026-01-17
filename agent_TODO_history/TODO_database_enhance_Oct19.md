# Database Path Enhancement Plan (Revised)

## Overview
Enhance database path handling in InstrMCP to provide better error messages, discovery tools, and clearer documentation. The basic path resolution is already implemented and supports 3 formats.

## Current Implementation Status

### ✅ Already Implemented (Phase 1)
The `_resolve_database_path()` function in `query_tools.py` already supports 3 path formats:

1. **Explicit path**: `database_path="C:\\Users\\...\\mydata.db"` (absolute path)
2. **MeasureItHome default**: `database_path=None` → uses `$MeasureItHome/Databases/Example_database.db`
3. **QCodes config fallback**: If MeasureItHome not set, falls back to `qc.config.core.db_location`

### MeasureIt Helper Functions Available
- `measureit.get_data_dir()` - Returns base MeasureIt directory (checks MEASUREIT_HOME, MeasureItHome, platform defaults)
- `measureit.get_path("databases")` - Returns databases subdirectory path

## Remaining Work

### Phase 2: Enhanced Error Messages ⭐ (HIGH PRIORITY)

**Goal**: Provide helpful error messages when database path is invalid or not found.

**Implementation** in `instrmcp/extensions/database/query_tools.py`:

```python
def _resolve_database_path(database_path: Optional[str] = None) -> tuple[str, dict]:
    """
    Resolve the database path using the following priority:
    1. Provided database_path parameter
    2. MeasureIt get_path("databases") -> Example_database.db
    3. QCodes default configuration

    Args:
        database_path: Explicit database path

    Returns:
        tuple: (resolved_path, resolution_info)
            resolved_path: Absolute path to database file
            resolution_info: Dict with 'source', 'available_databases', 'error_details'

    Raises:
        FileNotFoundError: If database path doesn't exist, with helpful suggestions
    """
    resolution_info = {
        'source': None,
        'available_databases': [],
        'tried_path': None
    }

    # Case 1: Explicit path provided
    if database_path:
        db_path = Path(database_path)
        resolution_info['tried_path'] = str(db_path)

        if db_path.exists():
            resolution_info['source'] = 'explicit'
            return str(db_path), resolution_info
        else:
            # Path doesn't exist - provide helpful error
            resolution_info['available_databases'] = _list_available_databases()
            raise FileNotFoundError(
                f"Database not found: {database_path}\n\n"
                f"Available databases:\n" +
                _format_available_databases(resolution_info['available_databases']) +
                f"\n\nTip: Use database_list_available() to discover all databases"
            )

    # Case 2: Try MeasureIt default
    try:
        from measureit import get_path
        db_dir = get_path("databases")
        default_db = db_dir / "Example_database.db"
        resolution_info['tried_path'] = str(default_db)

        if default_db.exists():
            resolution_info['source'] = 'measureit_default'
            return str(default_db), resolution_info
    except (ImportError, ValueError):
        # MeasureIt not available or get_path failed
        pass

    # Case 3: Fall back to QCodes config
    qcodes_db = Path(qc.config.core.db_location)
    resolution_info['tried_path'] = str(qcodes_db)

    if qcodes_db.exists():
        resolution_info['source'] = 'qcodes_config'
        return str(qcodes_db), resolution_info

    # No database found - provide comprehensive error
    resolution_info['available_databases'] = _list_available_databases()
    raise FileNotFoundError(
        f"No database found. Tried:\n"
        f"  1. MeasureIt default: {db_dir / 'Example_database.db' if 'db_dir' in locals() else 'N/A (MeasureIt not available)'}\n"
        f"  2. QCodes config: {qcodes_db}\n\n"
        f"Available databases:\n" +
        _format_available_databases(resolution_info['available_databases']) +
        f"\n\nTip: Set MeasureItHome environment variable or provide explicit path"
    )


def _list_available_databases() -> list[dict]:
    """
    List available databases by searching common locations.

    Returns:
        List of dicts with 'name', 'path', 'source', 'size_mb', 'accessible'
    """
    databases = []

    # Check MeasureIt databases directory
    try:
        from measureit import get_path
        db_dir = get_path("databases")

        if db_dir.exists():
            for db_file in db_dir.glob("*.db"):
                databases.append({
                    'name': db_file.name,
                    'path': str(db_file),
                    'source': 'measureit',
                    'size_mb': round(db_file.stat().st_size / 1024 / 1024, 2),
                    'accessible': True
                })
    except (ImportError, ValueError):
        pass

    # Check QCodes config location
    qcodes_db = Path(qc.config.core.db_location)
    if qcodes_db.exists():
        databases.append({
            'name': qcodes_db.name,
            'path': str(qcodes_db),
            'source': 'qcodes_config',
            'size_mb': round(qcodes_db.stat().st_size / 1024 / 1024, 2),
            'accessible': True
        })

    return databases


def _format_available_databases(databases: list[dict]) -> str:
    """Format database list for error messages."""
    if not databases:
        return "  (none found)"

    lines = []
    for db in databases:
        lines.append(f"  - {db['name']} ({db['size_mb']} MB) [{db['source']}]")
        lines.append(f"    {db['path']}")

    return "\n".join(lines)
```

**Update all tool functions** to include resolution info in successful responses:

```python
def list_experiments(database_path: Optional[str] = None) -> str:
    """List all experiments in the database."""
    try:
        resolved_path, resolution_info = _resolve_database_path(database_path)

        # ... existing code to get experiments ...

        result = {
            'database_path': resolved_path,
            'path_resolved_via': resolution_info['source'],  # NEW
            'experiment_count': len(exp_list),
            'experiments': [...],
        }
        return json.dumps(result, indent=2)

    except FileNotFoundError as e:
        # Return helpful error with suggestions
        return json.dumps({
            'error': str(e),
            'error_type': 'database_not_found'
        }, indent=2)
```

### Phase 3: Database Discovery Tool ⭐ (HIGH PRIORITY)

**Goal**: Add tool to list all available databases for easy discovery.

**Implementation** in `instrmcp/extensions/database/query_tools.py`:

```python
def list_available_databases() -> str:
    """
    List all available QCodes databases across common locations.

    Searches:
    - MeasureIt databases directory (via measureit.get_path("databases"))
    - QCodes config location

    Returns:
        JSON string with available databases, their locations, and metadata
    """
    try:
        databases = _list_available_databases()

        # Try to get experiment counts for each database
        for db_info in databases:
            try:
                # Temporarily set database location
                original_db_location = qc.config.core.db_location
                qc.config.core.db_location = db_info['path']

                exp_list = experiments()
                db_info['experiment_count'] = len(exp_list)

                # Restore original location
                qc.config.core.db_location = original_db_location

            except Exception as e:
                db_info['experiment_count'] = None
                db_info['accessible'] = False
                db_info['error'] = str(e)

        # Get MeasureIt config info
        measureit_info = {}
        try:
            from measureit import get_data_dir, get_path
            measureit_info = {
                'data_dir': str(get_data_dir()),
                'databases_dir': str(get_path("databases")),
            }
        except ImportError:
            measureit_info['available'] = False

        result = {
            'databases': databases,
            'total_count': len(databases),
            'measureit_config': measureit_info,
            'qcodes_default': str(qc.config.core.db_location),
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({'error': str(e)}, indent=2)
```

**Register in** `instrmcp/servers/jupyter_qcodes/registrars/database_tools.py`:

```python
def _register_list_available_databases(self):
    """Register the database_list_available tool."""

    @self.mcp.tool(name="database_list_available")
    async def list_available_databases() -> List[TextContent]:
        """List all available QCodes databases.

        Searches common locations including MeasureIt databases directory
        and QCodes configuration paths.

        Returns JSON containing available databases with metadata including
        name, path, size, source, and experiment count.
        """
        try:
            result = self.db.list_available_databases()
            return [TextContent(type="text", text=result)]
        except Exception as e:
            logger.error(f"Error in database_list_available: {e}")
            return [
                TextContent(
                    type="text", text=json.dumps({"error": str(e)}, indent=2)
                )
            ]
```

Don't forget to add to `register_all()`:
```python
def register_all(self):
    """Register all database tools."""
    self._register_list_experiments()
    self._register_get_dataset_info()
    self._register_get_database_stats()
    self._register_list_available_databases()  # NEW
```

### Phase 4: Update Tool Descriptions (Documentation)

**Goal**: Improve tool descriptions with clear examples of supported path formats.

**Update** `instrmcp/servers/jupyter_qcodes/registrars/database_tools.py`:

```python
DATABASE_PATH_HELP = """
Database path format (optional):
  - None (default): Auto-detect using MeasureIt or QCodes config
  - Absolute path: "C:\\Users\\...\\mydata.db" or "/Users/.../mydata.db"

Path resolution priority:
  1. Explicit path (if provided)
  2. MeasureIt databases directory (if MeasureIt available)
  3. QCodes config location (fallback)

Discovery:
  - Use database_list_available() to see all accessible databases
  - Check database_config resource for current configuration
"""

# Then update each tool docstring:
@self.mcp.tool(name="database_list_experiments")
async def list_experiments(
    database_path: Optional[str] = None,
) -> List[TextContent]:
    f"""List all experiments in the specified QCodes database.

    Args:
        database_path: {DATABASE_PATH_HELP}

    Returns JSON containing experiment information including ID, name,
    sample name, and format string for each experiment.

    Examples:
        database_list_experiments()  # Use default database
        database_list_experiments("C:\\\\Data\\\\my_experiment.db")  # Absolute path
    """
```

### Phase 5: Update Database Resource

**Goal**: Enhance database_config resource with discovery guidance.

**Update** `instrmcp/extensions/database/db_resources.py`:

```python
def get_database_config_resource() -> dict:
    """Provide database configuration and discovery information."""

    config_info = {
        'qcodes_default_location': str(qc.config.core.db_location),
        'path_resolution_order': [
            '1. Explicit database_path parameter (if provided)',
            '2. MeasureIt databases directory via get_path("databases")',
            '3. QCodes config core.db_location (fallback)'
        ],
        'supported_path_formats': {
            'auto_detect': 'database_path=None',
            'absolute': 'database_path="C:\\\\Users\\\\...\\\\mydata.db"',
        },
        'discovery_tools': {
            'list_available': 'database_list_available() - Find all accessible databases',
            'list_experiments': 'database_list_experiments(db_path) - List experiments in specific DB',
            'get_stats': 'database_get_database_stats(db_path) - Get database metadata'
        },
    }

    # Add MeasureIt config if available
    try:
        from measureit import get_data_dir, get_path
        config_info['measureit_config'] = {
            'data_dir': str(get_data_dir()),
            'databases_dir': str(get_path("databases")),
            'default_database': str(get_path("databases") / "Example_database.db")
        }
    except ImportError:
        config_info['measureit_config'] = {
            'available': False,
            'note': 'Install MeasureIt for additional database discovery'
        }

    return config_info
```

## Testing Plan

### Unit Tests

**File**: `tests/unit/extensions/database/test_query_tools.py`

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from instrmcp.extensions.database.query_tools import (
    _resolve_database_path,
    _list_available_databases,
    list_available_databases
)


class TestDatabasePathResolution:
    """Test database path resolution with 3 supported formats."""

    def test_explicit_path_exists(self, tmp_path):
        """Test explicit path resolution when file exists."""
        db_file = tmp_path / "test.db"
        db_file.touch()

        resolved, info = _resolve_database_path(str(db_file))

        assert resolved == str(db_file)
        assert info['source'] == 'explicit'
        assert info['tried_path'] == str(db_file)

    def test_explicit_path_not_found(self, tmp_path):
        """Test explicit path raises helpful error when file doesn't exist."""
        db_file = tmp_path / "nonexistent.db"

        with pytest.raises(FileNotFoundError) as exc_info:
            _resolve_database_path(str(db_file))

        error_msg = str(exc_info.value)
        assert "Database not found" in error_msg
        assert "Available databases:" in error_msg
        assert "database_list_available()" in error_msg

    @patch('instrmcp.extensions.database.query_tools.get_path')
    def test_measureit_default(self, mock_get_path, tmp_path):
        """Test MeasureIt default database resolution."""
        db_file = tmp_path / "Example_database.db"
        db_file.touch()

        mock_get_path.return_value = tmp_path

        resolved, info = _resolve_database_path(None)

        assert resolved == str(db_file)
        assert info['source'] == 'measureit_default'

    @patch('instrmcp.extensions.database.query_tools.qc')
    def test_qcodes_fallback(self, mock_qc, tmp_path):
        """Test QCodes config fallback when MeasureIt unavailable."""
        db_file = tmp_path / "qcodes.db"
        db_file.touch()

        mock_qc.config.core.db_location = str(db_file)

        with patch('instrmcp.extensions.database.query_tools.get_path', side_effect=ImportError):
            resolved, info = _resolve_database_path(None)

        assert resolved == str(db_file)
        assert info['source'] == 'qcodes_config'

    def test_no_database_found_comprehensive_error(self):
        """Test comprehensive error when no database found."""
        with patch('instrmcp.extensions.database.query_tools.get_path', side_effect=ImportError):
            with patch('instrmcp.extensions.database.query_tools.qc') as mock_qc:
                mock_qc.config.core.db_location = "/nonexistent/qcodes.db"

                with pytest.raises(FileNotFoundError) as exc_info:
                    _resolve_database_path(None)

                error_msg = str(exc_info.value)
                assert "No database found. Tried:" in error_msg
                assert "MeasureIt default:" in error_msg
                assert "QCodes config:" in error_msg
                assert "Available databases:" in error_msg


class TestListAvailableDatabases:
    """Test database discovery functionality."""

    @patch('instrmcp.extensions.database.query_tools.get_path')
    def test_finds_measureit_databases(self, mock_get_path, tmp_path):
        """Test finding databases in MeasureIt directory."""
        # Create test databases
        (tmp_path / "test1.db").write_text("dummy")
        (tmp_path / "test2.db").write_text("dummy")

        mock_get_path.return_value = tmp_path

        databases = _list_available_databases()

        assert len(databases) >= 2
        db_names = [db['name'] for db in databases]
        assert 'test1.db' in db_names
        assert 'test2.db' in db_names

        # Check metadata
        for db in databases:
            assert 'path' in db
            assert 'source' in db
            assert 'size_mb' in db
            assert db['source'] == 'measureit'

    @patch('instrmcp.extensions.database.query_tools.qc')
    def test_includes_qcodes_config_db(self, mock_qc, tmp_path):
        """Test QCodes config database is included."""
        qcodes_db = tmp_path / "qcodes.db"
        qcodes_db.write_text("dummy")

        mock_qc.config.core.db_location = str(qcodes_db)

        with patch('instrmcp.extensions.database.query_tools.get_path', side_effect=ImportError):
            databases = _list_available_databases()

        assert len(databases) >= 1
        assert databases[0]['source'] == 'qcodes_config'
        assert databases[0]['name'] == 'qcodes.db'

    def test_list_available_databases_json(self):
        """Test list_available_databases returns valid JSON."""
        result = list_available_databases()

        import json
        parsed = json.loads(result)

        assert 'databases' in parsed
        assert 'total_count' in parsed
        assert 'measureit_config' in parsed
        assert 'qcodes_default' in parsed


class TestEnhancedErrorMessages:
    """Test error message formatting and helpfulness."""

    def test_error_includes_available_databases(self):
        """Test error message lists available databases."""
        with patch('instrmcp.extensions.database.query_tools._list_available_databases') as mock_list:
            mock_list.return_value = [
                {'name': 'db1.db', 'path': '/path/to/db1.db', 'source': 'measureit', 'size_mb': 1.5},
                {'name': 'db2.db', 'path': '/path/to/db2.db', 'source': 'qcodes_config', 'size_mb': 2.3}
            ]

            with pytest.raises(FileNotFoundError) as exc_info:
                _resolve_database_path("/nonexistent.db")

            error_msg = str(exc_info.value)
            assert 'db1.db' in error_msg
            assert 'db2.db' in error_msg
            assert '1.5 MB' in error_msg
            assert '2.3 MB' in error_msg

    def test_successful_resolution_includes_source(self, tmp_path):
        """Test successful resolution includes source information."""
        db_file = tmp_path / "test.db"
        db_file.touch()

        resolved, info = _resolve_database_path(str(db_file))

        assert info['source'] in ['explicit', 'measureit_default', 'qcodes_config']
        assert 'available_databases' in info
```

### Integration Tests

**File**: `tests/integration/test_database_workflow.py`

```python
def test_discovery_workflow(tmp_path):
    """Test full workflow: discover → select → query."""
    # Setup: Create test databases
    measureit_db = tmp_path / "databases"
    measureit_db.mkdir()
    (measureit_db / "test1.db").touch()
    (measureit_db / "test2.db").touch()

    with patch('measureit.get_path', return_value=measureit_db):
        # Step 1: Discover available databases
        result = list_available_databases()
        databases = json.loads(result)['databases']

        assert len(databases) >= 2

        # Step 2: Select database
        selected_db = databases[0]['path']

        # Step 3: Query database
        # (Would call list_experiments with selected path)
        # This requires actual QCodes database setup
```

## Implementation Order

1. ✅ **Phase 1 - DONE**: Basic path resolution (already implemented)
2. ⭐ **Phase 2 - HIGH PRIORITY**: Enhanced error messages (implement first)
3. ⭐ **Phase 3 - HIGH PRIORITY**: Database discovery tool (implement second)
4. **Phase 4**: Update tool descriptions (documentation polish)
5. **Phase 5**: Update database_config resource (final documentation)

## Benefits

1. **Better Error Messages**: Users get helpful suggestions when database not found
2. **Easy Discovery**: New `database_list_available()` tool helps users find databases
3. **Clear Documentation**: Tool descriptions clearly explain supported formats
4. **Transparent Resolution**: Response includes how path was resolved
5. **Backward Compatible**: Existing code continues to work unchanged

## Files to Modify

- `instrmcp/extensions/database/query_tools.py` - Core implementation (Phases 2 & 3)
- `instrmcp/servers/jupyter_qcodes/registrars/database_tools.py` - Tool registration (Phases 3 & 4)
- `instrmcp/extensions/database/db_resources.py` - Resource enhancement (Phase 5)
- `tests/unit/extensions/database/test_query_tools.py` - Unit tests (all phases)
- `tests/integration/test_database_workflow.py` - Integration tests (Phase 3)
