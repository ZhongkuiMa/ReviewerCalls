"""HTML parsing and date extraction utilities."""

from __future__ import annotations

import logging
import re
from datetime import date
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

from discover.utils import normalize_url
from discover import http

logger = logging.getLogger(__name__)


class LinkExtractor(HTMLParser):
    """Extract links with text from HTML documents.

    Usage:
        parser = LinkExtractor(base_url)
        parser.feed(html_content)
        links = parser.links  # List[dict] with 'url' and 'text' keys
    """

    def __init__(self, base_url: str):
        """Initialize the link extractor.

        :param base_url: Base URL for resolving relative links
        """
        super().__init__()
        self.base_url = base_url
        self.links = []
        self._in_a = False
        self._current_href = ""
        self._current_text = ""

    def handle_starttag(self, tag, attrs):
        """Handle opening HTML tags.

        :param tag: Tag name
        :param attrs: Tag attributes
        """
        if tag == "a":
            self._in_a = True
            self._current_text = ""
            self._current_href = dict(attrs).get("href", "")

    def handle_endtag(self, tag):
        """Handle closing HTML tags.

        :param tag: Tag name
        """
        if tag == "a":
            self._in_a = False
            if self._current_href:
                full_url = urljoin(self.base_url, self._current_href)
                full_url = normalize_url(full_url)
                self.links.append({"url": full_url, "text": self._current_text.strip()})

    def handle_data(self, data):
        """Handle text data within HTML tags.

        :param data: Text content
        """
        if self._in_a:
            self._current_text += data


def extract_page_date(url: str, timeout: int = 10) -> str:
    """Extract publication date from URL.

    :param url: URL to extract date from
    :param timeout: Request timeout in seconds
    :return: ISO date string (YYYY-MM-DD), or today's date if extraction fails
    """
    try:
        response = http.get(url, timeout=timeout)

        if "Last-Modified" in response.headers:
            dt = parsedate_to_datetime(response.headers["Last-Modified"])
            return dt.date().isoformat()

        html = response.content.decode("utf-8", errors="replace")

        meta_patterns = [
            r'<meta\s+property="article:published_time"\s+content="([^"]+)"',
            r'<meta\s+name="date"\s+content="([^"]+)"',
            r'<meta\s+name="DC\.date"\s+content="([^"]+)"',
            r'<meta\s+property="og:published_time"\s+content="([^"]+)"',
        ]

        for pattern in meta_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                parsed = match.group(1).split("T")[0]
                if re.match(r"\d{4}-\d{2}-\d{2}", parsed):
                    return parsed

        content_patterns = [
            r"(?:Posted|Published|Updated):\s*(\d{4}-\d{2}-\d{2})",
            r"(?:Posted|Published|Updated):\s*(\w+\s+\d{1,2},?\s+\d{4})",
        ]

        for pattern in content_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    from dateutil import parser

                    parsed_date = parser.parse(date_str).date()
                    return parsed_date.isoformat()
                except ImportError:
                    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                        return date_str
                except (ValueError, OverflowError):
                    pass

        return date.today().isoformat()

    except requests.RequestException as e:
        logger.warning("Could not extract date from %s: %s", url, e)
        return date.today().isoformat()
