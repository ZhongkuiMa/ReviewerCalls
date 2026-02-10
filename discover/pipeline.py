"""Discovery pipeline step implementations."""

from __future__ import annotations

import asyncio
from typing import Any

import requests
from urllib.parse import urlparse
from discover.parsers import LinkExtractor, extract_page_date
from discover.filters import (
    filter_links,
    LinkFilterOptions,
    has_promising_keywords,
    should_explore_link,
)
from discover.batch import async_extract_links_batch, async_check_content_batch
from discover.utils import guess_role_from_keywords, normalize_url, is_same_domain
from discover import http
from discover.search import search


def detect_url_label(url: str, matched_keywords: list[str]) -> str:
    """Detect label for URL (Workshop, Main, Industry, etc.).

    :param url: URL to analyze
    :param matched_keywords: Keywords that matched on the page
    :return: Label string or empty string
    """
    url_lower = url.lower()
    keywords_str = " ".join(matched_keywords).lower()

    workshop_indicators = [
        "workshop",
        "-ws-",
        "github.io",
        "sites.google.com",
        "/workshops/",
        "/accepted-workshops/",
    ]
    if any(indicator in url_lower for indicator in workshop_indicators):
        return "Workshop"
    if "workshop" in keywords_str:
        return "Workshop"

    industry_indicators = ["industry", "industrial"]
    if any(indicator in url_lower for indicator in industry_indicators):
        return "Industry"
    if any(indicator in keywords_str for indicator in industry_indicators):
        return "Industry"

    if "shadow" in url_lower or "junior" in url_lower:
        return "Shadow/Junior"
    if "shadow" in keywords_str or "junior" in keywords_str:
        return "Shadow/Junior"

    return "Main"


def _build_search_queries(conf: dict[str, Any], year: int) -> tuple[str, str]:
    """Build main and reviewer-specific search queries.

    :param conf: Conference dictionary
    :param year: Target year
    :return: Tuple of (main_query, reviewer_query)
    """
    main_query = f'"{conf["short"]}" "{year}" conference'
    reviewer_query = f'"{conf["short"]}" "{year}" reviewer'
    return main_query, reviewer_query


def _validate_and_score_results(
    results: list[dict[str, str]], conf: dict[str, Any], year: int
) -> list[dict[str, Any]]:
    """Validate and score search results to find homepage candidates.

    :param results: Raw search results
    :param conf: Conference dictionary
    :param year: Target year
    :return: Scored candidate list
    """
    candidates = []
    for result in results:
        score = _score_conference_page(result, conf, year)
        if score > 0:
            parsed = urlparse(result["url"])
            path_depth = len([p for p in parsed.path.strip("/").split("/") if p])
            candidates.append(
                {
                    "url": result["url"],
                    "depth": path_depth,
                    "score": score,
                    "title": result.get("title", ""),
                }
            )
    return candidates


def _select_best_homepage(candidates: list[dict[str, Any]]) -> str:
    """Select best homepage from scored candidates.

    :param candidates: List of scored candidates
    :return: Best homepage URL
    """
    candidates.sort(key=lambda x: (-x["score"], x["depth"]))
    return candidates[0]["url"]


def _filter_reviewer_results(
    reviewer_results: list[dict[str, str]],
    homepage_url: str,
) -> list[dict[str, str]]:
    """Filter reviewer search results by domain.

    :param reviewer_results: Raw reviewer search results
    :param homepage_url: Homepage URL to filter by
    :return: Filtered list of reviewer links
    """
    reviewer_links = []
    homepage_domain = urlparse(homepage_url).netloc
    for result in reviewer_results:
        result_domain = urlparse(result["url"]).netloc
        if result_domain != homepage_domain:
            reviewer_links.append(
                {
                    "url": result["url"],
                    "text": result.get("title", ""),
                    "from_reviewer_search": True,
                }
            )
    return reviewer_links


def step1_search_homepage(
    conf: dict[str, Any],
    year: int,
    search_provider: str = "duckduckgo",
    serper_key: str = "",
    date_range: str = "m",
) -> tuple[str | None, list[dict[str, str]]]:
    """Step 1: Use DDG to find conference homepage and reviewer pages.

    :param conf: Conference dictionary
    :param year: Target year
    :param search_provider: Search provider ('duckduckgo' or 'serper')
    :param serper_key: API key for Serper provider
    :param date_range: Date range filter ('d', 'w', 'm', 'y', or None)
    :return: Tuple of (homepage URL or None, list of reviewer-specific search results)
    """
    main_query, reviewer_query = _build_search_queries(conf, year)
    print(f"  [1/4] Search: {main_query}")

    search_kwargs = dict(
        provider=search_provider,
        serper_key=serper_key,
        date_range=date_range,
    )
    results = search(main_query, max_results=10, **search_kwargs)
    reviewer_results = search(reviewer_query, max_results=10, **search_kwargs)

    if not results:
        print("    No search results - conference may not be recruiting yet")
        return None, []

    candidates = _validate_and_score_results(results, conf, year)

    if not candidates:
        print(
            f"    No validated results in {len(results)} results - skipping conference"
        )
        return None, []

    homepage = _select_best_homepage(candidates)
    print(
        f"    Homepage: {homepage} (score: {candidates[0]['score']}, {len(candidates)} candidates)"
    )

    reviewer_links = _filter_reviewer_results(reviewer_results, homepage)

    if reviewer_links:
        print(f"    Additional reviewer-specific results: {len(reviewer_links)}")

    return homepage, reviewer_links


def _score_conference_page(
    result: dict[str, str], conf: dict[str, Any], year: int
) -> int:
    """Score a search result to determine if it's the conference page.

    :param result: Search result with 'url', 'title', 'snippet'
    :param conf: Conference dictionary
    :param year: Target year
    :return: Score (0 = not a match, higher = better match)
    """
    score = 0
    url_lower = result["url"].lower()
    title_lower = result.get("title", "").lower()
    snippet_lower = result.get("snippet", "").lower()

    conf_abbr = conf["short"].lower()
    conf_name = conf["name"].lower()
    year_str = str(year)

    if conf_abbr in url_lower:
        score += 10

    if is_same_domain(result["url"], conf["domain"]):
        score += 5

    if conf_abbr in title_lower or conf_abbr in snippet_lower:
        score += 3

    if conf_name in title_lower or conf_name in snippet_lower:
        score += 2

    if year_str in title_lower or year_str in snippet_lower:
        score += 2

    return score


def _explore_links_batch(
    links_to_explore: list[dict[str, str]],
    domain: str,
    conference_name: str = "",
    prioritize_by_keywords: bool = True,
) -> list[dict[str, str]]:
    """Extract and deduplicate links from multiple pages (async batch).

    :param links_to_explore: List of links to fetch and extract from
    :param domain: Conference domain for filtering
    :param conference_name: Conference short name
    :param prioritize_by_keywords: If True, sort by promising keywords
    :return: Deduplicated list of links
    """
    urls_to_fetch = [link["url"] for link in links_to_explore]

    url_to_links = asyncio.run(
        async_extract_links_batch(urls_to_fetch, domain, conference_name)
    )

    collected_links = []
    seen_urls = set()

    for url in urls_to_fetch:
        for new_link in url_to_links.get(url, []):
            if new_link["url"] not in seen_urls:
                collected_links.append(new_link)
                seen_urls.add(new_link["url"])

    if prioritize_by_keywords:
        promising = [
            link for link in collected_links if has_promising_keywords(link["text"])
        ]
        other = [
            link for link in collected_links if not has_promising_keywords(link["text"])
        ]
        collected_links = promising + other

    return collected_links


def step2_explore_level1(
    homepage: str, domain: str, conference_name: str = "", max_links: int = 15
) -> list[dict[str, str]]:
    """Step 2: Dynamic link discovery via keyword filtering.

    :param homepage: Conference homepage URL
    :param domain: Conference domain
    :param conference_name: Conference short name
    :param max_links: Maximum links to explore (default: 15)
    :return: List of level 2 links with text
    """
    print("  [2/4] Dynamic link discovery from homepage")

    try:
        resp = http.get(homepage)
        if resp.status_code != 200:
            print("    Failed to fetch homepage")
            return []

        parser = LinkExtractor(resp.url)
        parser.feed(resp.text)

        filter_options = LinkFilterOptions(
            base_domain=domain,
            conference_name=conference_name,
            filter_useless=True,
            filter_by_text=False,
            filter_by_domain=False,
        )
        all_links = filter_links(parser.links, filter_options)

    except requests.RequestException as e:
        print(f"    Error extracting links: {e}")
        return []

    print(f"    Extracted {len(all_links)} links from homepage")

    keyword_links = [link for link in all_links if should_explore_link(link)]

    keyword_links = keyword_links[:max_links]

    print(
        f"    Filtered {len(all_links)} links -> {len(keyword_links)} with keywords (max={max_links})"
    )

    if not keyword_links:
        print("    No links match keywords")
        return []

    level2_links = _explore_links_batch(
        keyword_links, domain, conference_name, prioritize_by_keywords=True
    )

    promising = [link for link in level2_links if has_promising_keywords(link["text"])]

    print(f"    Level 2 links: {len(level2_links)} total ({len(promising)} promising)")
    return level2_links


def step3_explore_level2(
    level2_links: list[dict[str, str]], domain: str, conference_name: str = ""
) -> list[dict[str, str]]:
    """Step 3: Explore level 2 pages, collect level 3 URLs.

    :param level2_links: List of level 2 links with text
    :param domain: Conference domain
    :param conference_name: Conference short name
    :return: List of level 3 links with text
    """
    promising_links = [
        link for link in level2_links if has_promising_keywords(link["text"])
    ]

    if not promising_links:
        print(
            f"  [3/4] No promising L2 pages to explore (filtered from {len(level2_links)})"
        )
        return []

    print(
        f"  [3/4] Extract links from {len(promising_links)} promising L2 pages (filtered from {len(level2_links)} total)"
    )

    level3_links = _explore_links_batch(
        promising_links, domain, conference_name, prioritize_by_keywords=False
    )

    print(f"    Level 3 links: {len(level3_links)}")
    return level3_links


def _filter_promising_links(all_links: list[dict[str, str]]) -> list[dict[str, str]]:
    """Filter to promising links based on link text.

    :param all_links: All links
    :return: Filtered promising links
    """
    return [
        link
        for link in all_links
        if has_promising_keywords(link["text"])
        or link.get("from_reviewer_search", False)
    ]


def _filter_known_urls(
    promising_links: list[dict[str, str]], known_urls: set[str]
) -> tuple[list[dict[str, str]], int]:
    """Filter out known URLs from promising links.

    :param promising_links: List of promising links
    :param known_urls: Set of known URLs to filter
    :return: Tuple of (new_links, skipped_count)
    """
    to_check = []
    skipped = 0
    for link in promising_links:
        if normalize_url(link["url"]) in known_urls:
            print(f"      Skipping known URL: {link['url'][:100]}...")
            skipped += 1
        else:
            to_check.append(link)
    return to_check, skipped


def _enrich_matches(
    url_to_match: dict[str, Any],
    conf: dict[str, Any],
    year: int,
) -> list[dict[str, Any]]:
    """Enrich matched URLs with metadata and build candidates.

    :param url_to_match: Dict mapping URLs to match dicts
    :param conf: Conference dictionary
    :param year: Target year
    :return: List of enriched candidate dictionaries
    """
    candidates = []
    for url, match in url_to_match.items():
        if match:
            page_date = extract_page_date(url)
            role = guess_role_from_keywords(match["matched_keywords"])
            label = detect_url_label(match["url"], match["matched_keywords"])

            candidate = {
                "url": match["url"],
                "conference": conf["short"],
                "year": year,
                "role": role,
                "label": label,
                "date": page_date,
                "confirmed": False,
                "matched_keywords": match["matched_keywords"],
            }
            candidates.append(candidate)

            print(f"    MATCH #{len(candidates)}: {role} - {match['url'][:120]}...")
            print(f"          Keywords: {', '.join(match['matched_keywords'][:3])}")

    return candidates


def step4_analyze_content(
    all_links: list[dict[str, str]],
    conf: dict[str, Any],
    year: int,
    known_urls: set[str],
) -> list[dict[str, Any]]:
    """Step 4: Analyze content of collected pages.

    :param all_links: List of all links with text
    :param conf: Conference dictionary
    :param year: Target year
    :param known_urls: Set of known URLs to skip
    :return: List of candidate dictionaries
    """
    promising = _filter_promising_links(all_links)

    if not promising:
        print(
            f"  [4/4] No promising pages to analyze (filtered from {len(all_links)} total)"
        )
        return []

    to_check, skipped = _filter_known_urls(promising, known_urls)

    if not to_check:
        print(f"  [4/4] All {len(promising)} promising pages already known (skipped)")
        return []

    print(
        f"  [4/4] Analyze content of {len(to_check)} promising pages (filtered from {len(all_links)} total, {skipped} known)"
    )

    urls_to_check = [link["url"] for link in to_check]
    url_to_match = asyncio.run(async_check_content_batch(urls_to_check))

    candidates = _enrich_matches(url_to_match, conf, year)

    print(f"    Results: {len(candidates)} matches, {skipped} known URLs skipped")
    return candidates
