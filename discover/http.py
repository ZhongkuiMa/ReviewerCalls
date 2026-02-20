"""Shared HTTP client with default headers, timeout, and retry."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from discover import config

_HEADERS = {"User-Agent": config.USER_AGENT}

_retry = Retry(
    total=config.RETRY_MAX_ATTEMPTS,
    backoff_factor=config.RETRY_BACKOFF_BASE,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "HEAD"],
)

_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://", HTTPAdapter(max_retries=_retry))


def get(
    url: str,
    timeout: int | None = None,
    headers: dict[str, str] | None = None,
    allow_redirects: bool = True,
) -> requests.Response:
    """Perform GET request with shared configuration.

    :param url: URL to fetch
    :param timeout: Request timeout in seconds (defaults to config.TIMEOUT_TOTAL)
    :param headers: Additional headers to merge with defaults
    :param allow_redirects: Follow redirects
    :return: Response object
    :raises requests.RequestException: On network or timeout errors
    """
    if timeout is None:
        timeout = config.TIMEOUT_TOTAL

    merged = {**_HEADERS, **(headers or {})}

    return _session.get(
        url,
        timeout=timeout,
        headers=merged,
        allow_redirects=allow_redirects,
    )
