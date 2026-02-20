"""Tests for discover/scoring.py scoring functions."""

import pytest
from discover.scoring import (
    ScoredURL,
    score_search_result,
    score_link,
    score_content_signals,
    compute_final_score,
    classify_decision,
)
from discover import config


class TestScoredURL:
    """Tests for ScoredURL dataclass properties."""

    def test_graph_score_sum(self):
        su = ScoredURL(url="https://a.com", search_score=5.0, link_score=3.0)
        assert su.graph_score == 8.0

    def test_graph_score_zero(self):
        su = ScoredURL(url="https://a.com")
        assert su.graph_score == 0.0

    def test_final_score_uses_weights(self):
        su = ScoredURL(
            url="https://a.com",
            search_score=10.0,
            link_score=5.0,
            content_score=8.0,
        )
        expected = compute_final_score(10.0, 15.0, 8.0)
        assert su.final_score == pytest.approx(expected)

    def test_defaults(self):
        su = ScoredURL(url="https://a.com")
        assert su.parent_url == ""
        assert su.depth == 0
        assert su.source_type == ""
        assert su.from_reviewer_search is False


class TestScoreSearchResult:
    """Tests for score_search_result."""

    def test_matching_conference_scores_high(self):
        result = {
            "url": "https://ijcai.org/2026",
            "title": "IJCAI 2026",
            "snippet": "International Joint Conference on AI",
        }
        conf = {"short": "IJCAI", "name": "IJCAI", "domain": "ijcai.org"}
        score = score_search_result(result, conf, 2026, "homepage")
        # 10 (abbr in url) + 5 (same domain) + 3 (abbr in title) + 2 (name in title)
        # + 2 (year in title) + 3 (homepage category) = 25
        assert score > 20

    def test_non_matching_scores_low(self):
        result = {
            "url": "https://example.com/random",
            "title": "Random Page",
            "snippet": "Nothing relevant",
        }
        conf = {"short": "IJCAI", "name": "IJCAI", "domain": "ijcai.org"}
        score = score_search_result(result, conf, 2026, "homepage")
        assert score == config.QUERY_SCORE_HOMEPAGE  # only category bonus

    def test_category_reviewer_bonus(self):
        result = {"url": "https://example.com", "title": "", "snippet": ""}
        conf = {"short": "TEST", "name": "Test", "domain": "example.com"}
        score_rev = score_search_result(result, conf, 2026, "reviewer")
        score_call = score_search_result(result, conf, 2026, "call")
        # reviewer bonus (3) > call bonus (1)
        assert score_rev > score_call

    def test_year_in_snippet_bonus(self):
        result = {
            "url": "https://example.com",
            "title": "",
            "snippet": "Conference 2026",
        }
        conf = {"short": "TEST", "name": "Test", "domain": "example.com"}
        with_year = score_search_result(result, conf, 2026, "homepage")
        result_no_year = {
            "url": "https://example.com",
            "title": "",
            "snippet": "Conference",
        }
        without_year = score_search_result(result_no_year, conf, 2026, "homepage")
        assert with_year > without_year


class TestScoreLink:
    """Tests for score_link."""

    def test_reviewer_keyword_bonus(self):
        score = score_link("Call for Reviewers", "https://a.com/reviewers", 0, 0, True)
        assert score >= config.LINK_SCORE_REVIEWER_KW

    def test_pc_keyword_bonus(self):
        score = score_link("Program Committee", "https://a.com/pc", 0, 0, True)
        assert score >= config.LINK_SCORE_PC_KW

    def test_committee_keyword_bonus(self):
        score = score_link("Committee Members", "https://a.com/committee", 0, 0, True)
        assert score >= config.LINK_SCORE_COMMITTEE_KW

    def test_call_keyword_bonus(self):
        score = score_link("Call for Nominations", "https://a.com/calls", 0, 0, True)
        assert score >= config.LINK_SCORE_CALL_KW

    def test_same_domain_bonus(self):
        score_same = score_link("Page", "https://a.com/page", 0, 0, True)
        score_ext = score_link("Page", "https://a.com/page", 0, 0, False)
        assert score_same > score_ext

    def test_depth_penalty(self):
        score_d0 = score_link("Review", "https://a.com/review", 0, 0, True)
        score_d2 = score_link("Review", "https://a.com/review", 0, 2, True)
        assert score_d0 > score_d2
        assert score_d0 - score_d2 == pytest.approx(2 * config.DEPTH_PENALTY)

    def test_non_html_penalty(self):
        score_html = score_link("Paper", "https://a.com/doc.html", 0, 0, True)
        score_pdf = score_link("Paper", "https://a.com/doc.pdf", 0, 0, True)
        assert score_html > score_pdf

    def test_no_keyword_match(self):
        score = score_link("About Us", "https://a.com/about", 0, 0, True)
        # Only domain bonus, no keyword bonus
        assert score == config.LINK_SCORE_SAME_DOMAIN


class TestScoreContentSignals:
    """Tests for score_content_signals."""

    def test_high_confidence_signal(self):
        text = "please self-nomination form for reviewers"
        score, evidence = score_content_signals(text)
        assert score > 0
        assert any("high:" in e for e in evidence)

    def test_negative_signal_no_recovery(self):
        text = "call for workshop proposals deadline extended"
        score, evidence = score_content_signals(text)
        assert score < 0
        assert any("negative:" in e for e in evidence)

    def test_negative_signal_with_recovery(self):
        text = (
            "call for workshop proposals and call for reviewers and reviewer nomination"
        )
        score, evidence = score_content_signals(text)
        assert any("negative_recovered:" in e for e in evidence)

    def test_medium_confidence_with_context(self):
        text = "we are looking for reviewer to help with the conference"
        score, evidence = score_content_signals(text)
        assert score > 0
        assert any("medium:" in e for e in evidence)

    def test_medium_confidence_without_context(self):
        text = "we are looking for sponsors to help with the conference"
        score, evidence = score_content_signals(text)
        assert not any("medium:" in e for e in evidence)

    def test_multiple_high_signals_bonus(self):
        text = (
            "self-nomination nominate yourself call for reviewer "
            "recruiting reviewer pc recruitment become a reviewer"
        )
        score, evidence = score_content_signals(text)
        assert any("bonus:multi_strong" in e for e in evidence)

    def test_empty_text(self):
        score, evidence = score_content_signals("")
        assert score == 0.0
        assert evidence == []


class TestComputeFinalScore:
    """Tests for compute_final_score."""

    def test_weighted_combination(self):
        result = compute_final_score(10.0, 5.0, 8.0)
        expected = (
            10.0 * config.WEIGHT_SEARCH
            + 5.0 * config.WEIGHT_GRAPH
            + 8.0 * config.WEIGHT_CONTENT
        )
        assert result == pytest.approx(expected)

    def test_zero_inputs(self):
        assert compute_final_score(0, 0, 0) == 0.0

    def test_negative_content(self):
        result = compute_final_score(10.0, 5.0, -5.0)
        assert result < compute_final_score(10.0, 5.0, 0)


class TestClassifyDecision:
    """Tests for classify_decision."""

    def test_accept(self):
        assert classify_decision(config.ACCEPT_THRESHOLD) == "accept"
        assert classify_decision(config.ACCEPT_THRESHOLD + 1) == "accept"

    def test_gray_zone(self):
        assert classify_decision(config.GRAY_ZONE_THRESHOLD) == "gray_zone"
        assert classify_decision(config.ACCEPT_THRESHOLD - 0.1) == "gray_zone"

    def test_reject(self):
        assert classify_decision(config.GRAY_ZONE_THRESHOLD - 0.1) == "reject"
        assert classify_decision(0) == "reject"
        assert classify_decision(-5) == "reject"
