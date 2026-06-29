"""Runtime component model for the supervisor.

The supervisor tracks a handful of components. Some it *spawns* (JupyterLab); some it
only *observes* (the kernel-hosted MCP server, the kernel itself). Each carries a small
state machine used to compute an aggregate readiness for the dashboard.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class ComponentState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"
    STOPPED = "stopped"


class Component:
    """A single tracked runtime component."""

    def __init__(self, name: str, observed: bool = False) -> None:
        self.name = name
        #: True for components the supervisor only observes (never starts/stops).
        self.observed = observed
        self.state: ComponentState = ComponentState.IDLE
        self.detail: str = ""
        self.pid: Optional[int] = None
        self.error: Optional[str] = None
        #: Consecutive failed health polls (drives READY -> DEGRADED).
        self.fail_count: int = 0

    def set(
        self,
        state: ComponentState,
        detail: str = "",
        *,
        pid: Optional[int] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update the component; return True if the state changed."""
        changed = state != self.state
        self.state = state
        if detail:
            self.detail = detail
        if pid is not None:
            self.pid = pid
        self.error = error
        return changed

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "observed": self.observed,
            "state": self.state.value,
            "detail": self.detail,
            "pid": self.pid,
            "error": self.error,
        }


def aggregate_state(components: dict[str, Component]) -> ComponentState:
    """Compute an overall state from the individual components.

    - ERROR if any non-observed component errored (a spawned process died).
    - STOPPED only if everything is stopped/idle.
    - READY if every relevant component is READY.
    - DEGRADED / STARTING otherwise.
    """
    states = [c.state for c in components.values()]
    if not states:
        return ComponentState.IDLE

    if any(
        c.state == ComponentState.ERROR and not c.observed for c in components.values()
    ):
        return ComponentState.ERROR

    if all(s in (ComponentState.STOPPED, ComponentState.IDLE) for s in states):
        return ComponentState.STOPPED

    if any(s == ComponentState.DEGRADED for s in states):
        return ComponentState.DEGRADED

    if any(s == ComponentState.STARTING for s in states):
        return ComponentState.STARTING

    if all(
        s in (ComponentState.READY, ComponentState.STOPPED, ComponentState.IDLE)
        for s in states
    ):
        return ComponentState.READY

    return ComponentState.DEGRADED
