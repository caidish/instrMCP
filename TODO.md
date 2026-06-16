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

### Follow-ups (post-MVP)
- [ ] Per-kernel MCP port allocation (today `:8123` is a singleton; two `instrmcp`
  kernels collide — `doctor` warns)
- [ ] Optional `jupyter_client` proxy so CLI/GUI `restart-mcp` can actually restart
  the kernel-hosted server (currently advisory)
- [ ] Optional JupyterLab side panel mirroring the dashboard in-notebook
- [ ] `--detach` daemon mode (M1–M2 are foreground only)
