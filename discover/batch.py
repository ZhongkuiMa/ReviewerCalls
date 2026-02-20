"""Async batch processing utilities for parallel HTTP requests."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
import aiohttp
from discover.parsers import LinkExtractor
from discover.filters import filter_links, LinkFilterOptions
from discover import config, constants
from discover import validators
from discover.scoring import score_content_signals
from discover.utils import extract_visible_text

logger = logging.getLogger(__name__)


class AsyncFetcher:
    """Managed async HTTP fetcher with single session, retry, and content guards.

    Usage::

        async with AsyncFetcher() as fetcher:
            url, html = await fetcher.fetch("https://example.com")
    """

    def __init__(
        self,
        concurrency: int | None = None,
        timeout_total: int | None = None,
        timeout_connect: int | None = None,
    ):
        self._concurrency = concurrency or config.CONCURRENT_REQUESTS
        self._timeout_total = timeout_total or config.TIMEOUT_TOTAL
        self._timeout_connect = timeout_connect or config.TIMEOUT_CONNECT
        self._session: aiohttp.ClientSession | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self.seen_final_urls: set[str] = set()

    async def __aenter__(self) -> AsyncFetcher:
        timeout = aiohttp.ClientTimeout(
            total=self._timeout_total,
            connect=self._timeout_connect,
        )
        connector = aiohttp.TCPConnector(limit=self._concurrency)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": config.USER_AGENT},
        )
        self._semaphore = asyncio.Semaphore(self._concurrency)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def fetch(self, url: str) -> tuple[str, str | None]:
        """Fetch a URL with retry, content-type guard, and size guard.

        :param url: URL to fetch
        :return: Tuple of (url, html_content or None)
        """
        assert self._session is not None, "Use AsyncFetcher as context manager"
        assert self._semaphore is not None

        async with self._semaphore:
            return await self._fetch_with_retry(url)

    async def _fetch_with_retry(self, url: str) -> tuple[str, str | None]:
        """Fetch with retry logic.

        :param url: URL to fetch
        :return: Tuple of (url, html or None)
        """
        assert self._session is not None

        last_exc: Exception | None = None
        for attempt in range(config.RETRY_MAX_ATTEMPTS):
            try:
                async with self._session.get(url, allow_redirects=True) as resp:
                    # Track redirect final URL
                    final_url = str(resp.url)
                    self.seen_final_urls.add(final_url)

                    # 429 Too Many Requests: respect Retry-After
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        wait = (
                            float(retry_after)
                            if retry_after
                            else config.RETRY_429_BACKOFF
                        )
                        logger.debug(
                            "429 for %s, waiting %.1fs (attempt %d)",
                            url[:80],
                            wait,
                            attempt + 1,
                        )
                        await asyncio.sleep(wait)
                        continue

                    # 5xx: retry with backoff
                    if resp.status >= 500:
                        wait = config.RETRY_BACKOFF_BASE * (2**attempt)
                        logger.debug(
                            "%d for %s, retrying in %.1fs (attempt %d)",
                            resp.status,
                            url[:80],
                            wait,
                            attempt + 1,
                        )
                        await asyncio.sleep(wait)
                        continue

                    # 4xx (not 429): skip
                    if resp.status >= 400:
                        return (url, None)

                    # Non-200 success codes: skip
                    if resp.status != 200:
                        return (url, None)

                    # Content-Type guard
                    content_type = resp.content_type or ""
                    if (
                        content_type
                        and content_type not in config.ALLOWED_CONTENT_TYPES
                    ):
                        logger.debug(
                            "Skipped %s: content-type %s", url[:80], content_type
                        )
                        return (url, None)

                    # Size guard: check Content-Length before reading
                    content_length = resp.headers.get("Content-Length")
                    if (
                        content_length
                        and int(content_length) > config.MAX_RESPONSE_BYTES
                    ):
                        logger.debug(
                            "Skipped %s: too large (%s bytes)",
                            url[:80],
                            content_length,
                        )
                        return (url, None)

                    raw = await resp.read()

                    # Size guard: actual read size
                    if len(raw) > config.MAX_RESPONSE_BYTES:
                        logger.debug(
                            "Skipped %s: body too large (%d bytes)",
                            url[:80],
                            len(raw),
                        )
                        return (url, None)

                    return (url, raw.decode("utf-8", errors="replace"))

            except asyncio.TimeoutError:
                wait = config.RETRY_BACKOFF_BASE * (2**attempt)
                logger.debug(
                    "Timeout for %s (attempt %d), retrying in %.1fs",
                    url[:80],
                    attempt + 1,
                    wait,
                )
                last_exc = asyncio.TimeoutError()
                if attempt < config.RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(wait)
            except aiohttp.ClientError as e:
                last_exc = e
                break  # Client errors are not retryable

        if last_exc:
            logger.debug("Failed to fetch %s: %s", url[:80], last_exc)
        return (url, None)

    async def fetch_many(self, urls: list[str]) -> list[tuple[str, str | None]]:
        """Fetch multiple URLs concurrently.

        :param urls: List of URLs to fetch
        :return: List of (url, html_content or None)
        """
        tasks = [self.fetch(url) for url in urls]
        return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Backwards-compatible free functions that create a temporary fetcher
# ---------------------------------------------------------------------------


async def async_fetch_page(
    session: aiohttp.ClientSession, url: str, timeout: int = 10
) -> tuple[str, str | None]:
    """Async fetch a single page (legacy interface).

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
                raw = await resp.read()
                return (url, raw.decode("utf-8", errors="replace"))
            return (url, None)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return (url, None)


async def async_extract_links_batch(
    urls: list[str],
    base_domain: str,
    conference_name: str = "",
    fetcher: AsyncFetcher | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Extract links from multiple pages in parallel.

    :param urls: List of URLs to fetch
    :param base_domain: Conference domain to filter by
    :param conference_name: Conference short name (for external platform whitelisting)
    :param fetcher: Optional AsyncFetcher instance (creates temp one if None)
    :return: Dict mapping URL to list of extracted links
    """
    if fetcher is not None:
        results = await fetcher.fetch_many(urls)
    else:
        # Legacy path: create temporary session
        connector = aiohttp.TCPConnector(limit=config.CONCURRENT_REQUESTS)
        timeout = aiohttp.ClientTimeout(total=config.HOMEPAGE_TIMEOUT)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": config.USER_AGENT},
        ) as session:
            tasks = [async_fetch_page(session, url) for url in urls]
            results = await asyncio.gather(*tasks)

    url_to_links: dict[str, list[dict[str, str]]] = {}
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
    urls: list[str],
    fetcher: AsyncFetcher | None = None,
) -> dict[str, dict[str, Any] | None]:
    """Async check page content for multiple URLs in parallel with strict validation.

    :param urls: List of URLs to check
    :param fetcher: Optional AsyncFetcher instance (creates temp one if None)
    :return: Dict mapping URL to match dict or None
    """
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
        logger.info("    Pre-filtered %d false positive URLs", len(excluded_urls))
        for url in excluded_urls[:3]:
            logger.debug("      - %s", url[:80])

    if not filtered_urls:
        return url_to_match

    if fetcher is not None:
        results = await fetcher.fetch_many(filtered_urls)
    else:
        # Legacy path: create temporary session
        connector = aiohttp.TCPConnector(limit=config.CONCURRENT_REQUESTS)
        timeout = aiohttp.ClientTimeout(total=config.HOMEPAGE_TIMEOUT)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": config.USER_AGENT},
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
            visible_text = extract_visible_text(html)

            # Cheap precheck: skip expensive regex if no root terms present
            if not any(root in visible_text for root in constants.PRECHECK_ROOTS):
                url_to_match[url] = None
                failed_keywords += 1
                continue

            if not validators.has_positive_signals(visible_text):
                url_to_match[url] = None
                failed_positive_signals += 1
                continue

            matched_indices = []
            matched_keywords = []

            for i, pattern in enumerate(constants.KEYWORD_PATTERNS):
                if pattern.search(visible_text):
                    matched_indices.append(i)
                    matched_keywords.append(constants.STEP4_CONTENT_KEYWORDS[i])

            if matched_indices:
                # Content scoring: signal score + keyword score
                signal_score, signal_evidence = score_content_signals(visible_text)
                keyword_score = len(matched_indices) * config.CONTENT_WEAK_POSITIVE
                total_content_score = signal_score + keyword_score

                # Match strength: derive from content_score for backwards compat
                if total_content_score >= 10:
                    strength = "high"
                elif total_content_score >= 4:
                    strength = "medium"
                else:
                    strength = "low"

                # Evidence snippet: 160 chars around first match
                evidence = ""
                first_kw = matched_keywords[0]
                kw_pos = visible_text.find(first_kw.lower())
                if kw_pos >= 0:
                    start = max(0, kw_pos - 60)
                    end = min(len(visible_text), kw_pos + 100)
                    evidence = visible_text[start:end].strip()
                    if start > 0:
                        evidence = "..." + evidence
                    if end < len(visible_text):
                        evidence = evidence + "..."

                logger.debug(
                    "    Content score %.1f for %s (%d keywords, %.1f signals)",
                    total_content_score,
                    url[:80],
                    len(matched_indices),
                    signal_score,
                )

                url_to_match[url] = {
                    "url": url,
                    "matched_keyword_indices": matched_indices,
                    "matched_keywords": matched_keywords,
                    "match_strength": strength,
                    "evidence_snippet": evidence,
                    "content_score": total_content_score,
                }
            else:
                url_to_match[url] = None
                failed_keywords += 1
        except (ValueError, UnicodeDecodeError):
            url_to_match[url] = None
            failed_fetch += 1

    if failed_fetch + failed_positive_signals + failed_keywords > 0:
        logger.debug(
            "    Validation failures: %d fetch, %d signals, %d keywords",
            failed_fetch,
            failed_positive_signals,
            failed_keywords,
        )

    return url_to_match
