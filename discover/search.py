"""Search engine abstraction for DuckDuckGo and Serper.

Returns ``list[dict]`` with keys: title, url, snippet.
Providers: duckduckgo (free, default), serper (2500 free/month).
"""

from __future__ import annotations


def search(
    query: str,
    max_results: int = 10,
    provider: str = "duckduckgo",
    serper_key: str = "",
    date_range: str | None = "m",
) -> list[dict[str, str]]:
    """Search for a query using the specified provider.

    :param query: Search query string
    :param max_results: Maximum number of results to return
    :param provider: Search provider ('duckduckgo' or 'serper')
    :param serper_key: API key for Serper provider
    :param date_range: Date range filter ('d', 'w', 'm', 'y', or None)
    :return: List of result dicts with keys: title, url, snippet
    """
    if provider == "serper":
        return _search_serper(query, max_results, serper_key)
    return _search_duckduckgo(query, max_results, date_range)


def _search_duckduckgo(
    query: str, max_results: int, date_range: str | None = "m"
) -> list[dict[str, str]]:
    """Search via DuckDuckGo text API.

    :param query: Search query string
    :param max_results: Maximum results to return
    :param date_range: Time limit filter
    :return: List of result dicts
    """
    from ddgs import DDGS
    from ddgs.exceptions import TimeoutException, DDGSException

    try:
        raw = DDGS().text(query, timelimit=date_range, max_results=max_results)
        return [
            {"title": r["title"], "url": r["href"], "snippet": r["body"]} for r in raw
        ]
    except (TimeoutException, DDGSException) as e:
        print(f"    [SKIP] Search failed: {e}")
        return []


def _search_serper(
    query: str, max_results: int, serper_key: str
) -> list[dict[str, str]]:
    """Search via Serper (Google) API.

    :param query: Search query string
    :param max_results: Maximum results to return
    :param serper_key: Serper API key
    :return: List of result dicts
    :raises requests.HTTPError: On API errors
    """
    import requests

    resp = requests.post(
        "https://google.serper.dev/search",
        json={"q": query, "num": max_results},
        headers={
            "X-API-KEY": serper_key,
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return [
        {"title": r["title"], "url": r["link"], "snippet": r.get("snippet", "")}
        for r in resp.json().get("organic", [])
    ]
