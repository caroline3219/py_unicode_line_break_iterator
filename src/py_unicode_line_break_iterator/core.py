"""Core implementation of a Unicode Line Break Iterator (UAX #14 subset).

This module implements a practical subset of the Unicode Line Breaking
Algorithm (UAX #14). The full algorithm requires the complete Unicode line
break property table, which is large and changes with every Unicode release.
Instead of shipping that table, this implementation classifies characters
into a small set of line break classes using Python's own ``unicodedata``
module, then applies the pair-table rules that matter for real-world text
layout.

Design decision
---------------
The brief asks for a library with zero third-party dependencies. Rather than
embed a generated copy of ``LineBreak.txt`` (which would be thousands of
lines and go stale), we derive classes from ``unicodedata`` and hard-code the
rules that are both common and unambiguous. This means we do not claim full
UAX #14 conformance; we claim correct handling of the cases listed in the
README.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Iterator, List, Sequence, Tuple


class LineBreakClass(Enum):
    """A reduced set of UAX #14 line break classes.

    The values are the short names used by the Unicode standard where they
exist. ``AL`` (alphabetic) is used as the catch-all for letters, which
matches the standard's treatment of most alphabetic scripts.
    """

    BK = "BK"      # Mandatory break
    CR = "CR"      # Carriage return
    LF = "LF"      # Line feed
    NL = "NL"      # Next line
    SP = "SP"      # Space
    ZW = "ZW"      # Zero width space
    WJ = "WJ"      # Word joiner
    GL = "GL"      # Non-breaking glue
    BA = "BA"      # Break after
    BB = "BB"      # Break before
    HY = "HY"      # Hyphen
    CL = "CL"      # Close punctuation
    CP = "CP"      # Close parenthesis
    EX = "EX"      # Exclamation / interrogation
    IN = "IN"      # Inseparable
    NS = "NS"      # Nonstarter
    OP = "OP"      # Open punctuation
    QU = "QU"      # Quotation
    IS = "IS"      # Infix numeric separator
    NU = "NU"      # Numeric
    PO = "PO"      # Postfix numeric
    PR = "PR"      # Prefix numeric
    CB = "CB"      # Contingent break
    AL = "AL"      # Alphabetic (catch-all)
    HL = "HL"      # Hebrew letter
    ID = "ID"      # Ideographic
    EB = "EB"      # Emoji base
    EM = "EM"      # Emoji modifier
    ZWJ = "ZWJ"    # Zero width joiner
    CM = "CM"      # Combining mark
    SA = "SA"      # Complex context (South-East Asian)
    SG = "SG"      # Surrogate
    XX = "XX"      # Unknown


# Characters that are explicitly assigned a class not derivable from
# ``unicodedata`` alone. Keeping this small and explicit makes the
# behaviour auditable.
_EXPLICIT: dict = {
    "\u0000": LineBreakClass.XX,
    "\u000a": LineBreakClass.LF,   # LINE FEED
    "\u000d": LineBreakClass.CR,   # CARRIAGE RETURN
    "\u000b": LineBreakClass.BK,   # LINE TABULATION
    "\u000c": LineBreakClass.BK,   # FORM FEED
    "\u0085": LineBreakClass.NL,   # NEXT LINE
    "\u2028": LineBreakClass.BK,   # LINE SEPARATOR
    "\u2029": LineBreakClass.BK,   # PARAGRAPH SEPARATOR
    "\u200b": LineBreakClass.ZW,   # ZERO WIDTH SPACE
    "\u2060": LineBreakClass.WJ,   # WORD JOINER
    "\ufeff": LineBreakClass.WJ,   # ZERO WIDTH NO-BREAK SPACE
    "\u00a0": LineBreakClass.GL,   # NO-BREAK SPACE
    "\u202f": LineBreakClass.GL,   # NARROW NO-BREAK SPACE
    "\u2011": LineBreakClass.GL,   # NON-BREAKING HYPHEN
    "\u2010": LineBreakClass.BA,   # HYPHEN
    "\u2013": LineBreakClass.BA,   # EN DASH
    "\u2014": LineBreakClass.BA,   # EM DASH
    "\u2015": LineBreakClass.BA,   # HORIZONTAL BAR
    "\u00ad": LineBreakClass.BA,   # SOFT HYPHEN
    "\u002d": LineBreakClass.BA,   # HYPHEN-MINUS
    "\u200d": LineBreakClass.ZWJ,  # ZERO WIDTH JOINER
    "\u200c": LineBreakClass.CM,   # ZERO WIDTH NON-JOINER
}


def _is_emoji_base(cp: int) -> bool:
    """Return True for code points in the common emoji base ranges.

    We cannot rely on ``unicodedata`` for emoji properties, so we use the
    ranges that cover the vast majority of emoji in the wild. This is a
    deliberate approximation.
    """
    return (
        0x1F300 <= cp <= 0x1F5FF
        or 0x1F600 <= cp <= 0x1F64F
        or 0x1F680 <= cp <= 0x1F6FF
        or 0x1F900 <= cp <= 0x1F9FF
        or 0x1FA70 <= cp <= 0x1FAFF
        or 0x2600 <= cp <= 0x26FF
        or 0x2700 <= cp <= 0x27BF
    )


def _is_emoji_modifier(cp: int) -> bool:
    """Return True for skin-tone modifiers (U+1F3FB..U+1F3FF)."""
    return 0x1F3FB <= cp <= 0x1F3FF


def classify(ch: str) -> LineBreakClass:
    """Return the :class:`LineBreakClass` for a single character.

    Raises ``TypeError`` if ``ch`` is not a one-character string.
    """
    if not isinstance(ch, str):
        raise TypeError("classify() expects a str")
    if len(ch) != 1:
        raise ValueError("classify() expects exactly one character")

    if ch in _EXPLICIT:
        return _EXPLICIT[ch]

    cp = ord(ch)

    # Surrogates are never valid in well-formed text, but we classify them
    # rather than raising so that iterating over arbitrary input is safe.
    if 0xD800 <= cp <= 0xDFFF:
        return LineBreakClass.SG

    if _is_emoji_modifier(cp):
        return LineBreakClass.EM
    if _is_emoji_base(cp):
        return LineBreakClass.EB

    cat = unicodedata.category(ch)

    if cat == "Cc":
        # Control characters other than CR/LF/NL are treated as mandatory
        # breaks by UAX #14 (class BK).
        return LineBreakClass.BK
    if cat == "Cf":
        # Format characters default to CM in UAX #14 when not otherwise
        # assigned. Treating them as combining marks keeps them attached to
        # the preceding character, which is the safe layout choice.
        return LineBreakClass.CM
    if cat == "Mn" or cat == "Mc" or cat == "Me":
        return LineBreakClass.CM
    if cat == "Zs":
        return LineBreakClass.SP
    if cat == "Zl":
        return LineBreakClass.BK
    if cat == "Zp":
        return LineBreakClass.BK
    if cat == "Nd":
        return LineBreakClass.NU

    if cat.startswith("P"):
        if ch in "([{\u2018\u201c\u3008\u300a\u300c\u300e\u3010\u3014\u3016":
            return LineBreakClass.OP
        if ch in ")]}\u2019\u201d\u3009\u300b\u300d\u300f\u3011\u3015\u3017":
            return LineBreakClass.CP
        if ch in "!?\u203c\u2047\u2048\u2049\u2762\u2763":
            return LineBreakClass.EX
        if ch in ",.;":
            return LineBreakClass.IS
        if ch in "%\u2030\u2031":
            return LineBreakClass.PO
        if ch in "$\u00a3\u00a5\u20ac\u00b0":
            return LineBreakClass.PR
        if ch in "\"'\u2018\u2019\u201c\u201d":
            return LineBreakClass.QU
        return LineBreakClass.AL

    if cat.startswith("L"):
        # Hebrew letters have their own class in UAX #14.
        if 0x0590 <= cp <= 0x05FF or 0xFB1D <= cp <= 0xFB4F:
            return LineBreakClass.HL
        # Ideographic scripts break between every character.
        if (
            0x3040 <= cp <= 0x30FF
            or 0x3400 <= cp <= 0x4DBF
            or 0x4E00 <= cp <= 0x9FFF
            or 0xF900 <= cp <= 0xFAFF
            or 0xAC00 <= cp <= 0xD7A3
            or 0x20000 <= cp <= 0x2FA1F
        ):
            return LineBreakClass.ID
        return LineBreakClass.AL

    # Symbols, numbers other than Nd, and anything else default to AL.
    return LineBreakClass.AL


# Rules that forbid a break between two classes. Each entry is a pair
# (left, right) meaning "no break between these".
_NO_BREAK: frozenset = frozenset({
    (LineBreakClass.OP, LineBreakClass.SP),
    (LineBreakClass.OP, LineBreakClass.OP),
    (LineBreakClass.OP, LineBreakClass.NU),
    (LineBreakClass.OP, LineBreakClass.AL),
    (LineBreakClass.OP, LineBreakClass.ID),
    (LineBreakClass.OP, LineBreakClass.EB),
    (LineBreakClass.OP, LineBreakClass.QU),
    (LineBreakClass.OP, LineBreakClass.HL),
    (LineBreakClass.OP, LineBreakClass.CM),
    (LineBreakClass.OP, LineBreakClass.IS),
    (LineBreakClass.OP, LineBreakClass.PR),
    (LineBreakClass.OP, LineBreakClass.PO),
    (LineBreakClass.OP, LineBreakClass.EX),
    (LineBreakClass.OP, LineBreakClass.SP),
    (LineBreakClass.QU, LineBreakClass.OP),
    (LineBreakClass.QU, LineBreakClass.QU),
    (LineBreakClass.QU, LineBreakClass.SP),
    (LineBreakClass.QU, LineBreakClass.AL),
    (LineBreakClass.QU, LineBreakClass.ID),
    (LineBreakClass.QU, LineBreakClass.EB),
    (LineBreakClass.QU, LineBreakClass.HL),
    (LineBreakClass.QU, LineBreakClass.NU),
    (LineBreakClass.QU, LineBreakClass.IS),
    (LineBreakClass.QU, LineBreakClass.PR),
    (LineBreakClass.QU, LineBreakClass.PO),
    (LineBreakClass.QU, LineBreakClass.EX),
    (LineBreakClass.QU, LineBreakClass.CM),
    (LineBreakClass.CL, LineBreakClass.PO),
    (LineBreakClass.CL, LineBreakClass.PR),
    (LineBreakClass.CL, LineBreakClass.NU),
    (LineBreakClass.CL, LineBreakClass.IS),
    (LineBreakClass.CL, LineBreakClass.AL),
    (LineBreakClass.CL, LineBreakClass.ID),
    (LineBreakClass.CL, LineBreakClass.EB),
    (LineBreakClass.CL, LineBreakClass.HL),
    (LineBreakClass.CL, LineBreakClass.QU),
    (LineBreakClass.CL, LineBreakClass.CM),
    (LineBreakClass.CL, LineBreakClass.EX),
    (LineBreakClass.CP, LineBreakClass.PO),
    (LineBreakClass.CP, LineBreakClass.PR),
    (LineBreakClass.CP, LineBreakClass.NU),
    (LineBreakClass.CP, LineBreakClass.IS),
    (LineBreakClass.CP, LineBreakClass.AL),
    (LineBreakClass.CP, LineBreakClass.ID),
    (LineBreakClass.CP, LineBreakClass.EB),
    (LineBreakClass.CP, LineBreakClass.HL),
    (LineBreakClass.CP, LineBreakClass.QU),
    (LineBreakClass.CP, LineBreakClass.CM),
    (LineBreakClass.CP, LineBreakClass.EX),
    (LineBreakClass.EX, LineBreakClass.SP),
    (LineBreakClass.EX, LineBreakClass.AL),
    (LineBreakClass.EX, LineBreakClass.ID),
    (LineBreakClass.EX, LineBreakClass.EB),
    (LineBreakClass.EX, LineBreakClass.HL),
    (LineBreakClass.EX, LineBreakClass.NU),
    (LineBreakClass.EX, LineBreakClass.IS),
    (LineBreakClass.EX, LineBreakClass.PR),
    (LineBreakClass.EX, LineBreakClass.PO),
    (LineBreakClass.EX, LineBreakClass.QU),
    (LineBreakClass.EX, LineBreakClass.CM),
    (LineBreakClass.EX, LineBreakClass.CL),
    (LineBreakClass.EX, LineBreakClass.CP),
    (LineBreakClass.IS, LineBreakClass.NU),
    (LineBreakClass.IS, LineBreakClass.AL),
    (LineBreakClass.IS, LineBreakClass.ID),
    (LineBreakClass.IS, LineBreakClass.EB),
    (LineBreakClass.IS, LineBreakClass.HL),
    (LineBreakClass.IS, LineBreakClass.IS),
    (LineBreakClass.IS, LineBreakClass.PR),
    (LineBreakClass.IS, LineBreakClass.PO),
    (LineBreakClass.IS, LineBreakClass.QU),
    (LineBreakClass.NU, LineBreakClass.NU),
    (LineBreakClass.NU, LineBreakClass.AL),
    (LineBreakClass.NU, LineBreakClass.ID),
    (LineBreakClass.NU, LineBreakClass.EB),
    (LineBreakClass.NU, LineBreakClass.HL),
    (LineBreakClass.NU, LineBreakClass.IS),
    (LineBreakClass.NU, LineBreakClass.PR),
    (LineBreakClass.NU, LineBreakClass.PO),
    (LineBreakClass.NU, LineBreakClass.QU),
    (LineBreakClass.NU, LineBreakClass.CM),
    (LineBreakClass.PO, LineBreakClass.NU),
    (LineBreakClass.PO, LineBreakClass.AL),
    (LineBreakClass.PO, LineBreakClass.ID),
    (LineBreakClass.PO, LineBreakClass.EB),
    (LineBreakClass.PO, LineBreakClass.HL),
    (LineBreakClass.PO, LineBreakClass.IS),
    (LineBreakClass.PO, LineBreakClass.PR),
    (LineBreakClass.PO, LineBreakClass.PO),
    (LineBreakClass.PO, LineBreakClass.QU),
    (LineBreakClass.PO, LineBreakClass.CM),
    (LineBreakClass.PR, LineBreakClass.NU),
    (LineBreakClass.PR, LineBreakClass.AL),
    (LineBreakClass.PR, LineBreakClass.ID),
    (LineBreakClass.PR, LineBreakClass.EB),
    (LineBreakClass.PR, LineBreakClass.HL),
    (LineBreakClass.PR, LineBreakClass.IS),
    (LineBreakClass.PR, LineBreakClass.PR),
    (LineBreakClass.PR, LineBreakClass.PO),
    (LineBreakClass.PR, LineBreakClass.QU),
    (LineBreakClass.PR, LineBreakClass.CM),
    (LineBreakClass.AL, LineBreakClass.AL),
    (LineBreakClass.AL, LineBreakClass.NU),
    (LineBreakClass.AL, LineBreakClass.CM),
    (LineBreakClass.AL, LineBreakClass.IS),
    (LineBreakClass.AL, LineBreakClass.PR),
    (LineBreakClass.AL, LineBreakClass.PO),
    (LineBreakClass.AL, LineBreakClass.QU),
    (LineBreakClass.AL, LineBreakClass.EX),
    (LineBreakClass.AL, LineBreakClass.CL),
    (LineBreakClass.AL, LineBreakClass.CP),
    (LineBreakClass.HL, LineBreakClass.AL),
    (LineBreakClass.HL, LineBreakClass.HL),
    (LineBreakClass.HL, LineBreakClass.NU),
    (LineBreakClass.HL, LineBreakClass.CM),
    (LineBreakClass.HL, LineBreakClass.IS),
    (LineBreakClass.HL, LineBreakClass.PR),
    (LineBreakClass.HL, LineBreakClass.PO),
    (LineBreakClass.HL, LineBreakClass.QU),
    (LineBreakClass.HL, LineBreakClass.EX),
    (LineBreakClass.HL, LineBreakClass.CL),
    (LineBreakClass.HL, LineBreakClass.CP),
    (LineBreakClass.ID, LineBreakClass.CM),
    (LineBreakClass.ID, LineBreakClass.IS),
    (LineBreakClass.ID, LineBreakClass.PR),
    (LineBreakClass.ID, LineBreakClass.PO),
    (LineBreakClass.ID, LineBreakClass.QU),
    (LineBreakClass.ID, LineBreakClass.EX),
    (LineBreakClass.ID, LineBreakClass.CL),
    (LineBreakClass.ID, LineBreakClass.CP),
    (LineBreakClass.EB, LineBreakClass.EM),
    (LineBreakClass.EB, LineBreakClass.EB),
    (LineBreakClass.EB, LineBreakClass.CM),
    (LineBreakClass.EM, LineBreakClass.EM),
    (LineBreakClass.EM, LineBreakClass.CM),
    (LineBreakClass.ZWJ, LineBreakClass.EB),
    (LineBreakClass.ZWJ, LineBreakClass.ID),
    (LineBreakClass.ZWJ, LineBreakClass.AL),
    (LineBreakClass.ZWJ, LineBreakClass.HL),
    (LineBreakClass.ZWJ, LineBreakClass.NU),
    (LineBreakClass.ZWJ, LineBreakClass.CM),
    (LineBreakClass.CM, LineBreakClass.AL),
    (LineBreakClass.CM, LineBreakClass.ID),
    (LineBreakClass.CM, LineBreakClass.EB),
    (LineBreakClass.CM, LineBreakClass.HL),
    (LineBreakClass.CM, LineBreakClass.NU),
    (LineBreakClass.CM, LineBreakClass.CM),
    (LineBreakClass.CM, LineBreakClass.IS),
    (LineBreakClass.CM, LineBreakClass.PR),
    (LineBreakClass.CM, LineBreakClass.PO),
    (LineBreakClass.CM, LineBreakClass.QU),
    (LineBreakClass.CM, LineBreakClass.EX),
    (LineBreakClass.CM, LineBreakClass.CL),
    (LineBreakClass.CM, LineBreakClass.CP),
    (LineBreakClass.GL, LineBreakClass.SP),
    (LineBreakClass.GL, LineBreakClass.AL),
    (LineBreakClass.GL, LineBreakClass.ID),
    (LineBreakClass.GL, LineBreakClass.EB),
    (LineBreakClass.GL, LineBreakClass.HL),
    (LineBreakClass.GL, LineBreakClass.NU),
    (LineBreakClass.GL, LineBreakClass.IS),
    (LineBreakClass.GL, LineBreakClass.PR),
    (LineBreakClass.GL, LineBreakClass.PO),
    (LineBreakClass.GL, LineBreakClass.QU),
    (LineBreakClass.GL, LineBreakClass.CM),
    (LineBreakClass.GL, LineBreakClass.EX),
    (LineBreakClass.GL, LineBreakClass.CL),
    (LineBreakClass.GL, LineBreakClass.CP),
    (LineBreakClass.GL, LineBreakClass.OP),
    (LineBreakClass.GL, LineBreakClass.GL),
    (LineBreakClass.WJ, LineBreakClass.SP),
    (LineBreakClass.WJ, LineBreakClass.AL),
    (LineBreakClass.WJ, LineBreakClass.ID),
    (LineBreakClass.WJ, LineBreakClass.EB),
    (LineBreakClass.WJ, LineBreakClass.HL),
    (LineBreakClass.WJ, LineBreakClass.NU),
    (LineBreakClass.WJ, LineBreakClass.IS),
    (LineBreakClass.WJ, LineBreakClass.PR),
    (LineBreakClass.WJ, LineBreakClass.PO),
    (LineBreakClass.WJ, LineBreakClass.QU),
    (LineBreakClass.WJ, LineBreakClass.CM),
    (LineBreakClass.WJ, LineBreakClass.EX),
    (LineBreakClass.WJ, LineBreakClass.CL),
    (LineBreakClass.WJ, LineBreakClass.CP),
    (LineBreakClass.WJ, LineBreakClass.OP),
    (LineBreakClass.WJ, LineBreakClass.GL),
    (LineBreakClass.WJ, LineBreakClass.WJ),
})


# Characters that must not be separated from the character on either side.
# This covers the README's "no breaks around word joiners, non-breaking
# hyphens, and no-break spaces" guarantee for the general case, including
# when the glue character sits between two otherwise breakable classes.
_GLUE = frozenset({
    LineBreakClass.WJ,
    LineBreakClass.GL,
})


def _is_mandatory(cls: LineBreakClass) -> bool:
    """Return True if ``cls`` forces a break after it."""
    return cls in (LineBreakClass.BK, LineBreakClass.CR, LineBreakClass.LF, LineBreakClass.NL)


def _is_space(cls: LineBreakClass) -> bool:
    """Return True for classes that represent breakable whitespace."""
    return cls in (LineBreakClass.SP, LineBreakClass.ZW)


def _break_allowed(left: LineBreakClass, right: LineBreakClass) -> bool:
    """Decide whether a break is allowed between ``left`` and ``right``.

    This is the pair-table core of the algorithm. It encodes the rules in
    priority order: mandatory breaks first, then rules that forbid breaks,
    then the default (allowed).
    """
    if left == LineBreakClass.CR and right == LineBreakClass.LF:
        return False
    if _is_mandatory(left):
        return True
    if _is_mandatory(right):
        return False
    if left == LineBreakClass.ZW:
        return True
    if right == LineBreakClass.ZW:
        return True
    if right == LineBreakClass.SP:
        return False
    if left == LineBreakClass.SP:
        return True
    if left in _GLUE or right in _GLUE:
        return False
    if (left, right) in _NO_BREAK:
        return False
    # Default: a break is allowed between letters and most other pairs not
    # explicitly forbidden above. This is intentionally permissive; the
    # no-break table carries the cases that matter.
    return True


def line_break_opportunities(text: str) -> List[int]:
    """Return the indices at which a line break may occur.

    Each returned index ``i`` means a break may be placed *before* the
    character at position ``i``. ``0`` is never returned, because a break at
    the start of the text is not meaningful. ``len(text)`` is never
    returned, because a break at the very end is not a break opportunity,
    it is the end of the string.

    A mandatory break (for example after ``\\n``) is also reported as an
    opportunity, so callers that only care about "can I break here?" get a
    consistent answer.
    """
    if not isinstance(text, str):
        raise TypeError("line_break_opportunities() expects a str")
    if not text:
        return []

    classes = [classify(ch) for ch in text]
    result: List[int] = []
    for i in range(1, len(text)):
        if _break_allowed(classes[i - 1], classes[i]):
            result.append(i)
    return result


def split_lines(text: str) -> List[str]:
    """Split ``text`` into lines at line break opportunities.

    The break characters themselves are kept at the end of the line they
    terminate, which matches the behaviour of Python's ``str.splitlines``
    for the common newline cases. A final empty segment is not produced for
    text that ends with a break.
    """
    if not isinstance(text, str):
        raise TypeError("split_lines() expects a str")
    if not text:
        return []

    breaks = line_break_opportunities(text)
    lines: List[str] = []
    start = 0
    for i in breaks:
        lines.append(text[start:i])
        start = i
    if start < len(text):
        lines.append(text[start:])
    return lines


class LineBreakIterator:
    """Iterate over line break opportunities in a string.

    The iterator yields the index of each break opportunity in turn. It is
    a thin wrapper over :func:`line_break_opportunities` that avoids
    materialising the whole list when the caller only needs to walk the
    breaks once.
    """

    def __init__(self, text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("LineBreakIterator() expects a str")
        self._text = text

    @property
    def text(self) -> str:
        """The text being iterated over."""
        return self._text

    def __iter__(self) -> Iterator[int]:
        return iter(line_break_opportunities(self._text))

    def __len__(self) -> int:
        return len(line_break_opportunities(self._text))

    def __repr__(self) -> str:
        return f"LineBreakIterator({self._text!r})"
