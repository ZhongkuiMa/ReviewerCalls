"""Fetch and extract text from URLs."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

from discover import http as discover_http
from discover import utils as discover_utils

logger = logging.getLogger(__name__)


def fetch_page_text(url: str, max_chars: int = 6000) -> tuple[str, str]:
    """Fetch URL and extract visible text.

    :param url: URL to fetch
    :param max_chars: Maximum characters to return
    :returns: Tuple of (text, status). Status is 'ok', 'blocked', 'error', or 'empty'
    """
    if "linkedin.com" in urlparse(url).netloc:
        return "", "blocked"

    try:
        response = discover_http.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.debug(f"Fetch error: {url} - {e}")
        return "", "error"

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return "", "error"

    text = discover_utils.extract_visible_text(response.text)

    if not text or len(text) < 200:
        return "", "empty"

    if len(text) > max_chars:
        text = text[:max_chars]

    return text, "ok"
