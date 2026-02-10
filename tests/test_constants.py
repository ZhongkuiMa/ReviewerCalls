"""Tests for discover/constants.py keyword regex generation."""

import re
from discover.constants import (
    keyword_to_regex,
    KEYWORD_PATTERNS,
    STEP4_CONTENT_KEYWORDS,
)


class TestKeywordToRegex:
    """Tests for keyword_to_regex function."""

    def test_single_word_adds_optional_plural(self):
        pattern = keyword_to_regex("reviewer")
        assert re.search(pattern, "reviewer", re.IGNORECASE)
        assert re.search(pattern, "reviewers", re.IGNORECASE)

    def test_single_word_ending_in_s_no_double_plural(self):
        pattern = keyword_to_regex("reviewers")
        assert re.search(pattern, "reviewers", re.IGNORECASE)
        # Should not match "reviewerss"
        assert not re.search(pattern, "reviewerss", re.IGNORECASE)

    def test_multi_word_flexible_separator(self):
        pattern = keyword_to_regex("pc member")
        assert re.search(pattern, "pc member", re.IGNORECASE)
        assert re.search(pattern, "pc-member", re.IGNORECASE)
        assert re.search(pattern, "PC  Member", re.IGNORECASE)

    def test_multi_word_optional_plural_on_last(self):
        pattern = keyword_to_regex("pc member")
        assert re.search(pattern, "pc members", re.IGNORECASE)

    def test_hyphenated_keyword(self):
        pattern = keyword_to_regex("self-nomination")
        compiled = re.compile(pattern, re.IGNORECASE)
        assert compiled.search("self-nomination")
        assert compiled.search("self-nominations")
        assert compiled.search("Self-Nomination")

    def test_word_boundary_prevents_partial(self):
        pattern = keyword_to_regex("pc")
        compiled = re.compile(pattern, re.IGNORECASE)
        assert compiled.search("PC nomination")
        assert compiled.search("join PC")
        # "specific" contains "pc" but not at word boundary
        assert not compiled.search("specific")

    def test_case_insensitive_when_compiled(self):
        pattern = keyword_to_regex("call for reviewers")
        compiled = re.compile(pattern, re.IGNORECASE)
        assert compiled.search("Call For Reviewers")
        assert compiled.search("CALL FOR REVIEWERS")
        assert compiled.search("call for reviewers")

    def test_special_characters_escaped(self):
        # "ARR reviewer" should not treat "ARR" as a regex pattern
        pattern = keyword_to_regex("ARR reviewer")
        compiled = re.compile(pattern, re.IGNORECASE)
        assert compiled.search("ARR reviewer")


class TestKeywordPatterns:
    """Tests for pre-compiled KEYWORD_PATTERNS."""

    def test_patterns_count_matches_keywords(self):
        assert len(KEYWORD_PATTERNS) == len(STEP4_CONTENT_KEYWORDS)

    def test_all_patterns_are_compiled_regex(self):
        for p in KEYWORD_PATTERNS:
            assert isinstance(p, re.Pattern)

    def test_each_keyword_matches_itself(self):
        """Every keyword should match its own text."""
        for kw, pattern in zip(STEP4_CONTENT_KEYWORDS, KEYWORD_PATTERNS):
            assert pattern.search(kw), f"Keyword '{kw}' doesn't match its own pattern"
