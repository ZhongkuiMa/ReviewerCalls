"""Numeric scoring functions for the discovery pipeline.

Four scoring layers:
  1. Query  – base score from search category
  2. Graph  – link-level score for BFS prioritisation
  3. Content – page-level signal scoring
  4. Decision – weighted combination → accept / gray_zone / reject
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from discover import config, constants
from discover.utils import is_same_domain

logger = logging.getLogger(__name__)

# Keyword buckets for link scoring (checked against link text + URL path)
_REVIEWER_TERMS = {"reviewer", "reviewers", "review"}
_PC_TERMS = {"pc", "program-committee", "programme-committee", "program committee"}
_COMMITTEE_TERMS = {
    "committee",
    "member",
    "members",
    "area-chair",
    "area chair",
    "spc",
    "aec",
    "artifact",
    "shadow",
}
_CALL_TERMS = {
    "call",
    "calls",
    "nomination",
    "nominations",
    "nominate",
    "recruitment",
    "recruit",
    "invite",
    "invitation",
    "volunteer",
    "join",
    "participate",
    "apply",
    "register",
    "signup",
    "sign-up",
}


@dataclass
class ScoredURL:
    """A URL with numeric scores from each pipeline layer."""

    url: str
    parent_url: str = ""
    depth: int = 0
    search_score: float = 0.0
    link_score: float = 0.0
    content_score: float = 0.0
    source_type: str = ""  # "search" | "homepage_link" | "graph_link"
    query_category: str = ""  # "homepage" | "reviewer" | "pc" | "call"
    text: str = ""
    from_reviewer_search: bool = False

    @property
    def graph_score(self) -> float:
        """Combined search + link score (used for BFS priority)."""
        return self.search_score + self.link_score

    @property
    def final_score(self) -> float:
        """Weighted combination of all layers."""
        return compute_final_score(
            self.search_score, self.graph_score, self.content_score
        )


def score_search_result(
    result: dict[str, str],
    conf: dict[str, Any],
    year: int,
    category: str,
) -> float:
    """Score a search result using existing page scoring + category bonus.

    :param result: Search result dict (url, title, snippet)
    :param conf: Conference dictionary
    :param year: Target year
    :param category: Query category ("homepage", "reviewer", "pc", "call")
    :return: Numeric score (higher is better)
    """
    # Inline the existing _score_conference_page logic
    score = 0.0
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

    # Category bonus
    category_bonus = {
        "homepage": config.QUERY_SCORE_HOMEPAGE,
        "reviewer": config.QUERY_SCORE_REVIEWER,
        "pc": config.QUERY_SCORE_PC,
        "call": config.QUERY_SCORE_CALL,
    }
    score += category_bonus.get(category, 0)

    return score


def score_link(
    text: str,
    url: str,
    parent_score: float,
    depth: int,
    same_domain: bool,
) -> float:
    """Score an extracted link for BFS prioritisation.

    :param text: Link text (visible anchor text)
    :param url: Link URL
    :param parent_score: Parent page's graph_score
    :param depth: BFS depth of this link
    :param same_domain: Whether link is on the conference domain
    :return: Link score component
    """
    score = 0.0
    text_lower = text.lower()
    path_lower = url.lower()
    combined = text_lower + " " + path_lower

    # Keyword bonuses (highest match wins per bucket)
    if any(term in combined for term in _REVIEWER_TERMS):
        score += config.LINK_SCORE_REVIEWER_KW
    elif any(term in combined for term in _PC_TERMS):
        score += config.LINK_SCORE_PC_KW
    elif any(term in combined for term in _COMMITTEE_TERMS):
        score += config.LINK_SCORE_COMMITTEE_KW
    elif any(term in combined for term in _CALL_TERMS):
        score += config.LINK_SCORE_CALL_KW

    # Domain bonus/penalty
    if same_domain:
        score += config.LINK_SCORE_SAME_DOMAIN
    else:
        score += config.LINK_SCORE_EXTERNAL

    # Non-HTML penalty
    non_html_exts = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".zip", ".tar"}
    if any(path_lower.endswith(ext) for ext in non_html_exts):
        score += config.LINK_SCORE_NON_HTML

    # Depth penalty
    score -= depth * config.DEPTH_PENALTY

    return score


def score_content_signals(visible_text: str) -> tuple[float, list[str]]:
    """Numeric content scoring based on signal lists.

    :param visible_text: Lowercase visible text of page
    :return: Tuple of (score, evidence_list)
    """
    score = 0.0
    evidence: list[str] = []
    high_hits = 0

    # Negative signals first (can be recovered)
    for signal in constants.NEGATIVE_SIGNALS:
        if signal in visible_text:
            if any(term in visible_text for term in constants.REVIEWER_RECOVERY_TERMS):
                score += config.CONTENT_RECOVERY
                evidence.append(f"negative_recovered:{signal}")
            else:
                score += config.CONTENT_NEGATIVE
                evidence.append(f"negative:{signal}")

    # High-confidence signals
    for signal in constants.HIGH_CONFIDENCE_SIGNALS:
        if signal in visible_text:
            score += config.CONTENT_HIGH_POSITIVE
            evidence.append(f"high:{signal}")
            high_hits += 1

    # Medium-confidence signals (with context check)
    for signal, context_terms in constants.MEDIUM_CONFIDENCE_SIGNALS:
        if signal in visible_text:
            pos = visible_text.find(signal)
            window = visible_text[max(0, pos - 200) : pos + 200]
            if any(term in window for term in context_terms):
                score += config.CONTENT_MEDIUM_POSITIVE
                evidence.append(f"medium:{signal}")

    # Bonus for multiple high-confidence hits
    if high_hits >= 3:
        score += config.CONTENT_BONUS_MULTI_STRONG
        evidence.append("bonus:multi_strong")

    return score, evidence


def compute_final_score(
    search_score: float,
    graph_score: float,
    content_score: float,
) -> float:
    """Weighted combination of all scoring layers.

    :param search_score: Score from query layer
    :param graph_score: Combined search + link score
    :param content_score: Score from content layer
    :return: Final weighted score
    """
    return (
        search_score * config.WEIGHT_SEARCH
        + graph_score * config.WEIGHT_GRAPH
        + content_score * config.WEIGHT_CONTENT
    )


def classify_decision(final_score: float) -> str:
    """Classify a candidate based on its final score.

    :param final_score: Weighted final score
    :return: "accept", "gray_zone", or "reject"
    """
    if final_score >= config.ACCEPT_THRESHOLD:
        return "accept"
    if final_score >= config.GRAY_ZONE_THRESHOLD:
        return "gray_zone"
    return "reject"
