# Plan: JupyterLab Toolbar Configuration UI for MCP Server

## Overview

Add a comprehensive toolbar-based configuration UI to replace magic commands (`%mcp_start`, `%mcp_unsafe`, etc.) with visual controls directly in the notebook toolbar.

**Location:** Extend existing extension at `instrmcp/extensions/jupyterlab/` (NOT a separate extension)

## Architecture

```
Existing Plugin (mcp-active-cell-bridge:plugin)
    └── MCPToolbarExtension (DocumentRegistry.IWidgetExtension) [NEW]
            └── MCPToolbarWidget (ReactWidget)
                    └── MCPToolbarComponent (React)
                            ├── ServerControlButton (Start/Stop toggle)
                            ├── ModeSelector (Safe/Unsafe/Dangerous dropdown)
                            ├── OptionsPanel (Dynamic options from backend)
                            └── StatusIndicator (Running state display)
```

**Communication Flow:**
```
Toolbar UI ──► mcp:toolbar_control comm ──► Backend calls existing magic functions
                                                       │
Toolbar UI ◄── mcp:server_status comm (shared with Active Cell Bridge) ◄──┘
```

**Key Integration Points:**
- Toolbar extension registered in same plugin as Active Cell Bridge
- Shares existing WeakMaps: `comms`, `mcpServerReady`, `openedComms`, etc.
- Listens to existing `mcp:server_status` comm (no duplicate registration)
- Backend handler calls magic class methods directly (no logic duplication)

## Implementation Tasks

### Phase 1: Backend Communication
**File: `instrmcp/servers/jupyter_qcodes/jupyter_mcp_extension.py`**

- [ ] Extract magic logic into reusable async helpers:
  - `_do_start_server()` - extracted from `mcp_start` magic
  - `_do_stop_server()` - extracted from `mcp_close` magic
  - `_do_restart_server()` - extracted from `mcp_restart` magic
  - `_do_set_mode(mode)` - set `_desired_mode` and `_dangerous_mode` correctly
  - `_do_set_option(option, enabled)` - update `_enabled_options`
- [ ] **Each helper must call `broadcast_server_status()` after state mutation** - even before restart, so all notebooks/toolbars see the change:
  ```python
  def _do_set_mode(mode: str):
      global _desired_mode, _dangerous_mode
      if mode == "safe":
          _desired_mode = True
          _dangerous_mode = False
      elif mode == "unsafe":
          _desired_mode = False
          _dangerous_mode = False
      elif mode == "dangerous":
          _desired_mode = False
          _dangerous_mode = True
      # Broadcast immediately so all toolbars update
      broadcast_server_status("config_changed", _get_current_config())
  ```
- [ ] Add `mcp:toolbar_control` comm target in `load_ipython_extension()`
- [ ] Implement comm handler that calls extracted helpers (NOT reimplementing logic)
- [ ] Enhance `broadcast_server_status()` to include:
  - `enabled_options`: list of currently enabled options
  - `available_options`: list of all valid options with metadata (name, description)
  - `dangerous`: boolean flag for dangerous mode
- [ ] **Single source of truth for options** - Refactor existing `valid_options` (line 251) to include descriptions:
  ```python
  # Module-level constant - used by both magics and toolbar
  VALID_OPTIONS = {
      "measureit": "Enable MeasureIt sweep tools",
      "database": "Enable database tools",
      "auto_correct_json": "Auto-correct malformed JSON",
  }
  ```
- [ ] Update `mcp_option` magic to use `VALID_OPTIONS.keys()` instead of local `valid_options`
- [ ] Add helper `_get_current_config()` that uses `VALID_OPTIONS`:
  ```python
  def _get_current_config() -> dict:
      return {
          "mode": "dangerous" if _dangerous_mode else ("safe" if _desired_mode else "unsafe"),
          "enabled_options": list(_enabled_options),
          "available_options": [
              {"name": k, "description": v} for k, v in VALID_OPTIONS.items()
          ],
          "dangerous": _dangerous_mode,
          "server_running": _server is not None,
          "host": _server.host if _server else None,
          "port": _server.port if _server else None,
      }
  ```
- [ ] Add `get_status` message handler for initial toolbar state:
  ```python
  # In _handle_toolbar_control on_msg:
  if msg_type == "get_status":
      # Return current state immediately - for newly opened toolbars
      comm.send({"type": "status", **_get_current_config()})
  ```

### Phase 2: Package & Build Configuration
**File: `instrmcp/extensions/jupyterlab/package.json`**

- [ ] Add dependencies for React/Lumino integration:
  ```json
  "dependencies": {
    "@lumino/signaling": "^2.1.0",
    "@jupyterlab/ui-components": "^4.2.0",
    ... existing deps ...
  },
  "peerDependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.0.0",
    "@types/react-dom": "^18.0.0",
    ... existing deps ...
  }
  ```
  Note: `react`/`react-dom` as peerDependencies ensures tsc compiles JSX and Jupyter's builder dedupes versions

**File: `instrmcp/extensions/jupyterlab/tsconfig.json`**
- [ ] Add `"jsx": "react"` to compilerOptions
- [ ] Change `"include": ["src/*"]` to `"include": ["src/**/*"]` to include subdirectories

### Phase 3: Extend Existing Frontend Plugin
**File: `instrmcp/extensions/jupyterlab/src/index.ts`**

- [ ] Add shared `Signal` for status updates at module level:
  ```typescript
  import { Signal, ISignal } from '@lumino/signaling';

  // Shared signal that toolbar widgets subscribe to
  const statusUpdateSignal = new Signal<object, MCPStatusUpdate>({});
  ```
- [ ] Modify existing `mcp:server_status` comm handler to emit signal:
  ```typescript
  // In the existing onMsg handler (around line 1160)
  if (status === 'server_ready' || status === 'server_stopped' || status === 'config_changed') {
    statusUpdateSignal.emit({ kernel, status, details: data.details });
  }
  ```
- [ ] Import toolbar module at top of file
- [ ] Register `MCPToolbarExtension` with `app.docRegistry` in existing `activate()` function
- [ ] Pass shared state to toolbar: `{ mcpServerReady, statusUpdateSignal, getComm }`
- [ ] Ensure toolbar widget cleanup on kernel switch/close (integrate with existing cleanup logic)

### Phase 4: Frontend Widget Infrastructure
**New Files in `instrmcp/extensions/jupyterlab/src/toolbar/`**

- [ ] Create `types.ts` - TypeScript interfaces:
  ```typescript
  interface MCPState {
    serverRunning: boolean;
    mode: 'safe' | 'unsafe' | 'dangerous';
    enabledOptions: string[];
    availableOptions: Array<{name: string, description: string}>;
    host: string;
    port: number;
  }
  ```
- [ ] Create `MCPToolbarWidget.ts` - Lumino ReactWidget that:
  - Receives shared WeakMaps from main plugin (NOT creating duplicates)
  - Subscribes to existing `mcp:server_status` updates via callback
  - Creates `mcp:toolbar_control` comm for sending commands
  - Uses `UseSignal` for React state updates
- [ ] Create `MCPToolbarExtension.ts` - DocumentRegistry.IWidgetExtension:
  - Creates MCPToolbarWidget per NotebookPanel
  - Passes kernel connection and shared state references
  - Handles disposal when notebook closes

### Phase 5: React Components
**New Files in `instrmcp/extensions/jupyterlab/src/toolbar/`**

- [ ] Create `icons.tsx` - SVG icon components (Play, Stop, Shield, Warning, Skull, Gear, Chevron)
- [ ] Create `ServerControlButton.tsx` - Start/Stop toggle button
- [ ] Create `ModeSelector.tsx` - Mode dropdown with restart confirmation dialog
- [ ] Create `OptionsPanel.tsx` - **Dynamic** options panel:
  - Renders checkboxes from `availableOptions` array (NOT hard-coded)
  - Shows current state from `enabledOptions` array
  - Shows restart confirmation dialog on change
- [ ] Create `StatusIndicator.tsx` - Running state display
- [ ] Create `MCPToolbarComponent.tsx` - Main container component
- [ ] Create `index.ts` - Barrel export

### Phase 6: Styling
**File: `instrmcp/extensions/jupyterlab/style/index.css`**

- [ ] Add toolbar container layout (flexbox)
- [ ] Add button states (hover, active, disabled, running/stopped)
- [ ] Add dropdown positioning and animations
- [ ] Add mode-specific colors (safe=green, unsafe=orange, dangerous=red)
- [ ] Add status indicator with pulse animation
- [ ] Ensure dark theme compatibility using `--jp-*` CSS variables

### Phase 7: Build & Test
- [ ] Rebuild extension: `cd instrmcp/extensions/jupyterlab && jlpm run build`
- [ ] Reinstall: `pip install -e . --force-reinstall --no-deps`
- [ ] Test in JupyterLab

### Phase 8: Testing & Documentation
- [ ] Test Start/Stop/Restart via buttons
- [ ] Test mode switching with restart confirmation dialog
- [ ] Test ALL option toggles (MeasureIt, Database, auto_correct_json, future options)
- [ ] Test multi-notebook state sync (shared kernel state)
- [ ] Test kernel restart recovery
- [ ] Test notebook switch (toolbar state follows active notebook's kernel)
- [ ] Update README.md with toolbar UI docs
- [ ] Update CLAUDE.md with toolbar info

## Files Summary

### Files to Modify

| File | Changes |
|------|---------|
| `jupyter_mcp_extension.py` | Extract magic helpers, add `mcp:toolbar_control` comm, broadcast on config changes |
| `package.json` | Add deps, peerDeps (`react`, `react-dom`), devDeps (`@types/react`, `@types/react-dom`) |
| `tsconfig.json` | Add `"jsx": "react"`, change include to `"src/**/*"` |
| `src/index.ts` | Add shared Signal, modify comm handler, register toolbar extension |
| `style/index.css` | Add ~150 lines toolbar styling |

### New Files (in existing extension)

| File | Purpose |
|------|---------|
| `src/toolbar/types.ts` | TypeScript interfaces |
| `src/toolbar/MCPToolbarExtension.ts` | Document registry extension |
| `src/toolbar/MCPToolbarWidget.ts` | Lumino ReactWidget wrapper |
| `src/toolbar/MCPToolbarComponent.tsx` | Main React container |
| `src/toolbar/ServerControlButton.tsx` | Start/Stop button |
| `src/toolbar/ModeSelector.tsx` | Mode dropdown |
| `src/toolbar/OptionsPanel.tsx` | Dynamic options checkboxes |
| `src/toolbar/StatusIndicator.tsx` | Status display |
| `src/toolbar/icons.tsx` | SVG icons |
| `src/toolbar/index.ts` | Barrel export |

## Key Design Decisions

1. **Extend existing extension** - No duplicate packaging, build scripts, or installation complexity
2. **Share kernel state** - Toolbar uses same WeakMaps and comm handling as Active Cell Bridge
3. **Reuse magic logic** - Backend comm handler calls extracted helpers from magic class, not reimplementing
4. **Dynamic options** - `availableOptions` array from backend, UI auto-adapts to new options
5. **React + Lumino integration** - Use `ReactWidget` and `UseSignal` for reactive state
6. **Ask confirmation for restart** - Show dialog "Restart now?" after mode/option changes
7. **Keep magic commands** - Toolbar is an alternative UI, magic commands remain functional

## Backend Logic Extraction Pattern

```python
# In jupyter_mcp_extension.py

# Extract from mcp_start magic into reusable helper
async def _do_start_server():
    """Start MCP server - extracted logic from mcp_start magic."""
    global _server, _server_task, _desired_mode, _dangerous_mode
    # ... existing start logic from mcp_start ...

# Comm handler calls helpers, doesn't reimplement
def _handle_toolbar_control(comm, open_msg):
    def on_msg(msg):
        data = msg.get("content", {}).get("data", {})
        msg_type = data.get("type")

        if msg_type == "start_server":
            # Call existing logic, don't reimplement!
            asyncio.ensure_future(_do_start_server())
        elif msg_type == "set_mode":
            mode = data.get("mode")
            _do_set_mode(mode)  # Handles _dangerous_mode and _desired_mode correctly
            comm.send({"type": "result", "success": True, "restart_required": True})
        # ...
```

## Frontend State Sharing Pattern

```typescript
// At module level in index.ts (not inside activate)
import { Signal, ISignal } from '@lumino/signaling';

interface MCPStatusUpdate {
  kernel: Kernel.IKernelConnection;
  status: string;
  details: any;
}

// Shared signal - all toolbar widgets subscribe to this
const statusUpdateSignal = new Signal<object, MCPStatusUpdate>({});

// In existing mcp:server_status comm handler (around line 1160)
const onMsg = (msg: any) => {
  const data = msg?.content?.data || {};
  const status = data.status;

  // ... existing handling ...

  // NEW: Emit signal so toolbar widgets update
  if (status === 'server_ready' || status === 'server_stopped' || status === 'config_changed') {
    statusUpdateSignal.emit({ kernel, status, details: data.details });
  }
};

// In activate() function
const toolbarExtension = new MCPToolbarExtension({
  getServerReady: (kernel) => mcpServerReady.get(kernel) ?? false,
  getComm: (kernel) => comms.get(kernel),
  statusUpdateSignal,  // Pass signal reference
});

app.docRegistry.addWidgetExtension('Notebook', toolbarExtension);
```

```typescript
// In MCPToolbarWidget.ts - subscribe to signal AND request initial state
constructor(panel: NotebookPanel, sharedState: SharedState) {
  super();
  this._panel = panel;
  this._sharedState = sharedState;

  // Subscribe to status updates from the shared signal
  sharedState.statusUpdateSignal.connect(this._onStatusUpdate, this);

  // Request initial state when kernel is ready
  panel.sessionContext.ready.then(() => this._requestInitialState());
}

private async _requestInitialState(): Promise<void> {
  const kernel = this._panel.sessionContext.session?.kernel;
  if (!kernel) return;

  // Create control comm and request current status
  this._controlComm = kernel.createComm('mcp:toolbar_control');
  await this._controlComm.open();

  // Handle response
  this._controlComm.onMsg = (msg: any) => {
    const data = msg?.content?.data || {};
    if (data.type === 'status') {
      this._updateState('current_status', data);
    }
  };

  // Request current state - handles case where server already started
  this._controlComm.send({ type: 'get_status' });
}

private _onStatusUpdate(sender: object, update: MCPStatusUpdate): void {
  // Only update if this is our kernel
  if (update.kernel === this._panel.sessionContext.session?.kernel) {
    this._updateState(update.status, update.details);
  }
}

dispose(): void {
  // Unsubscribe on dispose to prevent memory leaks
  this._sharedState.statusUpdateSignal.disconnect(this._onStatusUpdate, this);
  if (this._controlComm && !this._controlComm.isDisposed) {
    this._controlComm.close();
  }
  super.dispose();
}
```

## Dynamic Options Pattern

```typescript
// OptionsPanel.tsx - renders from availableOptions, not hard-coded

const OptionsPanel: React.FC<{
  availableOptions: Array<{name: string, description: string}>;
  enabledOptions: string[];
  onToggle: (option: string, enabled: boolean) => void;
}> = ({ availableOptions, enabledOptions, onToggle }) => {
  return (
    <div className="mcp-options-dropdown">
      {availableOptions.map(opt => (
        <label key={opt.name} className="mcp-option-item" title={opt.description}>
          <input
            type="checkbox"
            checked={enabledOptions.includes(opt.name)}
            onChange={(e) => onToggle(opt.name, e.target.checked)}
          />
          {opt.name}
        </label>
      ))}
    </div>
  );
};
```

## UI Component Behavior

### ServerControlButton
- Shows Play icon when stopped (gray/red background)
- Shows Stop icon when running (green background)
- Click toggles server state

### ModeSelector
- Dropdown with 3 modes: Safe (green), Unsafe (orange), Dangerous (red)
- Disabled when server not running
- Shows "Restart now?" confirmation dialog after change

### OptionsPanel
- Gear icon button opens dropdown
- **Dynamically renders** all options from `availableOptions`
- Shows "Restart now?" confirmation dialog after change

### StatusIndicator
- Green pulsing dot when running + port number
- Gray/red dot when stopped
- Tooltip shows full status details

## Testing Plan

1. Manual tests:
   - Start/Stop/Restart via buttons
   - Mode switching and restart
   - Option toggles (all options, including future ones)
   - Multi-notebook state sync
   - Notebook/kernel switching

2. Edge cases:
   - Kernel restart recovery
   - Rapid button clicks (debouncing)
   - New options added to backend auto-appear in UI
