"""Helper utilities and URL functions."""

from __future__ import annotations

import datetime

from urllib.parse import urlparse

from discover import constants


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

    Strips trailing slash and fragment, converts to lowercase, removes www. prefix.

    :param url: Raw URL string
    :return: Normalized URL (lowercase, no trailing slash/fragment, no www)
    """
    url = url.rstrip("/").split("#", 1)[0].lower()

    # Remove www. prefix from domain
    parsed = urlparse(url)
    if parsed.netloc.startswith("www."):
        netloc_without_www = parsed.netloc[4:]  # Remove 'www.'
        url = url.replace(f"://{parsed.netloc}", f"://{netloc_without_www}", 1)

    return url


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
