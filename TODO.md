# TODO

## InstrMCP App / Launcher (v2.4.0)

One-command launcher + supervisor + dashboard around the kernel-hosted MCP server.
See `docs/ARCHITECTURE.md` → "App / Launcher Architecture".

- [x] M1 — CLI (`launch`, `doctor`, `status`, `stop`, `profiles`, `install-kernel`),
  profile config (`app/profiles.py`), auto-loading kernelspec (`app/install_kernel.py`),
  diagnostics (`app/doctor.py`)
- [x] M2 — Supervisor + component state machine + health loop + Starlette status API
  + `WS /events` (`app/supervisor.py`, `app/components.py`, `app/api.py`, `app/logs.py`);
  CLI `restart` / `logs` and API-backed `status` / `stop`
- [x] M3 — Supervisor-served static dashboard (`app/webapp/`), resilient to JupyterLab
  being down
- [x] M4 — MeasureIt status via HTTP poll of `measureit_get_status` (`app/mcp_client.py`),
  rendered in the dashboard (no kernel comm, no new MCP tool)
- [x] M5 — Demo profile (`app/defaults/demo.yaml`), docs (README + ARCHITECTURE),
  packaging (webapp assets in package-data), version bump to 2.4.0
- [x] Streamlit GUI control panel (`app/streamlit_app.py`, `instrmcp app`,
  `instrmcp[gui]` extra) — friendly front door over the supervisor; launch/status/
  logs/MeasureIt/doctor/recovery. MCP itself started from the notebook toolbar.
- [x] MeasureIt status fix: `mcp_client.get_measureit_status` now requests
  `detailed=True` so the dashboard gets the per-sweep `sweeps` dict (the concise
  default only returned names/count, so the panel found no sweeps)
- [x] Demote the kernelspec auto-launcher to "advanced/optional"; missing kernelspec is
  now a doctor **warning**, not a failure (the toolbar flow needs no kernelspec)
- [x] Kernelspec startup hardened: deferred onto the kernel event loop so it no longer
  blocks kernel readiness (was causing JupyterLab to restart the kernel) and is wrapped
  defensively so failures don't crash the kernel
- [x] Embedded MCP Inspector (Node-free): `app/inspector.py` + GUI **Inspector** tab over
  the kernel-hosted server. `app/mcp_client.py` gained a shared `_request` helper plus
  `list_tools`/`list_resources`/`list_prompts`/`read_resource`/`get_prompt`; the Streamlit
  app browses + calls tools/resources/prompts. Reuses the existing `:8123/mcp` streamable-
  HTTP handshake — no `npx`/Node, no new MCP tool, no extra port. Verified end-to-end
  against a live FastMCP server (`tests/unit/test_inspector.py`, `test_mcp_client.py`)

## Notebook-bridge "stale state" e2e coverage (#29 / PRs #30, #32, #33)

Durable e2e tests for the bridge fix, folding the throwaway `/tmp/bridge_repro/`
harnesses into the suite. Validated on an integration build (main + #32 + #33).

- [x] `tests/e2e/test_13_bridge_resilience.py` — BR-010/011/012 cover
  `notebook_execute_code` (registered + runs on the real kernel, shares the kernel
  namespace + advances exec count, and **survives frontend death** while `add_cell`
  fails — the deterministic recovery path). All 4 pass on the integration build.
- [x] Registration for `notebook_execute_code`: `metadata_baseline.yaml`,
  `docs/ARCHITECTURE.md`, `README.md`, regenerated `metadata_snapshot.json`
  (25→26 tools). STDIO-proxy path verified (HTTP==Proxy==26 tools).
  No `stdio_proxy.py` change needed — `FastMCP.as_proxy` mirrors tools transparently.
- [x] #33 regression check: `test_03_unsafe_mode_tools.py -m p0` (14) + the new BR-001
  burst all green — the comm-handler rewrite didn't regress add/execute/delete/patch.
- [!] **The listener-leak wedge is NOT deterministically reproducible** in the e2e
  harness: the original `repro.py` (qdevBot task notebook) runs 30/30 clean even
  against the *unpatched, leak-present* frontend on current hardware; neither the
  dangerous nor MeasureIt/qt fixture wedges at 80 cycles. It's a timing race. So
  BR-001 is an honest burst/responsiveness smoke test, not a leak guard, and the
  leak fix (#30, `stopTrackingActiveCell` in `src/index.ts`) is guarded by code
  review, not e2e. Follow-up: a jest unit test asserting the listener disconnects.
- [ ] Port the registration edits + `test_13` onto PRs #32/#33 before merge (they
  currently live on the throwaway `test/bridge-integration` branch).

### Follow-ups (post-MVP)
- [ ] Per-kernel MCP port allocation (today `:8123` is a singleton; two `instrmcp`
  kernels collide — `doctor` warns)
- [ ] Optional `jupyter_client` proxy so CLI/GUI `restart-mcp` can actually restart
  the kernel-hosted server (currently advisory)
- [ ] Optional JupyterLab side panel mirroring the dashboard in-notebook
- [ ] `--detach` daemon mode (M1–M2 are foreground only)
