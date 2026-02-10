"""Async batch processing utilities for parallel HTTP requests."""

from __future__ import annotations

import asyncio
from typing import Any
import aiohttp
from discover.parsers import LinkExtractor
from discover.filters import filter_links, LinkFilterOptions
from discover import config, constants
from discover import validators


async def async_fetch_page(
    session: aiohttp.ClientSession, url: str, timeout: int = 10
) -> tuple[str, str | None]:
    """Async fetch a single page.

    :param session: aiohttp session
    :param url: URL to fetch
    :param timeout: Timeout in seconds
    :return: Tuple of (url, html_content or None)
    """
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True
        ) as resp:
            if resp.status == 200:
                return (url, await resp.text())
            return (url, None)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return (url, None)


async def async_extract_links_batch(
    urls: list[str],
    base_domain: str,
    conference_name: str = "",
    concurrency: int | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Extract links from multiple pages in parallel.

    :param urls: List of URLs to fetch
    :param base_domain: Conference domain to filter by
    :param conference_name: Conference short name (for external platform whitelisting)
    :param concurrency: Max concurrent requests (defaults to config.CONCURRENT_REQUESTS)
    :return: Dict mapping URL to list of extracted links
    """
    if concurrency is None:
        concurrency = config.CONCURRENT_REQUESTS

    connector = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=config.HOMEPAGE_TIMEOUT)

    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout, headers={"User-Agent": config.USER_AGENT}
    ) as session:
        tasks = [async_fetch_page(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    url_to_links = {}
    filter_options = LinkFilterOptions(
        base_domain=base_domain,
        conference_name=conference_name,
        filter_useless=True,
        filter_by_text=True,
        filter_by_domain=True,
    )

    for url, html in results:
        if html is None:
            url_to_links[url] = []
            continue

        try:
            parser = LinkExtractor(url)
            parser.feed(html)

            filtered = filter_links(parser.links, filter_options)
            url_to_links[url] = filtered
        except (ValueError, UnicodeDecodeError):
            url_to_links[url] = []

    return url_to_links


async def async_check_content_batch(
    urls: list[str], concurrency: int | None = None
) -> dict[str, dict[str, Any] | None]:
    """Async check page content for multiple URLs in parallel with strict validation.

    :param urls: List of URLs to check
    :param concurrency: Max concurrent requests (defaults to config.CONCURRENT_REQUESTS)
    :return: Dict mapping URL to match dict or None
    """
    if concurrency is None:
        concurrency = config.CONCURRENT_REQUESTS

    filtered_urls = []
    excluded_urls = []
    for url in urls:
        if validators.is_false_positive_url(url):
            excluded_urls.append(url)
        else:
            filtered_urls.append(url)

    url_to_match: dict[str, dict[str, Any] | None] = {
        url: None for url in excluded_urls
    }

    if excluded_urls:
        print(f"    Pre-filtered {len(excluded_urls)} false positive URLs:")
        for url in excluded_urls[:3]:
            print(f"      - {url[:80]}...")

    if not filtered_urls:
        return url_to_match

    connector = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=config.HOMEPAGE_TIMEOUT)

    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout, headers={"User-Agent": config.USER_AGENT}
    ) as session:
        tasks = [async_fetch_page(session, url) for url in filtered_urls]
        results = await asyncio.gather(*tasks)

    failed_fetch = 0
    failed_positive_signals = 0
    failed_keywords = 0

    for url, html in results:
        if html is None:
            url_to_match[url] = None
            failed_fetch += 1
            continue

        try:
            text_lower = html.lower()

            if not validators.has_positive_signals(text_lower):
                url_to_match[url] = None
                failed_positive_signals += 1
                continue

            matched_indices = []
            matched_keywords = []

            for i, pattern in enumerate(constants.KEYWORD_PATTERNS):
                if pattern.search(text_lower):
                    matched_indices.append(i)
                    matched_keywords.append(constants.STEP4_CONTENT_KEYWORDS[i])

            if matched_indices:
                url_to_match[url] = {
                    "url": url,
                    "matched_keyword_indices": matched_indices,
                    "matched_keywords": matched_keywords,
                }
            else:
                url_to_match[url] = None
                failed_keywords += 1
        except (ValueError, UnicodeDecodeError):
            url_to_match[url] = None
            failed_fetch += 1

    if failed_fetch + failed_positive_signals + failed_keywords > 0:
        print(
            f"    Validation failures: {failed_fetch} fetch, {failed_positive_signals} signals, {failed_keywords} keywords"
        )

    return url_to_match
