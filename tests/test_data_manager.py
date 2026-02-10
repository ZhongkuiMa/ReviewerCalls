"""Tests for data.py data loading and persistence."""

import tempfile
import yaml
from datetime import date
from pathlib import Path
from unittest.mock import patch
from discover.data import (
    load_confs,
    is_in_recruitment_window,
    write_to_calls_yaml,
    read_yaml,
    write_yaml,
    backup_file,
    load_calls,
    merge_and_sort_calls,
)


class TestLoadConfs:
    """Tests for load_confs function."""

    def test_load_confs_basic(self):
        """Should load conferences from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "conferences": [
                        {"short": "IJCAI", "year": 2026, "conf_date": 8},
                        {"short": "AAAI", "year": 2026, "conf_date": 2},
                    ]
                },
                f,
            )
            f.flush()
            confs = load_confs(f.name)
            assert len(confs) == 2
            assert confs[0]["short"] == "IJCAI"
            Path(f.name).unlink()

    def test_load_confs_empty(self):
        """Should handle empty conference list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"conferences": []}, f)
            f.flush()
            confs = load_confs(f.name)
            assert len(confs) == 0
            Path(f.name).unlink()


class TestIsInRecruitmentWindow:
    """Tests for is_in_recruitment_window function."""

    @patch("discover.data.config.ROLLING_REVIEW_CONFERENCES", ["ACL", "EMNLP"])
    def test_rolling_review_always_in_window(self):
        """Should always include rolling review conferences."""
        conf = {"short": "ACL", "conf_date": 0}
        assert is_in_recruitment_window(conf, date(2026, 6, 15)) is True
        assert is_in_recruitment_window(conf, date(2026, 12, 15)) is True

    @patch("discover.data.config.ROLLING_REVIEW_CONFERENCES", [])
    def test_unknown_date_always_in_window(self):
        """Should include conferences with unknown date."""
        conf = {"short": "CONF", "conf_date": 0}
        assert is_in_recruitment_window(conf, date(2026, 6, 15)) is True

    @patch("discover.data.config.ROLLING_REVIEW_CONFERENCES", [])
    @patch("discover.data.config.RECRUITMENT_WINDOW_MIN_MONTHS", 2)
    @patch("discover.data.config.RECRUITMENT_WINDOW_MAX_MONTHS", 10)
    def test_conference_in_recruitment_window(self):
        """Should detect when conference is in recruitment window."""
        # Conference in August (month 8)
        # Active 2-10 months before = June to February
        conf = {"short": "CONF", "conf_date": 8}

        # June should be in window (2 months before August)
        assert is_in_recruitment_window(conf, date(2026, 6, 15)) is True
        # February should be in window (6 months before August)
        assert is_in_recruitment_window(conf, date(2026, 2, 15)) is True

    @patch("discover.data.config.ROLLING_REVIEW_CONFERENCES", [])
    @patch("discover.data.config.RECRUITMENT_WINDOW_MIN_MONTHS", 2)
    @patch("discover.data.config.RECRUITMENT_WINDOW_MAX_MONTHS", 10)
    def test_conference_outside_recruitment_window(self):
        """Should detect when conference is outside recruitment window."""
        # Conference in August (month 8)
        # Active 2-10 months before = June to February
        # September is outside (1 month before, need 2-10)
        conf = {"short": "CONF", "conf_date": 8}
        assert is_in_recruitment_window(conf, date(2026, 9, 15)) is False

    @patch("discover.data.config.ROLLING_REVIEW_CONFERENCES", [])
    @patch("discover.data.config.RECRUITMENT_WINDOW_MIN_MONTHS", 2)
    @patch("discover.data.config.RECRUITMENT_WINDOW_MAX_MONTHS", 10)
    def test_multiple_conference_dates(self):
        """Should be in window if ANY conference date matches."""
        conf = {"short": "CONF", "conf_date": [3, 8]}
        assert is_in_recruitment_window(conf, date(2026, 1, 15)) is True
        assert is_in_recruitment_window(conf, date(2026, 6, 15)) is True


class TestWriteToCallsYaml:
    """Tests for write_to_calls_yaml function."""

    def test_write_no_candidates(self):
        """Should return 0 when no candidates."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"calls": []}, f)
            f.flush()
            result = write_to_calls_yaml([], f.name)
            assert result == 0
            Path(f.name).unlink()

    def test_write_single_candidate(self):
        """Should write single candidate."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"calls": []}, f)
            f.flush()

            candidates = [
                {
                    "conference": "IJCAI",
                    "year": 2026,
                    "url": "https://example.com/call",
                    "role": "Reviewer",
                    "matched_keywords": ["reviewer", "call"],
                }
            ]

            result = write_to_calls_yaml(candidates, f.name)
            assert result == 1

            # Verify written file
            with open(f.name) as verify_f:
                data = yaml.safe_load(verify_f)
                assert len(data["calls"]) == 1
                assert data["calls"][0]["conference"] == "IJCAI"

            Path(f.name).unlink()

    def test_write_deduplicates_by_url(self):
        """Should not write duplicate URLs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            existing = [
                {
                    "conference": "IJCAI",
                    "year": 2025,
                    "url": "https://example.com/call",
                    "role": "Reviewer",
                }
            ]
            yaml.dump({"calls": existing}, f)
            f.flush()

            candidates = [
                {
                    "conference": "IJCAI",
                    "year": 2026,
                    "url": "https://example.com/call",
                    "role": "Reviewer",
                    "matched_keywords": ["reviewer"],
                }
            ]

            result = write_to_calls_yaml(candidates, f.name)
            assert result == 0

            Path(f.name).unlink()

    def test_write_normalizes_urls_for_dedup(self):
        """Should normalize URLs when checking for duplicates."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            existing = [
                {
                    "conference": "IJCAI",
                    "year": 2025,
                    "url": "HTTPS://EXAMPLE.COM/CALL/",
                    "role": "Reviewer",
                }
            ]
            yaml.dump({"calls": existing}, f)
            f.flush()

            candidates = [
                {
                    "conference": "IJCAI",
                    "year": 2026,
                    "url": "https://example.com/call",
                    "role": "Reviewer",
                    "matched_keywords": ["reviewer"],
                }
            ]

            result = write_to_calls_yaml(candidates, f.name)
            # Should detect as duplicate despite URL differences
            assert result == 0

            Path(f.name).unlink()

    def test_write_strips_matched_keywords(self):
        """Should not write matched_keywords field."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"calls": []}, f)
            f.flush()

            candidates = [
                {
                    "conference": "IJCAI",
                    "year": 2026,
                    "url": "https://example.com/call",
                    "role": "Reviewer",
                    "matched_keywords": ["reviewer", "call"],
                }
            ]

            write_to_calls_yaml(candidates, f.name)

            # Verify written file doesn't contain matched_keywords
            with open(f.name) as verify_f:
                data = yaml.safe_load(verify_f)
                assert "matched_keywords" not in data["calls"][0]

            Path(f.name).unlink()

    def test_write_creates_backup(self):
        """Should create backup file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"calls": []}, f)
            f.flush()
            yaml_path = f.name

            candidates = [
                {
                    "conference": "IJCAI",
                    "year": 2026,
                    "url": "https://example.com/call",
                    "role": "Reviewer",
                }
            ]

            write_to_calls_yaml(candidates, yaml_path)

            # Verify backup exists
            backup_path = yaml_path + ".backup"
            assert Path(backup_path).exists()

            Path(yaml_path).unlink()
            Path(backup_path).unlink()


class TestReadYaml:
    """Tests for read_yaml function."""

    def test_read_basic(self, tmp_yaml):
        path = tmp_yaml({"key": "value"})
        data = read_yaml(path)
        assert data["key"] == "value"

    def test_read_nested(self, tmp_yaml):
        path = tmp_yaml({"calls": [{"url": "https://example.com"}]})
        data = read_yaml(path)
        assert data["calls"][0]["url"] == "https://example.com"

    def test_read_nonexistent_raises(self):
        import pytest

        with pytest.raises(FileNotFoundError):
            read_yaml("/nonexistent/path.yaml")


class TestWriteYaml:
    """Tests for write_yaml function."""

    def test_write_and_read_back(self, tmp_path):
        path = str(tmp_path / "out.yaml")
        write_yaml(path, {"calls": [{"url": "https://example.com"}]})
        data = read_yaml(path)
        assert data["calls"][0]["url"] == "https://example.com"

    def test_write_with_header(self, tmp_path):
        path = str(tmp_path / "out.yaml")
        write_yaml(path, {"calls": []}, header="# My header\n")
        with open(path) as f:
            content = f.read()
        assert content.startswith("# My header\n")

    def test_write_without_header(self, tmp_path):
        path = str(tmp_path / "out.yaml")
        write_yaml(path, {"key": "val"})
        with open(path) as f:
            content = f.read()
        assert not content.startswith("#")


class TestBackupFile:
    """Tests for backup_file function."""

    def test_creates_backup(self, tmp_path):
        original = tmp_path / "test.yaml"
        original.write_text("original content")
        backup_path = backup_file(str(original))
        assert Path(backup_path).exists()
        assert Path(backup_path).read_text() == "original content"
        assert backup_path == str(original) + ".backup"

    def test_backup_overwrites_existing(self, tmp_path):
        original = tmp_path / "test.yaml"
        original.write_text("new content")
        backup = tmp_path / "test.yaml.backup"
        backup.write_text("old backup")
        backup_file(str(original))
        assert backup.read_text() == "new content"


class TestLoadCalls:
    """Tests for load_calls function."""

    def test_load_calls_basic(self, tmp_yaml):
        path = tmp_yaml({"calls": [{"url": "https://a.com"}, {"url": "https://b.com"}]})
        calls = load_calls(path)
        assert len(calls) == 2

    def test_load_calls_empty(self, tmp_yaml):
        path = tmp_yaml({"calls": []})
        calls = load_calls(path)
        assert calls == []

    def test_load_calls_missing_key(self, tmp_yaml):
        path = tmp_yaml({"other": "data"})
        calls = load_calls(path)
        assert calls == []


class TestMergeAndSortCalls:
    """Tests for merge_and_sort_calls function."""

    def test_merge_sorts_by_date_descending(self):
        new = [{"url": "https://a.com", "date": "2025-03-01"}]
        existing = [{"url": "https://b.com", "date": "2025-06-01"}]
        result = merge_and_sort_calls(new, existing)
        assert result[0]["date"] == "2025-06-01"
        assert result[1]["date"] == "2025-03-01"

    def test_merge_empty_new(self):
        existing = [{"url": "https://a.com", "date": "2025-01-01"}]
        result = merge_and_sort_calls([], existing)
        assert len(result) == 1

    def test_merge_empty_existing(self):
        new = [{"url": "https://a.com", "date": "2025-01-01"}]
        result = merge_and_sort_calls(new, [])
        assert len(result) == 1

    def test_merge_missing_date_sorts_last(self):
        entries = [
            {"url": "https://a.com", "date": "2025-06-01"},
            {"url": "https://b.com"},
        ]
        result = merge_and_sort_calls(entries, [])
        assert result[0]["date"] == "2025-06-01"
