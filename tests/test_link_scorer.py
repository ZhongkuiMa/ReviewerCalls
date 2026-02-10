"""Tests for keyword_matcher functions in filters.py."""

from discover.filters import has_filter_keyword, has_stop_word, should_explore_link


class TestHasFilterKeyword:
    """Tests for has_filter_keyword function."""

    def test_has_filter_keyword_reviewer(self):
        """Should detect 'reviewer' keyword."""
        assert has_filter_keyword("call for reviewers") is True

    def test_has_filter_keyword_pc(self):
        """Should detect 'pc' keyword."""
        assert has_filter_keyword("program committee") is True

    def test_has_filter_keyword_committee(self):
        """Should detect 'committee' keyword."""
        assert has_filter_keyword("join our committee") is True

    def test_has_filter_keyword_nomination(self):
        """Should detect 'nomination' keyword."""
        assert has_filter_keyword("reviewer nomination") is True

    def test_has_filter_keyword_case_insensitive(self):
        """Should be case-insensitive."""
        assert has_filter_keyword("CALL FOR REVIEWERS") is True
        assert has_filter_keyword("Call For Reviewers") is True

    def test_has_filter_keyword_no_match(self):
        """Should return False when no keyword matches."""
        assert has_filter_keyword("about our conference") is False

    def test_has_filter_keyword_in_url_path(self):
        """Should match keywords in URL paths."""
        assert has_filter_keyword("/reviewers/") is True
        assert has_filter_keyword("/committee") is True

    def test_has_filter_keyword_substring_match(self):
        """Should match keywords as substrings."""
        assert has_filter_keyword("we need reviewers") is True
        assert has_filter_keyword("pc_recruitment") is True


class TestHasStopWord:
    """Tests for has_stop_word function."""

    def test_has_stop_word_without_reviewer_keywords(self):
        """Should return True for stop words without reviewer keywords."""
        # "about" is typically a stop word
        assert has_stop_word("about") is True

    def test_has_stop_word_with_reviewer_keywords(self):
        """Should return False if reviewer keywords present."""
        assert has_stop_word("about reviewers") is False
        assert has_stop_word("about the nomination process") is False

    def test_has_stop_word_case_insensitive(self):
        """Should be case-insensitive."""
        assert has_stop_word("ABOUT") is True
        assert has_stop_word("About Reviewers") is False

    def test_has_stop_word_no_stop_word(self):
        """Should return False if no stop word."""
        assert has_stop_word("conference details") is False

    def test_has_stop_word_pc_keyword_prevents_stop(self):
        """Should not mark as stop word if 'pc' keyword present."""
        assert has_stop_word("about pc member") is False

    def test_has_stop_word_committee_keyword_prevents_stop(self):
        """Should not mark as stop word if 'committee' keyword present."""
        assert has_stop_word("about committee") is False

    def test_has_stop_word_nomination_keyword_prevents_stop(self):
        """Should not mark as stop word if 'nomination' keyword present."""
        assert has_stop_word("about nomination") is False

    def test_has_stop_word_call_keyword_prevents_stop(self):
        """Should not mark as stop word if 'call' keyword present."""
        assert has_stop_word("about call for papers") is False


class TestShouldExploreLink:
    """Tests for should_explore_link function."""

    def test_should_explore_reviewer_in_text(self):
        """Should explore if 'reviewer' in link text."""
        link = {"url": "https://example.com/page", "text": "Call for Reviewers"}
        assert should_explore_link(link) is True

    def test_should_explore_pc_in_url(self):
        """Should explore if 'pc' in URL path."""
        link = {"url": "https://example.com/pc/", "text": ""}
        assert should_explore_link(link) is True

    def test_should_explore_committee_in_url(self):
        """Should explore if 'committee' in URL path."""
        link = {"url": "https://example.com/committee", "text": ""}
        assert should_explore_link(link) is True

    def test_should_not_explore_no_keywords(self):
        """Should not explore if no keywords."""
        link = {"url": "https://example.com/page", "text": "General Information"}
        assert should_explore_link(link) is False

    def test_should_not_explore_with_stop_word(self):
        """Should not explore if has stop word and no reviewer keywords."""
        link = {"url": "https://example.com/about", "text": ""}
        assert should_explore_link(link) is False

    def test_should_explore_keyword_overrides_stop_word(self):
        """Should explore if keyword present despite stop word."""
        link = {"url": "https://example.com/about/reviewers", "text": ""}
        assert should_explore_link(link) is True

    def test_should_explore_missing_text_field(self):
        """Should handle missing text field."""
        link = {"url": "https://example.com/reviewers/"}
        assert should_explore_link(link) is True

    def test_should_explore_empty_text(self):
        """Should work with empty text field."""
        link = {"url": "https://example.com/page", "text": ""}
        assert should_explore_link(link) is False

    def test_should_explore_nomination_in_text(self):
        """Should explore if 'nomination' in link text."""
        link = {"url": "https://example.com/form", "text": "Reviewer Nomination Form"}
        assert should_explore_link(link) is True

    def test_should_explore_call_in_url(self):
        """Should explore if 'call' in URL path."""
        link = {"url": "https://example.com/call-for-reviewers", "text": ""}
        assert should_explore_link(link) is True

    def test_should_explore_case_insensitive(self):
        """Should be case-insensitive."""
        link = {"url": "https://example.com/REVIEWERS", "text": ""}
        assert should_explore_link(link) is True
        link = {"url": "https://example.com/page", "text": "CALL FOR REVIEWERS"}
        assert should_explore_link(link) is True
