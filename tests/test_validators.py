"""Tests for validators.py content validation functions."""

from unittest.mock import patch, MagicMock
from discover.validators import (
    is_obviously_useless,
    is_false_positive_url,
    has_positive_signals,
    check_page_content,
)
from discover.filters import has_promising_keywords, should_skip_link_text


class TestHasPromisingKeywords:
    """Tests for has_promising_keywords function."""

    def test_has_promising_keywords_positive(self):
        """Should detect promising keywords."""
        assert has_promising_keywords("Call for Reviewers") is True
        assert has_promising_keywords("Reviewer Nomination") is True

    def test_has_promising_keywords_negative(self):
        """Should not detect non-promising keywords."""
        assert has_promising_keywords("Conference Information") is False

    def test_has_promising_keywords_case_insensitive(self):
        """Should be case-insensitive."""
        assert has_promising_keywords("CALL FOR REVIEWERS") is True


class TestShouldSkipLinkText:
    """Tests for should_skip_link_text function."""

    def test_should_skip_about(self):
        """Should skip 'About' links."""
        assert should_skip_link_text("about") is True

    def test_should_skip_sponsor(self):
        """Should skip 'Sponsor' links."""
        assert should_skip_link_text("sponsor") is True

    def test_should_not_skip_reviewer_call(self):
        """Should not skip reviewer-related links."""
        assert should_skip_link_text("Call for Reviewers") is False

    def test_should_skip_overridden_by_promising_keywords(self):
        """Promising keywords should override skip."""
        assert should_skip_link_text("About Reviewer Nomination") is False


class TestIsObviouslyUseless:
    """Tests for is_obviously_useless function."""

    def test_useless_pdf(self):
        """Should filter PDF files."""
        assert is_obviously_useless("https://example.com/document.pdf") is True

    def test_useless_image(self):
        """Should filter image files."""
        assert is_obviously_useless("https://example.com/image.jpg") is True

    def test_useless_social_media(self):
        """Should filter social media URLs."""
        assert is_obviously_useless("https://twitter.com/user") is True
        assert is_obviously_useless("https://linkedin.com/company") is True

    def test_useless_login_page(self):
        """Should filter login/register pages."""
        assert is_obviously_useless("https://example.com/login") is True
        assert is_obviously_useless("https://example.com/register") is True

    def test_useless_about_page(self):
        """Should filter about pages."""
        assert is_obviously_useless("https://example.com/about") is True

    def test_useless_venue_page(self):
        """Should filter venue pages."""
        assert is_obviously_useless("https://example.com/venue") is True

    def test_useful_reviewer_page(self):
        """Should keep reviewer-related pages."""
        assert is_obviously_useless("https://example.com/reviewer-call") is False

    def test_useful_with_promising_keyword(self):
        """Should keep URLs with promising keywords despite useless path."""
        assert (
            is_obviously_useless("https://example.com/about/reviewer-nomination")
            is False
        )


class TestIsFalsePositiveUrl:
    """Tests for is_false_positive_url function."""

    def test_false_positive_committee_listing(self):
        """Should detect committee listing pages."""
        assert is_false_positive_url("https://example.com/committee") is True

    def test_false_positive_track_page(self):
        """Should detect track pages without reviewer context."""
        assert is_false_positive_url("https://example.com/track/") is True

    def test_false_positive_call_for_papers(self):
        """Should detect call for papers pages."""
        assert is_false_positive_url("https://example.com/call-for-papers") is True

    def test_false_positive_root_domain(self):
        """Should filter root domain."""
        assert is_false_positive_url("https://example.org") is True
        assert is_false_positive_url("https://example.com/") is True

    def test_false_positive_old_year(self):
        """Should filter URLs from old years."""
        assert is_false_positive_url("https://example.com/2020/page") is True

    def test_true_positive_reviewer_committee(self):
        """Should not filter reviewer committee pages with recruitment terms."""
        assert (
            is_false_positive_url("https://example.com/committee/call-for-reviewers")
            is False
        )

    def test_true_positive_artifact_track(self):
        """Should not filter artifact evaluation tracks."""
        assert is_false_positive_url("https://example.com/track/artifact") is False

    def test_true_positive_current_year(self):
        """Should not filter current year URLs."""
        import datetime

        current_year = datetime.date.today().year
        assert (
            is_false_positive_url(f"https://example.com/{current_year}/page") is False
        )


class TestHasPositiveSignals:
    """Tests for has_positive_signals function."""

    def test_positive_signal_self_nomination(self):
        """Should detect 'self-nomination' signal."""
        content = (
            "We invite you to submit your self-nomination for our review committee."
        )
        assert has_positive_signals(content) is True

    def test_positive_signal_call_for_reviewer(self):
        """Should detect 'call for reviewer' signal."""
        content = "call for reviewers now open!".lower()
        assert has_positive_signals(content) is True

    def test_positive_signal_become_reviewer(self):
        """Should detect 'become a reviewer' signal."""
        content = "become a reviewer for our conference.".lower()
        assert has_positive_signals(content) is True

    def test_positive_signal_nomination_form(self):
        """Should detect 'nomination form' signal."""
        content = "Please fill out our reviewer nomination form."
        assert has_positive_signals(content) is True

    def test_negative_signal_workshop_proposal(self):
        """Should reject workshop proposal calls."""
        content = "Call for workshop proposals now open!"
        assert has_positive_signals(content) is False

    def test_negative_signal_overridden_by_reviewer_term(self):
        """Reviewer terms should override negative signals."""
        content = "call for workshop proposals and please fill out our reviewer nomination form".lower()
        assert has_positive_signals(content) is True

    def test_negative_signal_demo_proposal(self):
        """Should reject demo proposals."""
        content = "Call for demonstration proposals"
        assert has_positive_signals(content) is False

    def test_medium_confidence_with_context(self):
        """Should detect medium-confidence signals with context."""
        content = "Submit your application form to join our review committee."
        assert has_positive_signals(content) is True

    def test_no_signals(self):
        """Should reject content without signals."""
        content = "General conference information"
        assert has_positive_signals(content) is False


def _make_mock_response(status_code=200, url="", html=""):
    """Create a mock response with proper content.decode() setup."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.url = url
    mock_response.content = MagicMock()
    mock_response.content.decode.return_value = html
    return mock_response


class TestCheckPageContent:
    """Tests for check_page_content function."""

    @patch("discover.http.get")
    def test_check_page_content_valid_call(self, mock_get):
        """Should detect valid reviewer call."""
        mock_get.return_value = _make_mock_response(
            status_code=200,
            url="https://example.com/reviewer-call",
            html="Call for reviewers now open! Please nominate yourself.",
        )

        result = check_page_content("https://example.com/reviewer-call")
        assert result is not None
        assert result["has_reviewer_call"] is True

    @patch("discover.http.get")
    def test_check_page_content_false_positive_url(self, mock_get):
        """Should reject known false positive URLs."""
        result = check_page_content("https://example.com/committee")
        assert result is None
        mock_get.assert_not_called()

    @patch("discover.http.get")
    def test_check_page_content_http_error(self, mock_get):
        """Should handle HTTP errors."""
        import requests

        mock_get.side_effect = requests.ConnectionError("Connection error")

        result = check_page_content("https://example.com/page")
        assert result is None

    @patch("discover.http.get")
    def test_check_page_content_non_200_status(self, mock_get):
        """Should reject non-200 status codes."""
        mock_get.return_value = _make_mock_response(status_code=404)

        result = check_page_content("https://example.com/page")
        assert result is None

    @patch("discover.http.get")
    def test_check_page_content_no_positive_signals(self, mock_get):
        """Should reject content without positive signals."""
        mock_get.return_value = _make_mock_response(
            status_code=200,
            url="https://example.com/page",
            html="General conference information",
        )

        result = check_page_content("https://example.com/page")
        assert result is None

    @patch("discover.http.get")
    def test_check_page_content_returns_matched_keywords(self, mock_get):
        """Should return matched keyword information."""
        mock_get.return_value = _make_mock_response(
            status_code=200,
            url="https://example.com/reviewer-call",
            html="Call for reviewers. Please nominate yourself for our review committee.",
        )

        result = check_page_content("https://example.com/reviewer-call")
        assert result is not None
        assert "matched_keywords" in result
        assert "matched_keyword_indices" in result
        assert "url" in result
