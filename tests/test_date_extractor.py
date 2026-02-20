"""Tests for date extraction from web pages (parsers.py)."""

from datetime import date
from unittest.mock import patch, MagicMock
from discover.parsers import extract_page_date


def _make_mock_response(headers=None, html=""):
    """Create a mock response with proper content.decode() setup."""
    mock_response = MagicMock()
    mock_response.headers = headers or {}
    mock_response.content = MagicMock()
    mock_response.content.decode.return_value = html
    return mock_response


class TestExtractPageDate:
    """Tests for extract_page_date function."""

    @patch("discover.http.get")
    def test_extract_from_last_modified_header(self, mock_get):
        """Should extract date from Last-Modified header."""
        mock_get.return_value = _make_mock_response(
            headers={"Last-Modified": "Wed, 15 Jan 2026 10:30:00 GMT"}
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-01-15"

    @patch("discover.http.get")
    def test_extract_from_meta_article_published_time(self, mock_get):
        """Should extract from article:published_time meta tag."""
        mock_get.return_value = _make_mock_response(
            html='<meta property="article:published_time" content="2026-02-10T14:30:00Z">'
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-02-10"

    @patch("discover.http.get")
    def test_extract_from_meta_date_name(self, mock_get):
        """Should extract from date meta name."""
        mock_get.return_value = _make_mock_response(
            html='<meta name="date" content="2026-03-15">'
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-03-15"

    @patch("discover.http.get")
    def test_extract_from_meta_dc_date(self, mock_get):
        """Should extract from DC.date meta tag."""
        mock_get.return_value = _make_mock_response(
            html='<meta name="DC.date" content="2026-04-20">'
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-04-20"

    @patch("discover.http.get")
    def test_extract_from_meta_og_published_time(self, mock_get):
        """Should extract from og:published_time meta tag."""
        mock_get.return_value = _make_mock_response(
            html='<meta property="og:published_time" content="2026-05-25T09:00:00Z">'
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-05-25"

    @patch("discover.http.get")
    def test_extract_from_content_posted_pattern(self, mock_get):
        """Should extract from 'Posted:' content pattern."""
        mock_get.return_value = _make_mock_response(html="Posted: 2026-06-10")

        result = extract_page_date("https://example.com/page")
        assert result == "2026-06-10"

    @patch("discover.http.get")
    def test_extract_from_content_published_pattern(self, mock_get):
        """Should extract from 'Published:' content pattern."""
        mock_get.return_value = _make_mock_response(html="Published: 2026-07-05")

        result = extract_page_date("https://example.com/page")
        assert result == "2026-07-05"

    @patch("discover.http.get")
    def test_extract_from_content_updated_pattern(self, mock_get):
        """Should extract from 'Updated:' content pattern."""
        mock_get.return_value = _make_mock_response(html="Updated: 2026-08-12")

        result = extract_page_date("https://example.com/page")
        assert result == "2026-08-12"

    @patch("discover.http.get")
    def test_fallback_to_today(self, mock_get):
        """Should fallback to today's date if extraction fails."""
        mock_get.return_value = _make_mock_response(
            html="<html>No date information</html>"
        )

        result = extract_page_date("https://example.com/page")
        assert result == date.today().isoformat()

    @patch("discover.http.get")
    def test_exception_returns_today(self, mock_get):
        """Should return today's date on request exception."""
        import requests

        mock_get.side_effect = requests.ConnectionError("Connection error")

        result = extract_page_date("https://example.com/page")
        assert result == date.today().isoformat()

    @patch("discover.http.get")
    def test_timeout_parameter(self, mock_get):
        """Should use timeout parameter."""
        mock_get.return_value = _make_mock_response()

        extract_page_date("https://example.com/page", timeout=20)
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("timeout") == 20

    @patch("discover.http.get")
    def test_header_priority_over_meta(self, mock_get):
        """Should prioritize Last-Modified header over meta tags."""
        mock_get.return_value = _make_mock_response(
            headers={"Last-Modified": "Wed, 15 Jan 2026 10:30:00 GMT"},
            html='<meta name="date" content="2026-06-20">',
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-01-15"

    @patch("discover.http.get")
    def test_meta_priority_over_content(self, mock_get):
        """Should prioritize meta tags over content patterns."""
        mock_get.return_value = _make_mock_response(
            html='<meta name="date" content="2026-03-15">\nPublished: 2026-06-20'
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-03-15"

    @patch("discover.http.get")
    def test_user_agent_header(self, mock_get):
        """Should call HTTPClient.get which handles User-Agent headers."""
        mock_get.return_value = _make_mock_response()

        extract_page_date("https://example.com/page")
        assert mock_get.called
        assert mock_get.call_args[0][0] == "https://example.com/page"

    @patch("discover.http.get")
    def test_case_insensitive_meta_search(self, mock_get):
        """Should find meta tags case-insensitively."""
        mock_get.return_value = _make_mock_response(
            html='<META NAME="DATE" CONTENT="2026-05-10">'
        )

        result = extract_page_date("https://example.com/page")
        assert result == "2026-05-10"
