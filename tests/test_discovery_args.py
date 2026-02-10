"""Tests for discovery argument parsing and helpers."""

import pytest
from discover.main import parse_args, DiscoveryArgs, _deduplicate_links, _apply_filters


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_args_defaults(self):
        """Should use defaults when no args provided."""
        args = parse_args([])
        assert args.conference is None
        assert args.rank is None
        assert args.area is None
        assert args.limit is None
        assert args.max_links == 15
        assert args.dry_run is False
        assert args.search_provider == "duckduckgo"
        assert args.serper_key == ""
        assert args.repo == ""
        assert args.date_range == "m"

    def test_parse_args_conference(self):
        """Should parse conference argument."""
        args = parse_args(["--conference", "IJCAI"])
        assert args.conference == "IJCAI"

    def test_parse_args_conference_uppercase(self):
        """Should convert conference to uppercase."""
        args = parse_args(["--conference", "ijcai"])
        assert args.conference == "IJCAI"

    def test_parse_args_rank(self):
        """Should parse rank argument."""
        args = parse_args(["--rank", "A"])
        assert args.rank == "A"

    def test_parse_args_rank_lowercase_to_upper(self):
        """Should convert rank to uppercase."""
        args = parse_args(["--rank", "a"])
        assert args.rank == "A"

    def test_parse_args_invalid_rank(self):
        """Should reject invalid rank."""
        with pytest.raises(SystemExit):
            parse_args(["--rank", "D"])

    def test_parse_args_area(self):
        """Should parse area argument."""
        args = parse_args(["--area", "AI"])
        assert args.area == "AI"

    def test_parse_args_area_lowercase_to_upper(self):
        """Should convert area to uppercase."""
        args = parse_args(["--area", "ai"])
        assert args.area == "AI"

    def test_parse_args_invalid_area(self):
        """Should reject invalid area."""
        with pytest.raises(SystemExit):
            parse_args(["--area", "XX"])

    def test_parse_args_limit(self):
        """Should parse limit argument."""
        args = parse_args(["--limit", "10"])
        assert args.limit == 10

    def test_parse_args_invalid_limit(self):
        """Should reject zero or negative limit."""
        with pytest.raises(SystemExit):
            parse_args(["--limit", "0"])
        with pytest.raises(SystemExit):
            parse_args(["--limit", "-5"])

    def test_parse_args_dry_run_flag(self):
        """Should set dry_run flag."""
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_parse_args_init_flag(self):
        """--init should override date_range to 'y'."""
        args = parse_args(["--init"])
        assert args.date_range == "y"

    def test_parse_args_init_overrides_date_range(self):
        """--init should override explicit --date-range."""
        args = parse_args(["--init", "--date-range", "w"])
        assert args.date_range == "y"

    def test_parse_args_max_links(self):
        """Should parse max_links argument."""
        args = parse_args(["--max-links", "20"])
        assert args.max_links == 20

    def test_parse_args_invalid_max_links(self):
        """Should reject zero or negative max_links."""
        with pytest.raises(SystemExit):
            parse_args(["--max-links", "0"])
        with pytest.raises(SystemExit):
            parse_args(["--max-links", "-1"])

    def test_parse_args_search_provider(self):
        """Should parse search provider."""
        args = parse_args(["--search-provider", "serper"])
        assert args.search_provider == "serper"

    def test_parse_args_invalid_search_provider(self):
        """Should reject invalid search provider."""
        with pytest.raises(SystemExit):
            parse_args(["--search-provider", "google"])

    def test_parse_args_serper_key(self):
        """Should parse serper key."""
        args = parse_args(["--serper-key", "abc123"])
        assert args.serper_key == "abc123"

    def test_parse_args_repo(self):
        """Should parse repo argument."""
        args = parse_args(["--repo", "owner/repo"])
        assert args.repo == "owner/repo"

    def test_parse_args_date_range(self):
        """Should parse date range."""
        args = parse_args(["--date-range", "m"])
        assert args.date_range == "m"

    def test_parse_args_date_range_none(self):
        """Should convert 'none' to None."""
        args = parse_args(["--date-range", "none"])
        assert args.date_range is None

    def test_parse_args_invalid_date_range(self):
        """Should reject invalid date range."""
        with pytest.raises(SystemExit):
            parse_args(["--date-range", "x"])

    def test_parse_args_multiple_arguments(self):
        """Should parse multiple arguments together."""
        args = parse_args(
            ["--conference", "IJCAI", "--rank", "A", "--area", "AI", "--limit", "5"]
        )
        assert args.conference == "IJCAI"
        assert args.rank == "A"
        assert args.area == "AI"
        assert args.limit == 5

    def test_parse_args_all_flags(self):
        """Should parse all options together."""
        args = parse_args(
            [
                "--dry-run",
                "--search-provider",
                "serper",
                "--serper-key",
                "key123",
                "--repo",
                "owner/repo",
                "--date-range",
                "w",
            ]
        )
        assert args.dry_run is True
        assert args.search_provider == "serper"
        assert args.serper_key == "key123"
        assert args.repo == "owner/repo"
        assert args.date_range == "w"

    def test_parse_args_valid_ranks(self):
        """Should accept all valid ranks."""
        for rank in ["A", "B", "C"]:
            args = parse_args(["--rank", rank])
            assert args.rank == rank

    def test_parse_args_valid_areas(self):
        """Should accept all valid areas."""
        valid_areas = ["AI", "CG", "CT", "DB", "DS", "HI", "MX", "NW", "SC", "SE"]
        for area in valid_areas:
            args = parse_args(["--area", area])
            assert args.area == area


class TestDiscoveryArgs:
    """Tests for DiscoveryArgs dataclass."""

    def test_discovery_args_creation(self):
        """Should create DiscoveryArgs instance."""
        args = DiscoveryArgs(
            conference="IJCAI", rank="A", area="AI", limit=10, dry_run=True
        )
        assert args.conference == "IJCAI"
        assert args.rank == "A"
        assert args.area == "AI"
        assert args.limit == 10
        assert args.dry_run is True

    def test_discovery_args_defaults(self):
        """Should have sensible defaults."""
        args = DiscoveryArgs()
        assert args.max_links == 15
        assert args.dry_run is False
        assert args.search_provider == "duckduckgo"
        assert args.serper_key == ""
        assert args.repo == ""
        assert args.date_range == "m"


class TestDeduplicateLinks:
    """Tests for _deduplicate_links function."""

    def test_removes_duplicates(self):
        links = [
            {"url": "https://a.com", "text": "A"},
            {"url": "https://b.com", "text": "B"},
            {"url": "https://a.com", "text": "A again"},
        ]
        result = _deduplicate_links(links)
        assert len(result) == 2

    def test_preserves_first_occurrence(self):
        links = [
            {"url": "https://a.com", "text": "First"},
            {"url": "https://a.com", "text": "Second"},
        ]
        result = _deduplicate_links(links)
        assert result[0]["text"] == "First"

    def test_preserves_order(self):
        links = [
            {"url": "https://c.com", "text": "C"},
            {"url": "https://a.com", "text": "A"},
            {"url": "https://b.com", "text": "B"},
        ]
        result = _deduplicate_links(links)
        assert [r["url"] for r in result] == [
            "https://c.com",
            "https://a.com",
            "https://b.com",
        ]

    def test_empty_list(self):
        assert _deduplicate_links([]) == []


class TestApplyFilters:
    """Tests for _apply_filters function."""

    def _make_confs(self):
        return [
            {"short": "IJCAI", "rank": {"ccf": "A"}, "area": "AI"},
            {"short": "AAAI", "rank": {"ccf": "A"}, "area": "AI"},
            {"short": "KDD", "rank": {"ccf": "A"}, "area": "DB"},
            {"short": "ICSE", "rank": {"ccf": "A"}, "area": "SE"},
            {"short": "SEKE", "rank": {"ccf": "B"}, "area": "SE"},
        ]

    def test_filter_by_conference(self):
        args = DiscoveryArgs(conference="IJCAI")
        result = _apply_filters(self._make_confs(), args)
        assert len(result) == 1
        assert result[0]["short"] == "IJCAI"

    def test_filter_by_rank(self):
        args = DiscoveryArgs(rank="A")
        result = _apply_filters(self._make_confs(), args)
        assert all(c["rank"]["ccf"] == "A" for c in result)

    def test_filter_by_area(self):
        args = DiscoveryArgs(area="SE")
        result = _apply_filters(self._make_confs(), args)
        assert all(c["area"] == "SE" for c in result)
        assert len(result) == 2

    def test_filter_by_limit(self):
        args = DiscoveryArgs(limit=2)
        result = _apply_filters(self._make_confs(), args)
        assert len(result) == 2

    def test_combined_filters(self):
        args = DiscoveryArgs(rank="A", area="AI")
        result = _apply_filters(self._make_confs(), args)
        assert len(result) == 2

    def test_no_filters_returns_all(self):
        args = DiscoveryArgs()
        result = _apply_filters(self._make_confs(), args)
        assert len(result) == 5

    def test_filter_no_match(self):
        args = DiscoveryArgs(conference="NONEXISTENT")
        result = _apply_filters(self._make_confs(), args)
        assert len(result) == 0
