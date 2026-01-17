"""
Backend package for QCoDeS and Jupyter notebook operations.

This package contains domain-specific backends that implement the actual
business logic, while the facade (QCodesReadOnlyTools) provides a unified
interface for registrars.

Structure:
- base.py: SharedState dataclass and BaseBackend ABC
- qcodes.py: QCodesBackend (instruments, parameters, caching)
- notebook.py: NotebookBackend (variables, cell reading, cursor)
- notebook_unsafe.py: NotebookUnsafeBackend (cell modification, execution)

MeasureIt backend is in options/measureit/backend.py (opt-in feature).
"""

from .base import SharedState, BaseBackend
from .qcodes import QCodesBackend
from .notebook import NotebookBackend
from .notebook_unsafe import NotebookUnsafeBackend

__all__ = [
    "SharedState",
    "BaseBackend",
    "QCodesBackend",
    "NotebookBackend",
    "NotebookUnsafeBackend",
]
