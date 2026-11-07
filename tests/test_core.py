"""Tests for the Unicode line break iterator core."""

import unittest

from py_unicode_line_break_iterator import (
    LineBreakClass,
    LineBreakIterator,
    classify,
    line_break_opportunities,
    split_lines,
)


class ClassifyTests(unittest.TestCase):
    def test_letters_are_alphabetic(self):
        self.assertEqual(classify("a"), LineBreakClass.AL)
        self.assertEqual(classify("Z"), LineBreakClass.AL)

    def test_digits_are_numeric(self):
        self.assertEqual(classify("0"), LineBreakClass.NU)
        self.assertEqual(classify("9"), LineBreakClass.NU)

    def test_space(self):
        self.assertEqual(classify(" "), LineBreakClass.SP)

    def test_newline_is_lf(self):
        self.assertEqual(classify("\n"), LineBreakClass.LF)

    def test_carriage_return_is_cr(self):
        self.assertEqual(classify("\r"), LineBreakClass.CR)

    def test_hyphen(self):
        self.assertEqual(classify("-"), LineBreakClass.BA)

    def test_non_breaking_hyphen_is_glue(self):
        self.assertEqual(classify("\u2011"), LineBreakClass.GL)

    def test_no_break_space_is_glue(self):
        self.assertEqual(classify("\u00a0"), LineBreakClass.GL)

    def test_open_paren(self):
        self.assertEqual(classify("("), LineBreakClass.OP)

    def test_close_paren(self):
        self.assertEqual(classify(")"), LineBreakClass.CP)

    def test_ideograph(self):
        self.assertEqual(classify("\u4e00"), LineBreakClass.ID)

    def test_hebrew_letter(self):
        self.assertEqual(classify("\u05d0"), LineBreakClass.HL)

    def test_combining_mark(self):
        self.assertEqual(classify("\u0301"), LineBreakClass.CM)

    def test_zero_width_space(self):
        self.assertEqual(classify("\u200b"), LineBreakClass.ZW)

    def test_word_joiner(self):
        self.assertEqual(classify("\u2060"), LineBreakClass.WJ)

    def test_rejects_empty_string(self):
        with self.assertRaises(ValueError):
            classify("")

    def test_rejects_multi_character_string(self):
        with self.assertRaises(ValueError):
            classify("ab")

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            classify(65)


class OpportunitiesTests(unittest.TestCase):
    def test_empty_text_has_no_breaks(self):
        self.assertEqual(line_break_opportunities(""), [])

    def test_single_character_has_no_breaks(self):
        self.assertEqual(line_break_opportunities("a"), [])

    def test_break_between_words(self):
        # "ab cd": break before 'c' at index 3.
        self.assertEqual(line_break_opportunities("ab cd"), [3])

    def test_break_after_newline(self):
        # "a\nb": mandatory break after \n, so index 2.
        self.assertEqual(line_break_opportunities("a\nb"), [2])

    def test_crlf_is_single_break(self):
        # "a\r\nb": break after the \n only.
        self.assertEqual(line_break_opportunities("a\r\nb"), [3])

    def test_no_break_inside_word(self):
        self.assertEqual(line_break_opportunities("hello"), [])

    def test_no_break_before_space(self):
        # "ab cd": no break before the space at index 2.
        self.assertNotIn(2, line_break_opportunities("ab cd"))

    def test_no_break_after_open_paren_before_letter(self):
        self.assertEqual(line_break_opportunities("(a"), [])

    def test_no_break_before_close_paren(self):
        self.assertEqual(line_break_opportunities("a)"), [])

    def test_break_between_ideographs(self):
        self.assertEqual(line_break_opportunities("\u4e00\u4e01"), [1])

    def test_no_break_around_word_joiner(self):
        self.assertEqual(line_break_opportunities("a\u2060b"), [])

    def test_break_at_zero_width_space(self):
        self.assertEqual(line_break_opportunities("a\u200bb"), [1, 2])

    def test_no_break_around_non_breaking_hyphen(self):
        self.assertEqual(line_break_opportunities("a\u2011b"), [])

    def test_no_break_around_no_break_space(self):
        self.assertEqual(line_break_opportunities("a\u00a0b"), [])

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            line_break_opportunities(None)


class SplitLinesTests(unittest.TestCase):
    def test_empty_text(self):
        self.assertEqual(split_lines(""), [])

    def test_single_line(self):
        self.assertEqual(split_lines("hello"), ["hello"])

    def test_two_lines_on_newline(self):
        self.assertEqual(split_lines("a\nb"), ["a\n", "b"])

    def test_trailing_newline_does_not_add_empty_line(self):
        self.assertEqual(split_lines("a\n"), ["a\n"])

    def test_wraps_at_space(self):
        self.assertEqual(split_lines("ab cd"), ["ab ", "cd"])

    def test_ideographs_split_apart(self):
        self.assertEqual(split_lines("\u4e00\u4e01"), ["\u4e00", "\u4e01"])

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            split_lines(42)


class IteratorTests(unittest.TestCase):
    def test_iterates_break_indices(self):
        it = LineBreakIterator("ab cd")
        self.assertEqual(list(it), [3])

    def test_length_matches_list(self):
        it = LineBreakIterator("ab cd")
        self.assertEqual(len(it), len(line_break_opportunities("ab cd")))

    def test_text_property(self):
        it = LineBreakIterator("ab cd")
        self.assertEqual(it.text, "ab cd")

    def test_repr(self):
        it = LineBreakIterator("ab")
        self.assertEqual(repr(it), "LineBreakIterator('ab')")

    def test_empty_text_iterates_nothing(self):
        self.assertEqual(list(LineBreakIterator("")), [])

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            LineBreakIterator(b"bytes")


if __name__ == "__main__":
    unittest.main()
