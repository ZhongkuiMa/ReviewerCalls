"""Runtime configuration settings."""

from __future__ import annotations

USER_AGENT = "ReviewerCalls/0.1 (GitHub Action)"
HOMEPAGE_TIMEOUT = 10

ROLLING_REVIEW_CONFERENCES = [
    "ACL",
    "EMNLP",
    "NAACL",
    "EACL",
    "ICLR",
    "ICML",
    "NEURIPS",
]
RECRUITMENT_WINDOW_MIN_MONTHS = 2
RECRUITMENT_WINDOW_MAX_MONTHS = 10

CONCURRENT_REQUESTS = 10

CONFERENCES_FILE = "data/conferences.yaml"
CALLS_FILE = "data/calls.yaml"
REJECTED_URLS_FILE = "data/rejected_urls.yaml"
