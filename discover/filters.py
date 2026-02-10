"""Link filtering and keyword matching utilities."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from discover.constants import (
    STEP2_PROMISING_KEYWORDS,
    STEP2_LINK_FILTER_KEYWORDS,
    STEP2_STOP_WORDS,
    SKIP_KEYWORDS,
)
from discover import validators as _validators
from discover.utils import is_same_domain


def has_promising_keywords(text: str) -> bool:
    """Check if text contains promising keywords for reviewer calls.

    :param text: Text to check
    :return: True if contains promising keywords
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in STEP2_PROMISING_KEYWORDS)


def should_skip_link_text(text: str) -> bool:
    """Check if link text suggests a non-reviewer page.

    :param text: Link text (visible text of <a> tag)
    :return: True if text suggests we should skip this link
    """
    text_lower = text.lower()

    for keyword in SKIP_KEYWORDS:
        if (
            text_lower == keyword
            or text_lower.startswith(keyword + " ")
            or text_lower.endswith(" " + keyword)
        ):
            if has_promising_keywords(text):
                return False
            return True

    return False


def has_filter_keyword(text: str) -> bool:
    """Check if text contains any filter keyword.

    :param text: Text to check
    :return: True if contains filter keyword
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in STEP2_LINK_FILTER_KEYWORDS)


def has_stop_word(text: str) -> bool:
    """Check if text contains stop-words without reviewer keywords.

    :param text: Text to check
    :return: True if has stop-word and no reviewer keywords
    """
    text_lower = text.lower()

    reviewer_keywords = ["reviewer", "pc", "committee", "nomination", "call"]
    if any(kw in text_lower for kw in reviewer_keywords):
        return False

    return any(word in text_lower for word in STEP2_STOP_WORDS)


def should_explore_link(link: dict[str, str]) -> bool:
    """Decide if link should be explored based on keywords.

    :param link: Dict with 'url' and 'text' keys
    :return: True if link should be explored
    """
    url = link.get("url", "")
    text = link.get("text", "")
    path = urlparse(url).path

    if has_filter_keyword(path) or has_filter_keyword(text):
        if has_stop_word(path):
            return False
        return True

    return False


@dataclass
class LinkFilterOptions:
    """Configuration for link filtering."""

    base_domain: str
    conference_name: str = ""
    filter_useless: bool = True
    filter_by_text: bool = True
    filter_by_domain: bool = True


def is_trusted_external_platform(url: str, conference_name: str) -> bool:
    """Check if URL is from a trusted external platform.

    :param url: URL to check
    :param conference_name: Conference short name for context
    :return: True if trusted external platform
    """
    url_lower = url.lower()
    conf_lower = conference_name.lower()

    import datetime

    current_year = datetime.date.today().year
    recent_years = [str(y) for y in range(current_year - 1, current_year + 2)]

    if ".github.io" in url_lower:
        if conf_lower in url_lower:
            return True
        workshop_patterns = ["workshop", "ws"]
        conf_patterns = [
            f"-{c.lower()}"
            for c in [
                "iclr",
                "icml",
                "neurips",
                "cvpr",
                "iccv",
                "aaai",
                "acl",
                "emnlp",
                "naacl",
                "eacl",
            ]
        ]
        year_patterns = [f"-{y}" for y in recent_years] + [
            f"iclr{y}" for y in recent_years
        ]
        topic_patterns = ["-ai", "science", "agent", "learning", "foundation", "model"]
        all_patterns = (
            workshop_patterns + conf_patterns + year_patterns + topic_patterns
        )
        return any(pattern in url_lower for pattern in all_patterns)

    if "sites.google.com" in url_lower:
        if conf_lower in url_lower:
            return True
        return any(year in url_lower for year in recent_years)

    if "conf.researchr.org" in url_lower:
        return True

    if "forum.cspaper.org" in url_lower:
        return conf_lower in url_lower or "cvpr" in url_lower or "iccv" in url_lower

    return False


def filter_links(
    links: list[dict[str, str]], options: LinkFilterOptions
) -> list[dict[str, str]]:
    """Filter links by domain, text, and useless patterns.

    :param links: List of dicts with 'url' and 'text' keys
    :param options: Filtering configuration
    :return: Filtered list of links
    """
    filtered = []
    for link in links:
        if options.filter_by_domain:
            if not is_same_domain(link["url"], options.base_domain):
                if not is_trusted_external_platform(
                    link["url"], options.conference_name
                ):
                    continue

        if options.filter_useless:
            if _validators.is_obviously_useless(link["url"]):
                continue

        if options.filter_by_text and link["text"]:
            if should_skip_link_text(link["text"]):
                continue

        filtered.append(link)

    return filtered
