"""Shared HTTP client with default headers and timeout."""

from __future__ import annotations

import requests
from discover import config

_HEADERS = {"User-Agent": config.USER_AGENT}


def get(
    url: str,
    timeout: int | None = None,
    headers: dict[str, str] | None = None,
    allow_redirects: bool = True,
) -> requests.Response:
    """Perform GET request with shared configuration.

    :param url: URL to fetch
    :param timeout: Request timeout in seconds (defaults to config.HOMEPAGE_TIMEOUT)
    :param headers: Additional headers to merge with defaults
    :param allow_redirects: Follow redirects
    :return: Response object
    :raises requests.RequestException: On network or timeout errors
    """
    if timeout is None:
        timeout = config.HOMEPAGE_TIMEOUT

    merged = {**_HEADERS, **(headers or {})}

    return requests.get(
        url,
        timeout=timeout,
        headers=merged,
        allow_redirects=allow_redirects,
    )
