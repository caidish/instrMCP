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

## Step 0: Create a baseline snapshot

This writes `tests/playwright/metadata_snapshot.json` with tool/resource
descriptions captured from the running MCP server.

```
python tests/playwright/run_metadata_e2e.py --mode snapshot
```

## Step 1 + 2: Run the E2E check

Runs the notebook with Playwright, waits for the MCP server, and compares the
server metadata to the snapshot.

```
python tests/playwright/run_metadata_e2e.py --mode verify
```

## How it works

- Notebook under test: `tests/playwright/notebooks/metadata_e2e.ipynb`
- JupyterLab runs headless on `127.0.0.1:8888` with token `instrmcp-playwright`
- MCP server starts inside the notebook (`%mcp_dangerous` + `%mcp_start`)
- Metadata extraction uses `tools/list` and `resources/list`
- Logs are captured in `tests/playwright/jupyter_lab.log`

## Reusing an existing JupyterLab session

If you already have JupyterLab running, skip the server startup:

```
python tests/playwright/run_metadata_e2e.py --mode verify --skip-jupyter
```

If the notebook is already running and the MCP server is up, you can also skip
Playwright:

```
python tests/playwright/run_metadata_e2e.py --mode verify --skip-playwright
```

## Adding extra cells for future E2E flows (Step 3)

You can extend the notebook directly, or pass extra cells via JSON:

```
python tests/playwright/run_metadata_e2e.py --mode verify \
  --extra-cells tests/playwright/extra_cells.json
```

Example `extra_cells.json`:

```
[
  "print('extra cell')",
  "1 + 1"
]
```
