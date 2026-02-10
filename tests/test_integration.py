"""Integration tests for the complete discovery pipeline."""

import datetime
import tempfile
import os
from unittest.mock import patch
from discover.data import is_in_recruitment_window, read_yaml, write_yaml
from discover.pipeline import step1_search_homepage, detect_url_label


class TestFullDiscoveryPipeline:
    """Test complete discovery pipeline with mocked search."""

    @patch("discover.pipeline.search")
    def test_step1_finds_homepage(self, mock_search):
        """Step 1 should find homepage from search results."""
        mock_search.return_value = [
            {
                "title": "IJCAI 2026",
                "url": "https://2026.ijcai.org/",
                "snippet": "IJCAI conf",
            },
        ]
        conf = {"short": "IJCAI", "name": "IJCAI", "domain": "ijcai.org"}
        homepage, reviewer_links = step1_search_homepage(conf, 2026)
        assert homepage is not None

    def test_recruitment_window_boundary(self):
        """Test recruitment window in/out boundaries."""
        conf = {"short": "AAAI", "conf_date": 2}
        assert is_in_recruitment_window(conf, datetime.date(2025, 4, 1))
        assert not is_in_recruitment_window(conf, datetime.date(2026, 3, 1))

    def test_url_label_detection(self):
        """Test URL label detection for different role types."""
        assert (
            detect_url_label(
                "https://example.com/workshops/call", ["workshop", "reviewer"]
            )
            == "Workshop"
        )
        assert (
            detect_url_label("https://example.com/industry-track/", ["industry"])
            == "Industry"
        )
        assert (
            detect_url_label("https://example.com/calls/shadow-pc", ["shadow", "pc"])
            == "Shadow/Junior"
        )
        assert (
            detect_url_label("https://example.com/reviewer-nomination", ["reviewer"])
            == "Main"
        )


class TestYAMLRoundTrip:
    """Test YAML read/write operations preserve data."""

    def test_round_trip(self):
        """Test basic YAML round trip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "test.yaml")
            test_data = {
                "calls": [
                    {
                        "url": "https://example.com/reviewer-call",
                        "conference": "TEST",
                        "year": 2026,
                        "role": "Reviewer",
                        "confirmed": True,
                        "date": "2025-01-15",
                    }
                ]
            }

            write_yaml(yaml_path, test_data)
            read_data = read_yaml(yaml_path)
            assert read_data["calls"][0]["url"] == "https://example.com/reviewer-call"
            assert read_data["calls"][0]["conference"] == "TEST"

    def test_header_preservation(self):
        """Test that YAML header comments are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "test_header.yaml")
            write_yaml(yaml_path, {"calls": []}, header="# Test header\n")

            with open(yaml_path) as f:
                assert "# Test header" in f.read()


class TestErrorHandling:
    """Test graceful error handling."""

    def test_malformed_html_extraction(self):
        """Test handling of malformed HTML during link extraction."""
        from discover.parsers import LinkExtractor

        extractor = LinkExtractor("https://example.com")
        extractor.feed(
            '<a href="/link1">Link 1</a><a href="/link2">Link 2<a href="/link3">Link 3</a>'
        )
        assert len(extractor.links) > 0

    def test_unknown_conference_in_recruitment_window(self):
        """Conference without conf_date should default to in-window."""
        conf = {"short": "UNKNOWN", "conf_date": 0}
        assert is_in_recruitment_window(conf, datetime.date.today()) is True


class TestDataIntegrity:
    """Test data integrity across pipeline operations."""

    def test_url_normalization_in_deduplication(self):
        """Trailing slash URLs should deduplicate to same normalized form."""
        from discover.data import extract_normalized_urls_from_calls

        calls = [
            {"url": "https://example.com/call/", "conference": "TEST", "year": 2026},
            {"url": "https://example.com/call", "conference": "TEST", "year": 2026},
        ]
        urls = extract_normalized_urls_from_calls(calls)
        assert len(urls) == 1

    def test_filter_new_candidates(self):
        """New candidates not in existing URLs should pass through."""
        from discover.data import filter_new_candidates

        candidates = [
            {"url": "https://example.com/call-1", "conference": "TEST", "year": 2026}
        ]
        existing_urls = {"https://other.com/call"}
        assert len(filter_new_candidates(candidates, existing_urls)) == 1

    def test_score_conference_page(self):
        """Conference page scoring should give positive score for matching result."""
        from discover.pipeline import _score_conference_page

        result = {
            "url": "https://ijcai.org/2026",
            "title": "IJCAI 2026",
            "snippet": "International Joint Conference",
        }
        conf = {"short": "IJCAI", "name": "IJCAI", "domain": "ijcai.org"}
        assert _score_conference_page(result, conf, 2026) > 0
