# Playwright MCP Metadata E2E

End-to-end workflow that launches JupyterLab, runs a notebook in dangerous MCP
mode via Playwright, then snapshots or verifies tool/resource metadata from the
local MCP server on `http://127.0.0.1:8123`.

## Setup

1. Activate the test environment:
   `source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev`
2. Install dev deps:
   `pip install -e .[dev]`
3. Install Playwright and browsers:
   `pip install playwright` and `python -m playwright install`

## Directory Structure

```
tests/playwright/
├── notebooks/
│   ├── original/           # Source notebooks (immutable)
│   │   └── metadata_e2e.ipynb
│   └── _working/           # Working copies (auto-created, gitignored)
├── run_metadata_e2e.py     # Main E2E test runner
├── test_stdio_proxy_metadata.py  # Proxy metadata alignment test
├── mcp_metadata_client.py  # MCP client utilities
├── metadata_snapshot.json  # Baseline snapshot
└── README.md
```

## Step 0: Create a baseline snapshot

This writes `tests/playwright/metadata_snapshot.json` with tool/resource
descriptions captured from the running MCP server.

```
python tests/playwright/run_metadata_e2e.py --mode snapshot
```

## Step 1: Run the E2E check

Runs the notebook with Playwright, waits for the MCP server, and compares the
server metadata to the snapshot.

```
python tests/playwright/run_metadata_e2e.py --mode verify
```

### Recommended options

```bash
# Clean start - kill any existing processes on ports 8888/8123
python tests/playwright/run_metadata_e2e.py --mode verify --clean

# With longer cell wait time for slower systems
python tests/playwright/run_metadata_e2e.py --mode verify --clean --cell-wait-ms 2000

# Keep JupyterLab running after test (for debugging or proxy tests)
python tests/playwright/run_metadata_e2e.py --mode verify --clean --keep-jupyter
```

## Step 2: Verify stdio_proxy metadata alignment

After starting the MCP server (with `--keep-jupyter`), verify that the
FastMCP proxy mirrors metadata correctly:

```bash
# First start MCP server
python tests/playwright/run_metadata_e2e.py --mode verify --clean --keep-jupyter

# Then run proxy test
python tests/playwright/test_stdio_proxy_metadata.py

# Or compare against snapshot
python tests/playwright/test_stdio_proxy_metadata.py --compare-snapshot
```

This verifies that Claude Desktop/Code (which uses the stdio proxy) sees the
same tool/resource metadata as direct HTTP clients.

## How it works

- **Original notebook**: `tests/playwright/notebooks/original/metadata_e2e.ipynb`
- **Working copy**: Copied to `notebooks/_working/` during test (auto-cleaned)
- JupyterLab runs headless on `127.0.0.1:8888` with token `instrmcp-playwright`
- MCP server starts inside the notebook (`%mcp_dangerous` + `%mcp_start`)
- Metadata extraction uses `tools/list` and `resources/list`
- Logs are captured in `tests/playwright/jupyter_lab.log` (gitignored)

## Command-line options

| Option | Description |
|--------|-------------|
| `--mode {snapshot,verify}` | Create snapshot or verify against existing |
| `--clean` | Kill processes on ports 8888/8123 before starting |
| `--keep-jupyter` | Leave JupyterLab running after test |
| `--skip-jupyter` | Assume JupyterLab is already running |
| `--skip-playwright` | Skip notebook execution (MCP server already up) |
| `--cell-wait-ms N` | Wait N ms between cell executions (default: 500) |
| `--jupyter-port N` | Use custom Jupyter port (default: 8888) |
| `--mcp-port N` | MCP server port for cleanup (default: 8123) |
| `--snapshot PATH` | Path to snapshot file |

## Adding extra cells for future E2E flows

You can extend the notebook directly, or pass extra cells via JSON:

```
python tests/playwright/run_metadata_e2e.py --mode verify \
  --extra-cells tests/playwright/extra_cells.json
```

Example `extra_cells.json`:

```json
[
  "print('extra cell')",
  "1 + 1"
]
```

## Cleanup

The test automatically cleans up:
- Working notebook copy in `notebooks/_working/`
- JupyterLab process (unless `--keep-jupyter`)
- MCP server process on port 8123

Manual cleanup if needed:
```bash
pkill -f jupyter; lsof -ti:8123 | xargs kill -9; lsof -ti:8888 | xargs kill -9
```
