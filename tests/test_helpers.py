"""Tests for utils.py utility functions."""

from datetime import date
from unittest.mock import patch
from discover.utils import guess_year, guess_role_from_keywords


class TestGuessYear:
    """Tests for guess_year function."""

    @patch("discover.utils.datetime.date")
    def test_guess_year_january(self, mock_date):
        """January should return current year."""
        mock_date.today.return_value = date(2026, 1, 15)
        assert guess_year() == 2026

    @patch("discover.utils.datetime.date")
    def test_guess_year_june(self, mock_date):
        """June should return current year."""
        mock_date.today.return_value = date(2026, 6, 30)
        assert guess_year() == 2026

    @patch("discover.utils.datetime.date")
    def test_guess_year_july(self, mock_date):
        """July should return next year."""
        mock_date.today.return_value = date(2026, 7, 1)
        assert guess_year() == 2027

    @patch("discover.utils.datetime.date")
    def test_guess_year_december(self, mock_date):
        """December should return next year."""
        mock_date.today.return_value = date(2026, 12, 31)
        assert guess_year() == 2027


class TestGuessRoleFromKeywords:
    """Tests for guess_role_from_keywords function."""

    def test_guess_role_pc_member(self):
        """Should detect PC member role."""
        keywords = ["call for pc member", "program committee"]
        assert guess_role_from_keywords(keywords) == "PC"

    def test_guess_role_area_chair(self):
        """Should detect Area Chair role."""
        keywords = ["area chair", "ac nomination"]
        assert guess_role_from_keywords(keywords) == "AC"

    def test_guess_role_senior_pc(self):
        """Should detect Senior PC role."""
        keywords = ["senior program committee", "spc recruitment"]
        assert guess_role_from_keywords(keywords) == "SPC"

    def test_guess_role_default_reviewer(self):
        """Should default to Reviewer if no specific role detected."""
        keywords = ["call for reviewers", "reviewer wanted"]
        assert guess_role_from_keywords(keywords) == "Reviewer"

    def test_guess_role_empty_list(self):
        """Empty keywords should default to Reviewer."""
        assert guess_role_from_keywords([]) == "Reviewer"

    def test_guess_role_case_insensitive(self):
        """Role detection should be case-insensitive."""
        keywords = ["PROGRAM COMMITTEE"]
        assert guess_role_from_keywords(keywords) == "PC"

    def test_guess_role_artifact_evaluation(self):
        """Should detect Artifact Evaluation Committee role."""
        keywords = ["artifact evaluation committee"]
        assert guess_role_from_keywords(keywords) == "AEC"

    def test_guess_role_meta_reviewer(self):
        """Should detect Meta Reviewer role."""
        keywords = ["meta reviewer", "meta review"]
        assert guess_role_from_keywords(keywords) == "Reviewer"
