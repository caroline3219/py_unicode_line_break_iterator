# py_unicode_line_break_iterator

Segment text into lines at valid UAX #14 line break opportunities for text layout engines.

```python
from py_unicode_line_break_iterator import (
    LineBreakIterator,
    classify,
    line_break_opportunities,
    split_lines,
)

# Where can we break?
line_break_opportunities("ab cd")      # [3]
line_break_opportunities("\u4e00\u4e01")  # [1]

# Split into lines, keeping break characters on the line they end.
split_lines("a\nb")                   # ['a\n', 'b']
split_lines("ab cd")                  # ['ab ', 'cd']

# Walk the breaks without building a list.
for index in LineBreakIterator("ab cd"):
    print(index)                      # 3

# Classify a single character.
classify("a")                         # LineBreakClass.AL
classify(" ")                         # LineBreakClass.SP
```

## Why this exists

Text layout engines need to know where a line may legally be broken. The full
UAX #14 algorithm is specified against a data table (`LineBreak.txt`) that is
large, changes with every Unicode release, and would have to be regenerated to
stay current. This library takes the other trade-off: it derives a reduced set
of line break classes from Python's standard-library `unicodedata` module and
applies the pair-table rules that matter for ordinary prose, numbers, CJK text,
and a handful of punctuation cases. The result is small, dependency-free, and
stable across Unicode versions, at the cost of not being a complete
implementation of the standard.

## What it handles

- Mandatory breaks after `\n`, `\r`, `\r\n`, and the Unicode line/paragraph
  separators.
- No breaks inside a run of letters, digits, or combining marks.
- Breaks between words at spaces, with the space kept on the preceding line.
- Breaks between ideographic characters.
- No breaks around word joiners, non-breaking hyphens, and no-break spaces.
- Breaks at zero-width spaces.
- No breaks before closing punctuation or after opening punctuation.

## The awkward edge

`split_lines` keeps the break character at the end of the line it terminates,
which is what most layout engines want but is not what every caller expects.
If you need the newline stripped, call `line_break_opportunities` and slice the
text yourself, or strip the trailing character from each returned line.

A second edge: `line_break_opportunities` never returns `0` or `len(text)`.
A break before the first character or after the last is not a break
opportunity, it is the boundary of the string.

## API

- `classify(ch)` — return the `LineBreakClass` for a one-character string.
- `line_break_opportunities(text)` — return a list of indices where a break
  may occur, each meaning "break before this index".
- `split_lines(text)` — return the text split at those indices.
- `LineBreakIterator(text)` — iterable over the break indices, with `.text`.
- `LineBreakClass` — enum of the reduced line break classes.
