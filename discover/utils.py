"""Helper utilities and URL functions."""

from __future__ import annotations

import datetime
import html as html_lib
import re

from urllib.parse import urlparse, urlencode, parse_qs

from discover import constants

# Regex patterns for visible text extraction (compiled once)
_RE_SCRIPT_STYLE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_RE_HTML_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_ALL_TAGS = re.compile(r"<[^>]+>")
_RE_WHITESPACE = re.compile(r"\s+")

# Tracking parameters to strip from URLs during normalization
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "fbclid",
    "gclid",
}

# Path suffixes to strip (index pages)
_INDEX_SUFFIXES = ("/index.html", "/index.php")


def guess_year() -> int:
    """Get target conference year (current if before July, else next).

    :return: Target year
    """
    now = datetime.date.today()
    return now.year if now.month <= 6 else now.year + 1


def guess_role_from_keywords(matched_keywords: list[str]) -> str:
    """Guess role from matched keywords.

    :param matched_keywords: List of matched keyword strings
    :return: Guessed role (Reviewer, PC, AC, etc.)
    """
    content = " ".join(matched_keywords).lower()

    # Check in priority order
    for pattern, role in constants.ROLE_GUESSES:
        if pattern.lower() in content:
            return role

    return "Reviewer"  # Default


def load_current_urls(calls_path: str) -> set[str]:
    """Read calls.yaml and return a set of normalized URLs.

    :param calls_path: Path to calls.yaml file
    :return: Set of normalized URLs
    """
    from discover.data import load_calls, extract_normalized_urls_from_calls

    return extract_normalized_urls_from_calls(load_calls(calls_path))


def normalize_url(url: str) -> str:
    """Normalize URL for comparison.

    Strips trailing slash and fragment, converts to lowercase, removes www. prefix,
    removes tracking parameters, and removes index.html/index.php suffixes.

    :param url: Raw URL string
    :return: Normalized URL (lowercase, no trailing slash/fragment, no www)
    """
    url = url.rstrip("/").split("#", 1)[0].lower()

    # Remove www. prefix from domain
    parsed = urlparse(url)
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
        url = url.replace(f"://{parsed.netloc}", f"://{netloc}", 1)

    # Remove tracking query parameters
    parsed = urlparse(url)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items() if k not in _TRACKING_PARAMS}
        if cleaned:
            new_query = urlencode(cleaned, doseq=True)
            url = url.split("?", 1)[0] + "?" + new_query
        else:
            url = url.split("?", 1)[0]

    # Remove index.html / index.php suffixes
    for suffix in _INDEX_SUFFIXES:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break

    return url.rstrip("/")


def is_same_domain(url: str, domain: str) -> bool:
    """Check if URL belongs to the given domain.

    Handles subdomains correctly (e.g., 2026.aaai.org matches aaai.org).

    :param url: Full URL to check
    :param domain: Base domain (e.g., 'aaai.org')
    :return: True if URL's domain matches or is subdomain of given domain
    """
    parsed = urlparse(url)
    url_domain = parsed.netloc.lower()
    domain_lower = domain.lower()
    return url_domain == domain_lower or url_domain.endswith("." + domain_lower)


def extract_visible_text(html: str) -> str:
    """Extract visible text from HTML, stripping script/style/tags.

    Uses only stdlib (re, html.unescape). Returns lowercase text with
    collapsed whitespace, suitable for keyword matching.

    :param html: Raw HTML string
    :return: Lowercase visible text
    """
    text = _RE_SCRIPT_STYLE.sub(" ", html)
    text = _RE_HTML_COMMENTS.sub(" ", text)
    text = _RE_ALL_TAGS.sub(" ", text)
    text = html_lib.unescape(text)
    text = _RE_WHITESPACE.sub(" ", text)
    return text.lower().strip()
