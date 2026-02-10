"""Tests for parsers.py HTML parsing utilities."""

from discover.parsers import LinkExtractor


class TestLinkExtractor:
    """Tests for LinkExtractor class."""

    def test_extract_single_link(self):
        """Should extract single link."""
        html = '<a href="/page">Click here</a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert len(parser.links) == 1
        assert parser.links[0]["url"] == "https://example.com/page"
        assert parser.links[0]["text"] == "Click here"

    def test_extract_multiple_links(self):
        """Should extract multiple links."""
        html = """
        <a href="/page1">Link 1</a>
        <a href="/page2">Link 2</a>
        <a href="/page3">Link 3</a>
        """
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert len(parser.links) == 3

    def test_extract_absolute_url(self):
        """Should preserve absolute URLs."""
        html = '<a href="https://other.com/page">Other site</a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert parser.links[0]["url"] == "https://other.com/page"

    def test_extract_relative_url(self):
        """Should resolve relative URLs."""
        html = '<a href="page">Link</a>'
        parser = LinkExtractor("https://example.com/subdir/")
        parser.feed(html)
        assert parser.links[0]["url"] == "https://example.com/subdir/page"

    def test_extract_root_relative_url(self):
        """Should resolve root-relative URLs."""
        html = '<a href="/page">Link</a>'
        parser = LinkExtractor("https://example.com/subdir/page/")
        parser.feed(html)
        assert parser.links[0]["url"] == "https://example.com/page"

    def test_extract_text_with_whitespace(self):
        """Should strip whitespace from link text."""
        html = '<a href="/page">  Click here  </a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert parser.links[0]["text"] == "Click here"

    def test_extract_empty_href(self):
        """Should skip links without href."""
        html = "<a>No href</a>"
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert len(parser.links) == 0

    def test_extract_normalizes_url(self):
        """Should normalize URLs to lowercase."""
        html = '<a href="/PAGE">Link</a>'
        parser = LinkExtractor("HTTPS://EXAMPLE.COM")
        parser.feed(html)
        assert parser.links[0]["url"] == "https://example.com/page"

    def test_extract_removes_fragment(self):
        """Should remove URL fragments."""
        html = '<a href="/page#section">Link</a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert parser.links[0]["url"] == "https://example.com/page"

    def test_extract_nested_tags(self):
        """Should extract text from nested tags."""
        html = '<a href="/page"><b>Bold</b> text</a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        # Text should contain content from nested tags
        assert "Bold" in parser.links[0]["text"]

    def test_extract_link_with_attributes(self):
        """Should handle links with multiple attributes."""
        html = '<a href="/page" class="btn" id="link1">Click</a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert parser.links[0]["url"] == "https://example.com/page"
        assert parser.links[0]["text"] == "Click"

    def test_extract_malformed_html(self):
        """Should handle well-formed HTML with missing closing tags."""
        html = '<a href="/page">Click</a><b>Here'  # b tag not closed, but a is
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert len(parser.links) == 1

    def test_extract_no_links(self):
        """Should return empty list when no links."""
        html = "<p>No links here</p>"
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert parser.links == []

    def test_extract_link_preserves_case_in_text(self):
        """Should preserve case in link text."""
        html = '<a href="/page">Click HERE</a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert parser.links[0]["text"] == "Click HERE"

    def test_extract_query_parameters(self):
        """Should preserve query parameters."""
        html = '<a href="/page?id=123&sort=name">Link</a>'
        parser = LinkExtractor("https://example.com")
        parser.feed(html)
        assert "id=123" in parser.links[0]["url"]
        assert "sort=name" in parser.links[0]["url"]
