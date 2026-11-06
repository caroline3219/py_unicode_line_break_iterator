"""Unicode Line Break Iterator.

Segments text into lines at valid UAX #14 line break opportunities.
"""

from .core import (
    LineBreakIterator,
    LineBreakClass,
    classify,
    line_break_opportunities,
    split_lines,
)

__all__ = [
    "LineBreakIterator",
    "LineBreakClass",
    "classify",
    "line_break_opportunities",
    "split_lines",
]

__version__ = "1.0.0"
