"""Content validation functions for reviewer call detection."""

from __future__ import annotations

import datetime
from typing import Any

import requests
from discover.constants import (
    STEP4_CONTENT_KEYWORDS,
    KEYWORD_PATTERNS,
    USELESS_EXTENSIONS,
    USELESS_URL_PATTERNS,
    NEVER_REVIEWER_CALL_PATHS,
    COMMITTEE_LISTING_PATTERNS,
    RECRUITMENT_TERMS_FOR_COMMITTEE,
    TRACK_EXCEPTIONS,
    CALL_FOR_PAPER_PATTERNS,
    REVIEWER_CONTEXT_TERMS_FOR_CFP,
    GENERIC_HOMEPAGE_PATTERNS,
    FALSE_POSITIVE_PATHS,
    NEGATIVE_SIGNALS,
    REVIEWER_RECOVERY_TERMS,
    HIGH_CONFIDENCE_SIGNALS,
    MEDIUM_CONFIDENCE_SIGNALS,
    YEAR_FILTER_START,
)
from discover.scoring import score_content_signals as _score_content_signals
from discover.utils import extract_visible_text


def is_obviously_useless(url: str) -> bool:
    """Check if URL is obviously not a reviewer call page.

    :param url: URL to check
    :return: True if URL should be filtered out
    """
    url_lower = url.lower()

    if any(url_lower.endswith(ext) for ext in USELESS_EXTENSIONS):
        return True

    if any(pattern in url_lower for pattern in USELESS_URL_PATTERNS):
        return True

    for pattern in NEVER_REVIEWER_CALL_PATHS:
        if pattern in url_lower:
            promising_keywords = [
                "call",
                "reviewer",
                "review",
                "pc",
                "committee",
                "nomination",
                "recruitment",
                "member",
                "chair",
            ]
            if not any(kw in url_lower for kw in promising_keywords):
                return True

    return False


def is_false_positive_url(url: str) -> bool:
    """Check if URL matches known false positive patterns.

    :param url: URL to check
    :return: True if URL is likely a false positive
    """
    url_lower = url.lower()

    has_recruitment_terms = any(
        term in url_lower for term in RECRUITMENT_TERMS_FOR_COMMITTEE
    )
    if not has_recruitment_terms:
        for pattern in COMMITTEE_LISTING_PATTERNS:
            if pattern in url_lower:
                return True

    if "/track/" in url_lower and "/call" not in url_lower:
        if not any(exc in url_lower for exc in TRACK_EXCEPTIONS):
            return True

    if "/details/" in url_lower:
        url_parts = url_lower.split("/")
        if len(url_parts) >= 6:
            return True

    has_reviewer_context = any(
        term in url_lower for term in REVIEWER_CONTEXT_TERMS_FOR_CFP
    )
    if not has_reviewer_context:
        for pattern in CALL_FOR_PAPER_PATTERNS:
            if pattern in url_lower:
                return True

    for pattern in GENERIC_HOMEPAGE_PATTERNS:
        if url_lower.endswith(pattern) or url_lower.endswith(pattern + "/"):
            return True

    if (
        url_lower.endswith(".org")
        or url_lower.endswith(".org/")
        or url_lower.endswith(".com")
        or url_lower.endswith(".com/")
    ):
        return True

    if (
        url_lower.endswith("/2024")
        or url_lower.endswith("/2025")
        or url_lower.endswith("/2026")
        or url_lower.endswith("/2027")
    ):
        return True

    if url_lower.endswith("/pc.html") or url_lower.endswith("/committee.html"):
        return True

    if "principles" in url_lower or "policy" in url_lower or "guidelines" in url_lower:
        if not has_recruitment_terms:
            return True

    if "/registration" in url_lower or "/attending/" in url_lower:
        return True

    if "/program/" in url_lower and "program-committee" not in url_lower:
        return True

    for path in FALSE_POSITIVE_PATHS:
        if path in url_lower and "reviewer" not in url_lower and "pc" not in url_lower:
            return True

    current_year = datetime.date.today().year

    for year in range(YEAR_FILTER_START, current_year - 1):
        if (
            f"/{year}/" in url_lower
            or f"-{year}/" in url_lower
            or f"-{year}-" in url_lower
        ):
            return True

    return False


def has_positive_signals(
    content: str, *, explain: bool = False
) -> bool | tuple[bool, dict[str, str]]:
    """Check if content has positive signals for reviewer recruitment.

    :param content: Page content (lowercase text)
    :param explain: If True, return (bool, explanation_dict) instead of just bool
    :return: True if positive recruitment signals found (or tuple if explain=True)
    """
    for signal in NEGATIVE_SIGNALS:
        if signal in content:
            if not any(term in content for term in REVIEWER_RECOVERY_TERMS):
                if explain:
                    return False, {"reason": "negative_signal", "signal": signal}
                return False

    for signal in HIGH_CONFIDENCE_SIGNALS:
        if signal in content:
            if explain:
                return True, {"reason": "high_confidence", "signal": signal}
            return True

    for signal, context_terms in MEDIUM_CONFIDENCE_SIGNALS:
        if signal in content:
            pos = content.find(signal)
            window = content[max(0, pos - 200) : pos + 200]
            if any(term in window for term in context_terms):
                if explain:
                    return True, {"reason": "medium_confidence", "signal": signal}
                return True

    if explain:
        return False, {"reason": "no_signals", "signal": ""}
    return False


def check_page_content(url: str) -> dict[str, Any] | None:
    """Check if page contains reviewer call keywords with strict validation.

    :param url: URL to check
    :return: Match dict if legitimate reviewer call found, None otherwise
    """
    if is_false_positive_url(url):
        return None

    from discover import http

    try:
        resp = http.get(url)
        if resp.status_code != 200:
            return None

        html = resp.content.decode("utf-8", errors="replace")
        content = extract_visible_text(html)

        if not has_positive_signals(content):
            return None

        matched_indices = []
        matched_keywords = []
        for i, pattern in enumerate(KEYWORD_PATTERNS):
            if pattern.search(content):
                matched_indices.append(i)
                matched_keywords.append(STEP4_CONTENT_KEYWORDS[i])

        if matched_indices:
            signal_score, _ = _score_content_signals(content)
            from discover import config as _cfg

            keyword_score = len(matched_indices) * _cfg.CONTENT_WEAK_POSITIVE
            return {
                "url": resp.url,
                "matched_keyword_indices": matched_indices,
                "matched_keywords": matched_keywords[:5],
                "has_reviewer_call": True,
                "content_score": signal_score + keyword_score,
            }

        return None

    except requests.RequestException:
        return None
