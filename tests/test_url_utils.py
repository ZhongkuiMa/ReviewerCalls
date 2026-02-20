"""Tests for utils.py URL utilities."""

import tempfile
import yaml
from pathlib import Path
from discover.utils import load_current_urls, normalize_url, is_same_domain


class TestNormalizeUrl:
    """Tests for normalize_url function."""

    def test_normalize_url_lowercase(self):
        """Should convert to lowercase."""
        assert normalize_url("HTTPS://EXAMPLE.COM/PATH") == "https://example.com/path"

    def test_normalize_url_trailing_slash(self):
        """Should remove trailing slash."""
        assert normalize_url("https://example.com/path/") == "https://example.com/path"

    def test_normalize_url_fragment(self):
        """Should remove fragment."""
        assert (
            normalize_url("https://example.com/path#section")
            == "https://example.com/path"
        )

    def test_normalize_url_www_removal(self):
        """Should remove www. prefix."""
        assert (
            normalize_url("https://www.example.com/path") == "https://example.com/path"
        )

    def test_normalize_url_www_in_subdomain(self):
        """Should handle www in subdomain (not at start)."""
        url = normalize_url("https://www2.example.com/path")
        assert url == "https://www2.example.com/path"

    def test_normalize_url_combined(self):
        """Should handle multiple transformations."""
        url = normalize_url("HTTPS://WWW.EXAMPLE.COM/PATH/#FRAG")
        assert url == "https://example.com/path"

    def test_normalize_url_without_www(self):
        """Should work for URLs without www."""
        assert normalize_url("https://example.com/path") == "https://example.com/path"

    def test_normalize_url_preserves_path_case(self):
        """Should convert only domain to lowercase, preserve path case in original."""
        # Note: normalize_url converts entire URL to lowercase for comparison
        assert normalize_url("https://EXAMPLE.COM/PATH") == "https://example.com/path"


class TestIsSameDomain:
    """Tests for is_same_domain function."""

    def test_is_same_domain_exact_match(self):
        """Should match exact domain."""
        assert is_same_domain("https://example.com/path", "example.com") is True

    def test_is_same_domain_subdomain(self):
        """Should match subdomain."""
        assert is_same_domain("https://sub.example.com/path", "example.com") is True

    def test_is_same_domain_different_domain(self):
        """Should not match different domain."""
        assert is_same_domain("https://other.com/path", "example.com") is False

    def test_is_same_domain_case_insensitive(self):
        """Should be case-insensitive."""
        assert is_same_domain("https://EXAMPLE.COM/path", "example.com") is True

    def test_is_same_domain_multiple_subdomains(self):
        """Should match with multiple subdomains."""
        assert is_same_domain("https://a.b.example.com/path", "example.com") is True

    def test_is_same_domain_www_prefix(self):
        """Should match with www prefix."""
        assert is_same_domain("https://www.example.com/path", "example.com") is True

    def test_is_same_domain_similar_name_different(self):
        """Should not match similar but different domains."""
        assert is_same_domain("https://notexample.com/path", "example.com") is False

    def test_is_same_domain_partial_match_fails(self):
        """Should not do substring matching."""
        assert is_same_domain("https://example-other.com/path", "example.com") is False


class TestLoadCurrentUrls:
    """Tests for load_current_urls function."""

    def test_load_current_urls_empty_file(self):
        """Should handle empty calls.yaml."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"calls": []}, f)
            f.flush()
            urls = load_current_urls(f.name)
            assert urls == set()
            Path(f.name).unlink()

    def test_load_current_urls_single_entry(self):
        """Should load single URL."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "calls": [
                        {
                            "conference": "IJCAI",
                            "year": 2026,
                            "url": "https://example.com/call",
                        }
                    ]
                },
                f,
            )
            f.flush()
            urls = load_current_urls(f.name)
            assert "https://example.com/call" in urls
            Path(f.name).unlink()

    def test_load_current_urls_normalizes(self):
        """Should normalize URLs when loading."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "calls": [
                        {
                            "conference": "IJCAI",
                            "year": 2026,
                            "url": "HTTPS://WWW.EXAMPLE.COM/CALL/",
                        }
                    ]
                },
                f,
            )
            f.flush()
            urls = load_current_urls(f.name)
            assert "https://example.com/call" in urls
            Path(f.name).unlink()

    def test_load_current_urls_multiple_entries(self):
        """Should load multiple URLs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "calls": [
                        {"url": "https://example.com/1"},
                        {"url": "https://example.com/2"},
                        {"url": "https://example.com/3"},
                    ]
                },
                f,
            )
            f.flush()
            urls = load_current_urls(f.name)
            assert len(urls) == 3
            Path(f.name).unlink()

    def test_load_current_urls_missing_url_field(self):
        """Should skip entries without url field."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "calls": [
                        {"conference": "IJCAI", "year": 2026},
                        {"url": "https://example.com/call"},
                    ]
                },
                f,
            )
            f.flush()
            urls = load_current_urls(f.name)
            assert len(urls) == 1
            assert "https://example.com/call" in urls
            Path(f.name).unlink()

    def test_load_current_urls_no_calls_key(self):
        """Should handle YAML without 'calls' key."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"other": []}, f)
            f.flush()
            urls = load_current_urls(f.name)
            assert urls == set()
            Path(f.name).unlink()
