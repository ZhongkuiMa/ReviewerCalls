"""Runtime configuration settings."""

from __future__ import annotations

USER_AGENT = "ReviewerCalls/0.1 (GitHub Action)"

# Network timeouts and retry settings
TIMEOUT_CONNECT = 5
TIMEOUT_TOTAL = 15
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 1.0
RETRY_429_BACKOFF = 5.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}

# Aliases for backwards compatibility
HOMEPAGE_TIMEOUT = TIMEOUT_TOTAL
CONCURRENT_REQUESTS = 10

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

CONFERENCES_FILE = "data/conferences.yaml"
CALLS_FILE = "data/calls.yaml"
REJECTED_URLS_FILE = "data/rejected_urls.yaml"

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

# Query layer: base score by search category
QUERY_SCORE_HOMEPAGE = 3
QUERY_SCORE_REVIEWER = 3
QUERY_SCORE_PC = 2
QUERY_SCORE_CALL = 1

# Graph layer: link scoring components
LINK_SCORE_REVIEWER_KW = 3
LINK_SCORE_PC_KW = 3
LINK_SCORE_COMMITTEE_KW = 2
LINK_SCORE_CALL_KW = 1
LINK_SCORE_SAME_DOMAIN = 2
LINK_SCORE_EXTERNAL = -1
LINK_SCORE_NON_HTML = -5
DEPTH_PENALTY = 1.0
MAX_GRAPH_DEPTH = 3
MIN_LINK_SCORE = -2.0
MAX_PAGES_PER_CONF = 50

# Content layer: signal scoring
CONTENT_HIGH_POSITIVE = 4
CONTENT_MEDIUM_POSITIVE = 2
CONTENT_WEAK_POSITIVE = 1
CONTENT_NEGATIVE = -5
CONTENT_RECOVERY = 2
CONTENT_BONUS_MULTI_STRONG = 3
CONTENT_BONUS_YEAR = 1

# Decision layer: weighted combination
WEIGHT_SEARCH = 0.4
WEIGHT_GRAPH = 0.3
WEIGHT_CONTENT = 0.3
ACCEPT_THRESHOLD = 5.0
GRAY_ZONE_THRESHOLD = 2.0
