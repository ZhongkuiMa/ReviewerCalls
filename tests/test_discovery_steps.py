"""Tests for pipeline.py discovery pipeline steps."""

import pytest
from discover.pipeline import (
    detect_url_label,
    _build_search_queries,
    _validate_and_score_results,
    _select_best_homepage,
    _filter_reviewer_results,
    _filter_promising_links,
    _filter_known_urls,
)


class TestDetectUrlLabel:
    """Tests for detect_url_label function."""

    def test_main_page(self):
        assert (
            detect_url_label(
                "https://example.com/reviewer-call", ["call for reviewers"]
            )
            == "Main"
        )

    def test_workshop(self):
        assert (
            detect_url_label(
                "https://example.com/workshop/reviewer-call", ["call for reviewers"]
            )
            == "Workshop"
        )

    def test_workshop_keyword(self):
        assert (
            detect_url_label(
                "https://docs.google.com/forms/d/123", ["workshop", "call"]
            )
            == "Workshop"
        )

    def test_industry_track(self):
        assert (
            detect_url_label(
                "https://example.com/industry-call", ["call for reviewers"]
            )
            == "Industry"
        )

    def test_shadow_pc(self):
        assert (
            detect_url_label("https://example.com/shadow-pc", ["shadow", "pc"])
            == "Shadow/Junior"
        )

    def test_default_main(self):
        assert (
            detect_url_label("https://example.com/page", ["call for reviewers"])
            == "Main"
        )


@pytest.mark.parametrize(
    "url,keywords,expected_label",
    [
        ("https://example.com/workshop/call", ["Workshop Call"], "Workshop"),
        ("https://example.com/industry", ["Industry Track"], "Industry"),
        ("https://docs.google.com/forms/d/123", ["Workshop Form"], "Workshop"),
        ("https://example.com/page", ["Reviewer Call"], "Main"),
    ],
)
def test_detect_url_label_parametrized(url, keywords, expected_label):
    """Parametrized tests for url label detection."""
    assert detect_url_label(url, keywords) == expected_label


class TestBuildSearchQueries:
    """Tests for _build_search_queries."""

    def test_basic_queries(self):
        conf = {"short": "IJCAI"}
        main_q, reviewer_q = _build_search_queries(conf, 2026)
        assert '"IJCAI"' in main_q
        assert '"2026"' in main_q
        assert "conference" in main_q
        assert '"IJCAI"' in reviewer_q
        assert "reviewer" in reviewer_q

    def test_different_conference(self):
        conf = {"short": "NeurIPS"}
        main_q, reviewer_q = _build_search_queries(conf, 2027)
        assert '"NeurIPS"' in main_q
        assert '"2027"' in main_q


class TestValidateAndScoreResults:
    """Tests for _validate_and_score_results."""

    def test_matching_result_gets_positive_score(self):
        results = [
            {"url": "https://ijcai.org/2026", "title": "IJCAI 2026", "snippet": ""}
        ]
        conf = {"short": "IJCAI", "name": "IJCAI", "domain": "ijcai.org"}
        candidates = _validate_and_score_results(results, conf, 2026)
        assert len(candidates) == 1
        assert candidates[0]["score"] > 0

    def test_non_matching_result_filtered(self):
        results = [
            {"url": "https://example.com/random", "title": "Random", "snippet": ""}
        ]
        conf = {"short": "IJCAI", "name": "IJCAI", "domain": "ijcai.org"}
        candidates = _validate_and_score_results(results, conf, 2026)
        assert len(candidates) == 0

    def test_multiple_results_scored(self):
        results = [
            {"url": "https://ijcai.org/2026", "title": "IJCAI 2026", "snippet": ""},
            {"url": "https://example.com/random", "title": "Random", "snippet": ""},
            {"url": "https://ijcai.org/calls", "title": "IJCAI Calls", "snippet": ""},
        ]
        conf = {"short": "IJCAI", "name": "IJCAI", "domain": "ijcai.org"}
        candidates = _validate_and_score_results(results, conf, 2026)
        assert len(candidates) == 2  # two matching, one filtered


class TestSelectBestHomepage:
    """Tests for _select_best_homepage."""

    def test_selects_highest_score(self):
        candidates = [
            {"url": "https://a.com", "score": 5, "depth": 0},
            {"url": "https://b.com", "score": 15, "depth": 0},
        ]
        assert _select_best_homepage(candidates) == "https://b.com"

    def test_tiebreak_by_depth(self):
        candidates = [
            {"url": "https://a.com/deep/path", "score": 15, "depth": 2},
            {"url": "https://b.com", "score": 15, "depth": 0},
        ]
        assert _select_best_homepage(candidates) == "https://b.com"


class TestFilterReviewerResults:
    """Tests for _filter_reviewer_results."""

    def test_excludes_same_domain(self):
        results = [
            {"url": "https://ijcai.org/reviewer", "title": "Review"},
            {"url": "https://other.com/form", "title": "Form"},
        ]
        filtered = _filter_reviewer_results(results, "https://ijcai.org/")
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://other.com/form"

    def test_marks_from_reviewer_search(self):
        results = [{"url": "https://other.com/form", "title": "Form"}]
        filtered = _filter_reviewer_results(results, "https://ijcai.org/")
        assert filtered[0]["from_reviewer_search"] is True

    def test_empty_results(self):
        assert _filter_reviewer_results([], "https://ijcai.org/") == []


class TestFilterPromisingLinks:
    """Tests for _filter_promising_links."""

    def test_keeps_promising_by_text(self):
        links = [
            {"url": "https://a.com", "text": "Call for Reviewers"},
            {"url": "https://b.com", "text": "About Us"},
        ]
        result = _filter_promising_links(links)
        assert len(result) == 1
        assert result[0]["url"] == "https://a.com"

    def test_keeps_from_reviewer_search(self):
        links = [
            {"url": "https://a.com", "text": "Some Form", "from_reviewer_search": True},
        ]
        result = _filter_promising_links(links)
        assert len(result) == 1

    def test_empty_input(self):
        assert _filter_promising_links([]) == []


class TestFilterKnownUrls:
    """Tests for _filter_known_urls."""

    def test_filters_known(self):
        links = [
            {"url": "https://a.com/call"},
            {"url": "https://b.com/call"},
        ]
        known = {"https://a.com/call"}
        new_links, skipped = _filter_known_urls(links, known)
        assert len(new_links) == 1
        assert skipped == 1
        assert new_links[0]["url"] == "https://b.com/call"

    def test_no_known(self):
        links = [{"url": "https://a.com/call"}]
        new_links, skipped = _filter_known_urls(links, set())
        assert len(new_links) == 1
        assert skipped == 0
