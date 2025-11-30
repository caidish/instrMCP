# Agent Guidance

This repository uses the conventions documented in `CLAUDE.md`. All agents (Claude, Codex, etc.) should follow that guidance when working here.

## Key Expectations
- Use conda env `instrMCPdev` for testing (`source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev`).
- Preferred commands: `pip install -e .[dev]`, `python -m build`, `instrmcp version`.
- Quality gates: `black --check instrmcp/ tests/`, `flake8 instrmcp/ tests/ --select=E9,F63,F7,F82`, optional `flake8 --max-line-length=127`, `mypy instrmcp/ --ignore-missing-imports`.
- Tests: `pytest` (or targeted variants listed in `CLAUDE.md`).
- JupyterLab extension changes: `cd instrmcp/extensions/jupyterlab && jlpm run build` then `pip install -e . --force-reinstall --no-deps` and restart JupyterLab.
- Server commands: `instrmcp jupyter --port 3000 [--unsafe]`, `instrmcp qcodes --port 3001`, `instrmcp config`.

For architecture, magic commands, and tool update checklist, refer to `CLAUDE.md` in the repo root.***
