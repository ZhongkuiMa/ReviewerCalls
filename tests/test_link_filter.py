"""Tests for filters.py link filtering utilities."""

from unittest.mock import patch
from discover.filters import (
    LinkFilterOptions,
    is_trusted_external_platform,
    filter_links,
)


class TestIsTrustedExternalPlatform:
    """Tests for is_trusted_external_platform function."""

    def test_trusted_github_pages_with_conference_name(self):
        """Should trust GitHub Pages if conference name in URL."""
        assert (
            is_trusted_external_platform(
                "https://ijcai2026.github.io/workshop", "ijcai"
            )
            is True
        )

    def test_trusted_github_pages_workshop_pattern(self):
        """Should trust GitHub Pages with workshop patterns."""
        assert (
            is_trusted_external_platform(
                "https://xai-workshop.github.io/", "conference"
            )
            is True
        )

    def test_trusted_github_pages_conference_year(self):
        """Should trust GitHub Pages with conference year."""
        assert (
            is_trusted_external_platform("https://example-iclr2026.github.io/", "iclr")
            is True
        )

    def test_trusted_github_pages_ai_topic(self):
        """Should trust GitHub Pages with AI topic patterns."""
        assert (
            is_trusted_external_platform(
                "https://agent-learning.github.io/", "conference"
            )
            is True
        )

    def test_untrusted_github_pages_random(self):
        """Should not trust random GitHub Pages without patterns."""
        assert (
            is_trusted_external_platform(
                "https://random-repo.github.io/page", "conference"
            )
            is False
        )

    def test_trusted_google_sites_with_conference_name(self):
        """Should trust Google Sites if conference name in URL."""
        assert (
            is_trusted_external_platform("https://sites.google.com/ijcai/form", "ijcai")
            is True
        )

    def test_trusted_google_sites_with_year(self):
        """Should trust Google Sites with year."""
        assert (
            is_trusted_external_platform(
                "https://sites.google.com/site/name2026", "conference"
            )
            is True
        )

    def test_untrusted_google_sites_no_pattern(self):
        """Should not trust Google Sites without conference/year."""
        assert (
            is_trusted_external_platform(
                "https://sites.google.com/site/random", "conference"
            )
            is False
        )

    def test_trusted_researchr(self):
        """Should always trust ResearchR."""
        assert (
            is_trusted_external_platform(
                "https://conf.researchr.org/track/ijcai-2026", "ijcai"
            )
            is True
        )

    def test_trusted_cspaper_forum_with_conference(self):
        """Should trust cspaper forum if conference-specific."""
        assert (
            is_trusted_external_platform(
                "https://forum.cspaper.org/cvpr2026/topic", "cvpr"
            )
            is True
        )

    def test_trusted_cspaper_forum_cvpr_iccv(self):
        """Should trust cspaper for CVPR and ICCV."""
        assert (
            is_trusted_external_platform(
                "https://forum.cspaper.org/cvpr2026/general", "cvpr"
            )
            is True
        )
        assert (
            is_trusted_external_platform(
                "https://forum.cspaper.org/iccv2026/general", "iccv"
            )
            is True
        )

    def test_untrusted_cspaper_forum_other(self):
        """Should not trust cspaper for non-CVPR/ICCV."""
        assert (
            is_trusted_external_platform("https://forum.cspaper.org/general", "ijcai")
            is False
        )

    def test_untrusted_random_domain(self):
        """Should not trust random domains."""
        assert (
            is_trusted_external_platform("https://random-site.com/page", "conference")
            is False
        )

    def test_case_insensitive_matching(self):
        """Should be case-insensitive."""
        assert (
            is_trusted_external_platform("https://IJCAI2026.GITHUB.IO/", "IJCAI")
            is True
        )


class TestLinkFilterOptions:
    """Tests for LinkFilterOptions dataclass."""

    def test_link_filter_options_defaults(self):
        """Should have correct defaults."""
        options = LinkFilterOptions(base_domain="example.com")
        assert options.base_domain == "example.com"
        assert options.conference_name == ""
        assert options.filter_useless is True
        assert options.filter_by_text is True
        assert options.filter_by_domain is True

    def test_link_filter_options_custom(self):
        """Should accept custom options."""
        options = LinkFilterOptions(
            base_domain="example.com",
            conference_name="IJCAI",
            filter_useless=False,
            filter_by_text=False,
        )
        assert options.base_domain == "example.com"
        assert options.conference_name == "IJCAI"
        assert options.filter_useless is False
        assert options.filter_by_text is False


class TestFilterLinks:
    """Tests for filter_links function."""

    @patch("discover.filters._validators.is_obviously_useless")
    @patch("discover.filters.should_skip_link_text")
    def test_filter_links_same_domain(self, mock_skip_text, mock_useless):
        """Should keep links from same domain."""
        mock_useless.return_value = False
        mock_skip_text.return_value = False

        links = [{"url": "https://example.com/page", "text": "Link"}]
        options = LinkFilterOptions(base_domain="example.com")
        result = filter_links(links, options)

        assert len(result) == 1

    @patch("discover.filters._validators.is_obviously_useless")
    @patch("discover.filters.should_skip_link_text")
    def test_filter_links_different_domain_untrusted(
        self, mock_skip_text, mock_useless
    ):
        """Should remove links from different untrusted domains."""
        mock_useless.return_value = False
        mock_skip_text.return_value = False

        links = [{"url": "https://other.com/page", "text": "Link"}]
        options = LinkFilterOptions(base_domain="example.com", conference_name="CONF")
        result = filter_links(links, options)

        assert len(result) == 0

    @patch("discover.filters._validators.is_obviously_useless")
    @patch("discover.filters.should_skip_link_text")
    def test_filter_links_trusted_external(self, mock_skip_text, mock_useless):
        """Should keep links from trusted external platforms."""
        mock_useless.return_value = False
        mock_skip_text.return_value = False

        links = [{"url": "https://conf.researchr.org/track", "text": "Link"}]
        options = LinkFilterOptions(base_domain="example.com")
        result = filter_links(links, options)

        assert len(result) == 1

    @patch("discover.filters._validators.is_obviously_useless")
    @patch("discover.filters.should_skip_link_text")
    def test_filter_links_useless_url(self, mock_skip_text, mock_useless):
        """Should remove obviously useless URLs."""
        mock_useless.return_value = True
        mock_skip_text.return_value = False

        links = [{"url": "https://example.com/about", "text": "Link"}]
        options = LinkFilterOptions(base_domain="example.com")
        result = filter_links(links, options)

        assert len(result) == 0

    @patch("discover.filters._validators.is_obviously_useless")
    @patch("discover.filters.should_skip_link_text")
    def test_filter_links_skip_text(self, mock_skip_text, mock_useless):
        """Should remove links with skip-worthy text."""
        mock_useless.return_value = False
        mock_skip_text.return_value = True

        links = [{"url": "https://example.com/page", "text": "About"}]
        options = LinkFilterOptions(base_domain="example.com")
        result = filter_links(links, options)

        assert len(result) == 0

    @patch("discover.filters._validators.is_obviously_useless")
    @patch("discover.filters.should_skip_link_text")
    def test_filter_links_disable_domain_filter(self, mock_skip_text, mock_useless):
        """Should keep all links when domain filtering disabled."""
        mock_useless.return_value = False
        mock_skip_text.return_value = False

        links = [{"url": "https://other.com/page", "text": "Link"}]
        options = LinkFilterOptions(base_domain="example.com", filter_by_domain=False)
        result = filter_links(links, options)

        assert len(result) == 1

    @patch("discover.filters._validators.is_obviously_useless")
    @patch("discover.filters.should_skip_link_text")
    def test_filter_links_multiple(self, mock_skip_text, mock_useless):
        """Should filter multiple links correctly."""
        mock_useless.side_effect = [False, True, False]
        mock_skip_text.return_value = False

        links = [
            {"url": "https://example.com/page1", "text": "Link1"},
            {"url": "https://example.com/page2", "text": "Link2"},
            {"url": "https://example.com/page3", "text": "Link3"},
        ]
        options = LinkFilterOptions(base_domain="example.com")
        result = filter_links(links, options)

        assert len(result) == 2
