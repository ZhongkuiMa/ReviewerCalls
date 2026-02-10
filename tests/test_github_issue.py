"""Tests for github.py GitHub issue creation."""

import json
from unittest.mock import patch, MagicMock
import subprocess
from discover.github import (
    get_github_issues,
    create_issue,
    _format_candidate_row,
    _format_candidate_checklist,
)


class TestGetGithubIssues:
    """Tests for get_github_issues function."""

    def test_get_github_issues_dry_run(self):
        """Should return empty set in dry-run mode."""
        result = get_github_issues("owner/repo", dry_run=True)
        assert result == set()

    def test_get_github_issues_empty_repo(self):
        """Should return empty set when repo is empty."""
        result = get_github_issues("")
        assert result == set()

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_success(self, mock_run):
        """Should extract URLs from issue bodies."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            [
                {"body": "URL: https://example.com/call1\n"},
                {"body": "Check this: https://example.com/call2"},
            ]
        )
        mock_run.return_value = mock_result

        result = get_github_issues("owner/repo")
        assert "https://example.com/call1" in result
        assert "https://example.com/call2" in result
        assert len(result) == 2

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_no_urls(self, mock_run):
        """Should handle issues without URLs."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            [
                {"body": "No URLs here"},
            ]
        )
        mock_run.return_value = mock_result

        result = get_github_issues("owner/repo")
        assert len(result) == 0

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_normalizes_urls(self, mock_run):
        """Should normalize URLs (lowercase, remove trailing slash)."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            [
                {"body": "https://EXAMPLE.COM/call/"},
            ]
        )
        mock_run.return_value = mock_result

        result = get_github_issues("owner/repo")
        assert "https://example.com/call" in result

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_multiple_urls_per_issue(self, mock_run):
        """Should extract multiple URLs from single issue."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            [
                {"body": "URLs: https://example.com/1 and https://example.com/2"},
            ]
        )
        mock_run.return_value = mock_result

        result = get_github_issues("owner/repo")
        assert len(result) == 2

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_command_format(self, mock_run):
        """Should call gh with correct arguments."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([])
        mock_run.return_value = mock_result

        get_github_issues("owner/repo")

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "gh"
        assert call_args[1] == "issue"
        assert call_args[2] == "list"
        assert "--repo" in call_args
        assert "owner/repo" in call_args

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_gh_not_found(self, mock_run):
        """Should return empty set if gh command not found."""
        mock_run.side_effect = FileNotFoundError()
        result = get_github_issues("owner/repo")
        assert result == set()

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_timeout(self, mock_run):
        """Should return empty set on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)
        result = get_github_issues("owner/repo")
        assert result == set()

    @patch("discover.github.subprocess.run")
    def test_get_github_issues_error_return_code(self, mock_run):
        """Should return empty set on non-zero return code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = get_github_issues("owner/repo")
        assert result == set()


class TestCreateIssue:
    """Tests for create_issue function."""

    CANDIDATES = [
        {
            "url": "https://example.com/call1",
            "conference": "IJCAI",
            "year": 2026,
            "role": "Reviewer",
            "matched_keywords": ["reviewer", "call"],
        },
        {
            "url": "https://example.com/call2",
            "conference": "AAAI",
            "year": 2026,
            "role": "PC",
            "matched_keywords": ["pc member"],
        },
    ]

    def test_create_issue_empty_candidates(self):
        """Should return False for empty candidate list."""
        result = create_issue([], "owner/repo")
        assert result is False

    def test_create_issue_empty_repo(self):
        """Should return False and skip when repo is empty."""
        result = create_issue(self.CANDIDATES, "")
        assert result is False

    def test_create_issue_dry_run(self):
        """Should print candidates and return True in dry-run mode."""
        result = create_issue(self.CANDIDATES, "owner/repo", dry_run=True)
        assert result is True

    @patch("discover.github.subprocess.run")
    def test_create_issue_success(self, mock_run):
        """Should create a single issue for all candidates."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/owner/repo/issues/42\n"
        mock_run.return_value = mock_result

        result = create_issue(self.CANDIDATES, "owner/repo")
        assert result is True
        mock_run.assert_called_once()

    @patch("discover.github.subprocess.run")
    def test_create_issue_title_includes_count(self, mock_run):
        """Should include candidate count in title."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        create_issue(self.CANDIDATES, "owner/repo")

        call_args = mock_run.call_args[0][0]
        title_idx = call_args.index("--title") + 1
        title = call_args[title_idx]
        assert "2 new candidate(s)" in title

    @patch("discover.github.subprocess.run")
    def test_create_issue_body_has_table(self, mock_run):
        """Should include markdown table with all candidates."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        create_issue(self.CANDIDATES, "owner/repo")

        call_args = mock_run.call_args[0][0]
        body_idx = call_args.index("--body") + 1
        body = call_args[body_idx]
        assert "| Conference | Year | Role | URL | Keywords |" in body
        assert "IJCAI" in body
        assert "AAAI" in body
        assert "https://example.com/call1" in body
        assert "https://example.com/call2" in body

    @patch("discover.github.subprocess.run")
    def test_create_issue_body_has_per_candidate_checklist(self, mock_run):
        """Should include per-candidate verification checklist."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        create_issue(self.CANDIDATES, "owner/repo")

        call_args = mock_run.call_args[0][0]
        body_idx = call_args.index("--body") + 1
        body = call_args[body_idx]
        assert "Verification Checklist" in body
        assert "- [ ] **IJCAI 2026** (Reviewer):" in body
        assert "- [ ] **AAAI 2026** (PC):" in body

    @patch("discover.github.subprocess.run")
    def test_create_issue_uses_candidate_label(self, mock_run):
        """Should use 'candidate' label."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        create_issue(self.CANDIDATES, "owner/repo")

        call_args = mock_run.call_args[0][0]
        assert "--label" in call_args
        label_idx = call_args.index("--label") + 1
        assert call_args[label_idx] == "candidate"

    @patch("discover.github.subprocess.run")
    def test_create_issue_failure(self, mock_run):
        """Should return False on failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Not Found"
        mock_run.return_value = mock_result

        result = create_issue(self.CANDIDATES, "owner/repo")
        assert result is False

    @patch("discover.github.subprocess.run")
    def test_create_issue_gh_not_found(self, mock_run):
        """Should return False if gh command not found."""
        mock_run.side_effect = FileNotFoundError()
        result = create_issue(self.CANDIDATES, "owner/repo")
        assert result is False

    @patch("discover.github.subprocess.run")
    def test_create_issue_timeout(self, mock_run):
        """Should return False on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)
        result = create_issue(self.CANDIDATES, "owner/repo")
        assert result is False

    @patch("discover.github.subprocess.run")
    def test_create_issue_single_candidate(self, mock_run):
        """Should work with a single candidate."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = create_issue([self.CANDIDATES[0]], "owner/repo")
        assert result is True

        call_args = mock_run.call_args[0][0]
        title_idx = call_args.index("--title") + 1
        assert "1 new candidate(s)" in call_args[title_idx]


class TestFormatCandidateRow:
    """Tests for _format_candidate_row function."""

    def test_basic_row(self):
        candidate = {
            "conference": "IJCAI",
            "year": 2026,
            "role": "Reviewer",
            "url": "https://example.com/call",
            "matched_keywords": ["reviewer", "call"],
        }
        row = _format_candidate_row(candidate)
        assert (
            "| IJCAI | 2026 | Reviewer | https://example.com/call | reviewer, call |"
            == row
        )

    def test_missing_fields_use_defaults(self):
        candidate = {"url": "https://example.com/call"}
        row = _format_candidate_row(candidate)
        assert "Unknown" in row
        assert "Reviewer" in row

    def test_keywords_truncated_to_three(self):
        candidate = {
            "url": "https://example.com",
            "matched_keywords": ["a", "b", "c", "d"],
        }
        row = _format_candidate_row(candidate)
        assert "a, b, c" in row
        assert "d" not in row


class TestFormatCandidateChecklist:
    """Tests for _format_candidate_checklist function."""

    def test_single_candidate(self):
        candidates = [
            {
                "conference": "IJCAI",
                "year": 2026,
                "role": "Reviewer",
                "url": "https://a.com",
            },
        ]
        result = _format_candidate_checklist(candidates)
        assert "- [ ] **IJCAI 2026** (Reviewer): https://a.com" == result

    def test_multiple_candidates(self):
        candidates = [
            {
                "conference": "IJCAI",
                "year": 2026,
                "role": "Reviewer",
                "url": "https://a.com",
            },
            {
                "conference": "AAAI",
                "year": 2026,
                "role": "PC Member",
                "url": "https://b.com",
            },
        ]
        result = _format_candidate_checklist(candidates)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "IJCAI" in lines[0]
        assert "AAAI" in lines[1]

    def test_empty_candidates(self):
        assert _format_candidate_checklist([]) == ""
