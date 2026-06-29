"""
Base classes for backend implementations.

Provides SharedState dataclass for shared resources and BaseBackend
abstract base class that all backends inherit from.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..cache import ReadCache, RateLimiter, ParameterPoller


@dataclass
class SharedState:
    """Shared state passed to all backends.

    Contains all shared resources that multiple backends need access to,
    including the IPython instance, cache, rate limiter, and cell capture state.
    """

    ipython: Any
    namespace: dict
    cache: "ReadCache"
    rate_limiter: "RateLimiter"
    poller: "ParameterPoller"
    min_interval_s: float = 0.2

    # Current cell capture state (modified by pre_run_cell callback)
    current_cell_content: Optional[str] = field(default=None)
    current_cell_id: Optional[str] = field(default=None)
    current_cell_timestamp: Optional[float] = field(default=None)

    # Kernel busy/idle tracking (written by pre/post_run_cell callbacks on the
    # kernel main thread, read by the MCP server background thread). All access
    # is guarded by kernel_state_lock. This is comm-free, so reads stay correct
    # and instant even while the kernel main thread is blocked in a stalled cell.
    kernel_busy: bool = field(default=False)
    kernel_busy_since_mono: Optional[float] = field(default=None)  # time.monotonic()
    kernel_busy_since_wall: Optional[float] = field(
        default=None
    )  # time.time(), display
    kernel_exec_count_at_start: Optional[int] = field(default=None)
    kernel_running_cell_preview: Optional[str] = field(default=None)
    kernel_last_idle_at: Optional[float] = field(default=None)  # time.time()
    kernel_state_lock: Any = field(default_factory=threading.Lock)


class BaseBackend:
    """Abstract base class for all backends.

    Provides common property accessors for shared state resources.
    """

    def __init__(self, state: SharedState):
        """Initialize backend with shared state.

        Args:
            state: SharedState instance containing shared resources
        """
        self.state = state

    @property
    def ipython(self):
        """Access the IPython instance."""
        return self.state.ipython

    @property
    def namespace(self):
        """Access the notebook namespace (user_ns)."""
        return self.state.namespace

    @property
    def cache(self):
        """Access the parameter cache."""
        return self.state.cache

    @property
    def rate_limiter(self):
        """Access the rate limiter."""
        return self.state.rate_limiter

    @property
    def poller(self):
        """Access the parameter poller."""
        return self.state.poller

    @property
    def min_interval_s(self):
        """Access the minimum interval setting."""
        return self.state.min_interval_s
