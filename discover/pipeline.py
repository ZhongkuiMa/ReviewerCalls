"""Discovery pipeline step implementations."""

from __future__ import annotations

import heapq
import logging
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
from discover.batch import (
    AsyncFetcher,
    async_extract_links_batch,
    async_check_content_batch,
)
from discover.utils import guess_role_from_keywords, normalize_url, is_same_domain
from discover.scoring import (
    ScoredURL,
    score_search_result as _score_search_result,
    score_link as _score_link,
    compute_final_score as _compute_final_score,
    classify_decision as _classify_decision,
)
from discover import config as _cfg
from discover import http
from discover.search import search

logger = logging.getLogger(__name__)


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


def _build_search_queries(conf: dict[str, Any], year: int) -> list[tuple[str, str]]:
    """Build categorized search queries for multi-query ensemble.

    :param conf: Conference dictionary
    :param year: Target year
    :return: List of (query_string, category) tuples
    """
    abbr = conf["short"]
    return [
        (f'"{abbr}" "{year}" conference', "homepage"),
        (f'"{abbr}" "{year}" reviewer nomination', "reviewer"),
        (f'"{abbr}" "{year}" program committee call', "pc"),
        (f'"{abbr}" "{year}" call for reviewers', "call"),
    ]


def _validate_and_score_results(
    results: list[dict[str, str]],
    conf: dict[str, Any],
    year: int,
    category: str = "homepage",
) -> list[dict[str, Any]]:
    """Validate and score search results to find homepage candidates.

    :param results: Raw search results
    :param conf: Conference dictionary
    :param year: Target year
    :param category: Query category for scoring bonus
    :return: Scored candidate list
    """
    candidates = []
    for result in results:
        score = _score_search_result(result, conf, year, category)
        if score > 0:
            parsed = urlparse(result["url"])
            path_depth = len([p for p in parsed.path.strip("/").split("/") if p])
            candidates.append(
                {
                    "url": result["url"],
                    "depth": path_depth,
                    "score": score,
                    "search_score": score,
                    "title": result.get("title", ""),
                    "category": category,
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
    """Step 1: Multi-query ensemble search for homepage and reviewer pages.

    Issues 4 categorized searches (homepage, reviewer, pc, call), scores
    each result with category bonus, deduplicates by URL keeping highest
    score, then selects homepage and collects reviewer links.

    :param conf: Conference dictionary
    :param year: Target year
    :param search_provider: Search provider ('duckduckgo' or 'serper')
    :param serper_key: API key for Serper provider
    :param date_range: Date range filter ('d', 'w', 'm', 'y', or None)
    :return: Tuple of (homepage URL or None, list of reviewer-specific search results)
    """
    query_groups = _build_search_queries(conf, year)
    logger.info("  [1/4] Multi-query search (%d queries)", len(query_groups))

    search_kwargs = dict(
        provider=search_provider,
        serper_key=serper_key,
        date_range=date_range,
    )

    # Collect scored results across all query categories
    all_candidates: dict[str, dict[str, Any]] = {}  # url -> best candidate
    all_reviewer_results: list[dict[str, str]] = []

    for query, category in query_groups:
        logger.debug("    Query [%s]: %s", category, query)
        results = search(query, max_results=10, **search_kwargs)

        if not results:
            continue

        scored = _validate_and_score_results(results, conf, year, category)

        for c in scored:
            url = c["url"]
            if url not in all_candidates or c["score"] > all_candidates[url]["score"]:
                all_candidates[url] = c

        # Non-homepage queries produce reviewer links
        if category != "homepage":
            for r in results:
                all_reviewer_results.append(r)

    if not all_candidates:
        logger.info("    No search results - conference may not be recruiting yet")
        return None, []

    candidates = sorted(
        all_candidates.values(), key=lambda x: (-x["score"], x["depth"])
    )

    homepage = candidates[0]["url"]
    homepage_score = candidates[0]["score"]
    logger.info(
        "    Homepage: %s (score: %.0f, %d unique candidates)",
        homepage,
        homepage_score,
        len(candidates),
    )

    reviewer_links = _filter_reviewer_results(all_reviewer_results, homepage)

    if reviewer_links:
        logger.info("    Additional reviewer-specific results: %d", len(reviewer_links))

    return homepage, reviewer_links


def _score_conference_page(
    result: dict[str, str], conf: dict[str, Any], year: int
) -> int:
    """Score a search result to determine if it's the conference page.

    Legacy wrapper around scoring.score_search_result for backwards compat.

    :param result: Search result with 'url', 'title', 'snippet'
    :param conf: Conference dictionary
    :param year: Target year
    :return: Score (0 = not a match, higher = better match)
    """
    return int(_score_search_result(result, conf, year, "homepage"))


async def _explore_links_batch(
    links_to_explore: list[dict[str, str]],
    domain: str,
    conference_name: str = "",
    prioritize_by_keywords: bool = True,
    fetcher: AsyncFetcher | None = None,
) -> list[dict[str, str]]:
    """Extract and deduplicate links from multiple pages (async batch).

    :param links_to_explore: List of links to fetch and extract from
    :param domain: Conference domain for filtering
    :param conference_name: Conference short name
    :param prioritize_by_keywords: If True, sort by promising keywords
    :param fetcher: Optional AsyncFetcher instance
    :return: Deduplicated list of links
    """
    urls_to_fetch = [link["url"] for link in links_to_explore]

    url_to_links = await async_extract_links_batch(
        urls_to_fetch, domain, conference_name, fetcher=fetcher
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


async def step2_explore_level1(
    homepage: str,
    domain: str,
    conference_name: str = "",
    max_links: int = 15,
    fetcher: AsyncFetcher | None = None,
) -> list[dict[str, str]]:
    """Step 2: Dynamic link discovery via keyword filtering.

    :param homepage: Conference homepage URL
    :param domain: Conference domain
    :param conference_name: Conference short name
    :param max_links: Maximum links to explore (default: 15)
    :param fetcher: Optional AsyncFetcher instance
    :return: List of level 2 links with text
    """
    logger.info("  [2/4] Dynamic link discovery from homepage")

    try:
        resp = http.get(homepage)
        if resp.status_code != 200:
            logger.warning("    Failed to fetch homepage")
            return []

        parser = LinkExtractor(resp.url)
        parser.feed(resp.content.decode("utf-8", errors="replace"))

        filter_options = LinkFilterOptions(
            base_domain=domain,
            conference_name=conference_name,
            filter_useless=True,
            filter_by_text=False,
            filter_by_domain=False,
        )
        all_links = filter_links(parser.links, filter_options)

    except requests.RequestException as e:
        logger.warning("    Error extracting links: %s", e)
        return []

    logger.debug("    Extracted %d links from homepage", len(all_links))

    keyword_links = [link for link in all_links if should_explore_link(link)]

    keyword_links = keyword_links[:max_links]

    logger.info(
        "    Filtered %d links -> %d with keywords (max=%d)",
        len(all_links),
        len(keyword_links),
        max_links,
    )

    if not keyword_links:
        logger.debug("    No links match keywords")
        return []

    level2_links = await _explore_links_batch(
        keyword_links,
        domain,
        conference_name,
        prioritize_by_keywords=True,
        fetcher=fetcher,
    )

    promising = [link for link in level2_links if has_promising_keywords(link["text"])]

    logger.info(
        "    Level 2 links: %d total (%d promising)", len(level2_links), len(promising)
    )
    return level2_links


async def step3_explore_level2(
    level2_links: list[dict[str, str]],
    domain: str,
    conference_name: str = "",
    fetcher: AsyncFetcher | None = None,
) -> list[dict[str, str]]:
    """Step 3: Explore level 2 pages, collect level 3 URLs.

    :param level2_links: List of level 2 links with text
    :param domain: Conference domain
    :param conference_name: Conference short name
    :param fetcher: Optional AsyncFetcher instance
    :return: List of level 3 links with text
    """
    promising_links = [
        link for link in level2_links if has_promising_keywords(link["text"])
    ]

    if not promising_links:
        logger.info(
            "  [3/4] No promising L2 pages to explore (filtered from %d)",
            len(level2_links),
        )
        return []

    logger.info(
        "  [3/4] Extract links from %d promising L2 pages (filtered from %d total)",
        len(promising_links),
        len(level2_links),
    )

    level3_links = await _explore_links_batch(
        promising_links,
        domain,
        conference_name,
        prioritize_by_keywords=False,
        fetcher=fetcher,
    )

    logger.info("    Level 3 links: %d", len(level3_links))
    return level3_links


async def explore_graph(
    seeds: list[ScoredURL],
    domain: str,
    conference_name: str,
    *,
    max_depth: int | None = None,
    min_score: float | None = None,
    max_pages: int | None = None,
    fetcher: AsyncFetcher | None = None,
) -> list[ScoredURL]:
    """Score-driven BFS graph exploration.

    Replaces the fixed L1→L2→L3 pipeline with a priority-queue BFS that
    expands highest-scoring URLs first, up to *max_pages* page fetches
    or *max_depth* levels deep.

    :param seeds: Initial ScoredURL seeds (homepage + reviewer search results)
    :param domain: Conference domain for same-domain detection
    :param conference_name: Conference short name (for link filtering)
    :param max_depth: Maximum BFS depth (default: config.MAX_GRAPH_DEPTH)
    :param min_score: Minimum graph_score to explore (default: config.MIN_LINK_SCORE)
    :param max_pages: Maximum pages to fetch (default: config.MAX_PAGES_PER_CONF)
    :param fetcher: Optional AsyncFetcher instance
    :return: All explored ScoredURL objects
    """
    if max_depth is None:
        max_depth = _cfg.MAX_GRAPH_DEPTH
    if min_score is None:
        min_score = _cfg.MIN_LINK_SCORE
    if max_pages is None:
        max_pages = _cfg.MAX_PAGES_PER_CONF

    # Max-heap: negate score for heapq (min-heap)
    heap: list[tuple[float, int, ScoredURL]] = []
    counter = 0
    seen_urls: set[str] = set()
    explored: list[ScoredURL] = []
    pages_fetched = 0

    # Push seeds
    for seed in seeds:
        if seed.url not in seen_urls:
            heapq.heappush(heap, (-seed.graph_score, counter, seed))
            counter += 1
            seen_urls.add(seed.url)

    logger.info(
        "  [2/4] Graph BFS: %d seeds, max_depth=%d, max_pages=%d",
        len(seeds),
        max_depth,
        max_pages,
    )

    filter_options = LinkFilterOptions(
        base_domain=domain,
        conference_name=conference_name,
        filter_useless=True,
        filter_by_text=False,
        filter_by_domain=False,
    )

    while heap and pages_fetched < max_pages:
        neg_score, _, current = heapq.heappop(heap)
        explored.append(current)

        # Don't expand beyond max_depth
        if current.depth >= max_depth:
            continue

        # Fetch page and extract links
        pages_fetched += 1
        url_to_links = await async_extract_links_batch(
            [current.url], domain, conference_name, fetcher=fetcher
        )
        child_links = url_to_links.get(current.url, [])

        if not child_links:
            continue

        # Filter links
        filtered_links = filter_links(child_links, filter_options)

        for link in filtered_links:
            child_url = link["url"]
            if child_url in seen_urls:
                continue
            seen_urls.add(child_url)

            same_dom = is_same_domain(child_url, domain)
            child_link_score = _score_link(
                text=link.get("text", ""),
                url=child_url,
                parent_score=current.graph_score,
                depth=current.depth + 1,
                same_domain=same_dom,
            )

            child = ScoredURL(
                url=child_url,
                parent_url=current.url,
                depth=current.depth + 1,
                search_score=current.search_score,
                link_score=child_link_score,
                source_type="graph_link",
                text=link.get("text", ""),
                from_reviewer_search=current.from_reviewer_search,
            )

            if child.graph_score >= min_score:
                heapq.heappush(heap, (-child.graph_score, counter, child))
                counter += 1
                logger.debug(
                    "    BFS push [d=%d score=%.1f]: %s",
                    child.depth,
                    child.graph_score,
                    child_url[:80],
                )

    # Add remaining heap items that weren't expanded (they're still candidates)
    while heap:
        _, _, remaining = heapq.heappop(heap)
        explored.append(remaining)

    logger.info(
        "    Graph BFS complete: %d URLs explored, %d pages fetched",
        len(explored),
        pages_fetched,
    )

    return explored


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
    promising_links: list[dict[str, str]],
    known_urls: set[str],
    seen_final_urls: set[str] | None = None,
) -> tuple[list[dict[str, str]], int]:
    """Filter out known URLs from promising links.

    :param promising_links: List of promising links
    :param known_urls: Set of known URLs to filter
    :param seen_final_urls: Set of redirect final URLs already fetched
    :return: Tuple of (new_links, skipped_count)
    """
    to_check = []
    skipped = 0
    final_normalized = (
        {normalize_url(u) for u in seen_final_urls} if seen_final_urls else set()
    )
    for link in promising_links:
        norm = normalize_url(link["url"])
        if norm in known_urls or norm in final_normalized:
            logger.debug("      Skipping known URL: %s", link["url"][:100])
            skipped += 1
        else:
            to_check.append(link)
    if skipped:
        logger.info("    Skipped %d known URLs", skipped)
    return to_check, skipped


def _enrich_matches(
    url_to_match: dict[str, Any],
    conf: dict[str, Any],
    year: int,
) -> list[dict[str, Any]]:
    """Enrich matched URLs with metadata, scores, and decision classification.

    :param url_to_match: Dict mapping URLs to match dicts
    :param conf: Conference dictionary
    :param year: Target year
    :return: List of enriched candidate dictionaries, sorted by final_score desc
    """
    candidates = []
    for url, match in url_to_match.items():
        if match:
            page_date = extract_page_date(url)
            role = guess_role_from_keywords(match["matched_keywords"])
            label = detect_url_label(match["url"], match["matched_keywords"])
            strength = match.get("match_strength", "medium")
            evidence = match.get("evidence_snippet", "")
            source = match.get("source", "discovered_links")

            # Compute final score and decision
            search_score = match.get("search_score", 0)
            graph_score = match.get("graph_score", 0)
            content_score = match.get("content_score", 0)
            final_score = _compute_final_score(search_score, graph_score, content_score)
            decision = _classify_decision(final_score)

            candidate = {
                "url": match["url"],
                "conference": conf["short"],
                "year": year,
                "role": role,
                "label": label,
                "date": page_date,
                "confirmed": False,
                "matched_keywords": match["matched_keywords"],
                "match_strength": strength,
                "evidence_snippet": evidence,
                "source": source,
                "search_score": search_score,
                "graph_score": graph_score,
                "content_score": content_score,
                "final_score": final_score,
                "decision": decision,
            }
            candidates.append(candidate)

    # Sort by final_score descending
    candidates.sort(key=lambda c: c.get("final_score", 0), reverse=True)

    # Log top matches at INFO, rest at DEBUG
    for i, c in enumerate(candidates, 1):
        score = c.get("final_score", 0)
        decision = c.get("decision", "?")
        evidence = c.get("evidence_snippet", "")
        if i <= 3:
            logger.info(
                "    MATCH #%d [%.1f %s]: %s - %s",
                i,
                score,
                decision,
                c["role"],
                c["url"][:120],
            )
            if evidence:
                logger.info("      Evidence: %s", evidence[:120])
        else:
            logger.debug(
                "    MATCH #%d [%.1f %s]: %s - %s",
                i,
                score,
                decision,
                c["role"],
                c["url"][:120],
            )

    return candidates


async def step4_analyze_content(
    all_links: list[dict[str, str]],
    conf: dict[str, Any],
    year: int,
    known_urls: set[str],
    fetcher: AsyncFetcher | None = None,
) -> list[dict[str, Any]]:
    """Step 4: Analyze content of collected pages.

    :param all_links: List of all links with text
    :param conf: Conference dictionary
    :param year: Target year
    :param known_urls: Set of known URLs to skip
    :param fetcher: Optional AsyncFetcher instance
    :return: List of candidate dictionaries
    """
    promising = _filter_promising_links(all_links)

    if not promising:
        logger.info(
            "  [4/4] No promising pages to analyze (filtered from %d total)",
            len(all_links),
        )
        return []

    seen_final = fetcher.seen_final_urls if fetcher else None
    to_check, skipped = _filter_known_urls(promising, known_urls, seen_final)

    if not to_check:
        logger.info(
            "  [4/4] All %d promising pages already known (skipped)", len(promising)
        )
        return []

    logger.info(
        "  [4/4] Analyze content of %d promising pages (filtered from %d total, %d known)",
        len(to_check),
        len(all_links),
        skipped,
    )

    urls_to_check = [link["url"] for link in to_check]
    url_to_match = await async_check_content_batch(urls_to_check, fetcher=fetcher)

    # Thread scores and source from input links to match results
    url_meta = {
        link["url"]: {
            "source": (
                "reviewer_search"
                if link.get("from_reviewer_search")
                else "discovered_links"
            ),
            "graph_score": link.get("graph_score", 0),
            "search_score": link.get("search_score", 0),
        }
        for link in to_check
    }
    for url, match in url_to_match.items():
        if match:
            meta = url_meta.get(url, {})
            match["source"] = meta.get("source", "discovered_links")
            match["graph_score"] = meta.get("graph_score", 0)
            match["search_score"] = meta.get("search_score", 0)

    candidates = _enrich_matches(url_to_match, conf, year)

    logger.info(
        "    Results: %d matches, %d known URLs skipped", len(candidates), skipped
    )
    return candidates
