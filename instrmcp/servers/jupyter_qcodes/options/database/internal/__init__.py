"""
Database internal utilities for code generation and sweep analysis.

This module provides comprehensive code suggestion generation for QCodes datasets,
with automatic grouping of related sweeps (Sweep2D parent runs, SweepQueue batches).
"""

from .code_suggestion import (
    generate_code_suggestion,
    analyze_sweep_groups,
    SweepType,
    SweepGroup,
)

__all__ = [
    "generate_code_suggestion",
    "analyze_sweep_groups",
    "SweepType",
    "SweepGroup",
]
