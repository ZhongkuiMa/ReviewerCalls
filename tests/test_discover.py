"""Tests for discovery logic."""

from __future__ import annotations

import datetime

from discover import constants
from discover.utils import guess_year, guess_role_from_keywords
from discover.data import is_in_recruitment_window


def _match_keywords(text: str) -> list[str]:
    """Match STEP4 content keywords against text."""
    text_lower = text.lower()
    return [
        constants.STEP4_CONTENT_KEYWORDS[i]
        for i, pattern in enumerate(constants.KEYWORD_PATTERNS)
        if pattern.search(text_lower)
    ]


def test_match_keywords_positive():
    assert "self-nomination" in _match_keywords("Self-Nomination Form")
    assert "call for reviewers" in _match_keywords("Call for Reviewers open")
    assert "aec application" in _match_keywords("AEC Application")


def test_match_keywords_negative():
    assert _match_keywords("Regular Conference Page Submit your paper here") == []
    assert _match_keywords("") == []


def test_match_keywords_spacing_variations():
    """Test that keyword matching handles spacing variations."""
    for text in [
        "Self - Nomination Form",
        "Self-Nomination Form",
        "Self nomination Form",
    ]:
        matches = _match_keywords(text)
        assert any("self-nomination" in m or "self nomination" in m for m in matches), (
            f"Expected self-nomination match for '{text}', got: {matches}"
        )


def test_match_keywords_abbreviations():
    """Test that keyword matching handles standalone abbreviations."""
    assert _match_keywords("PC Member Call")
    assert _match_keywords("SPC Nomination")
    assert _match_keywords("AEC Member Application")


def test_match_keywords_verb_forms():
    """Test that keyword matching handles verb forms."""
    assert _match_keywords("Nominate yourself as reviewer")
    assert _match_keywords("Apply as reviewer for ICSE")


def test_match_keywords_real_world_examples():
    """Test with real-world examples."""
    assert _match_keywords("Self - Nomination for ICSE 2027 PC")
    assert _match_keywords("PC Member recruitment")
    assert _match_keywords("PC Nomination for ICSE 2027")


def test_match_keywords_workshops():
    """Test that workshop-specific keywords are matched."""
    assert _match_keywords("Workshop Reviewer Call")
    assert _match_keywords("Workshop PC Nomination")
    assert _match_keywords("Call for Workshop Reviewers - XAI4Science @ ICLR 2026")
    assert _match_keywords("Join Workshop Program Committee")
    assert _match_keywords("Workshop Area Chair Application")


def test_guess_role():
    assert (
        guess_role_from_keywords(_match_keywords("External Reviewer Call"))
        == "External Reviewer"
    )
    assert guess_role_from_keywords(_match_keywords("AEC Application")) == "AEC"
    assert (
        guess_role_from_keywords(_match_keywords("Artifact Evaluation Committee"))
        == "AEC"
    )
    assert guess_role_from_keywords(_match_keywords("PC Nomination")) == "PC"
    assert (
        guess_role_from_keywords(_match_keywords("Program Committee Nomination"))
        == "PC"
    )
    assert guess_role_from_keywords(_match_keywords("SPC Nomination")) == "SPC"
    assert (
        guess_role_from_keywords(_match_keywords("Reviewer Application")) == "Reviewer"
    )


def test_guess_year():
    year = guess_year()
    assert isinstance(year, int)
    assert year >= 2026


def test_recruitment_window_unknown_month():
    """Conferences with unknown conf_date should always be searched."""
    conf = {"short": "TEST", "conf_date": 0}
    assert is_in_recruitment_window(conf, datetime.date(2026, 1, 15))
    assert is_in_recruitment_window(conf, datetime.date(2026, 7, 15))


def test_recruitment_window_december_conf():
    """NeurIPS-like: conf_date=12, always in recruitment window (rolling review)."""
    conf = {"short": "NEURIPS", "conf_date": 12}
    assert is_in_recruitment_window(conf, datetime.date(2026, 1, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 6, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 7, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 8, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 12, 1))


def test_recruitment_window_february_conf():
    """AAAI-like: conf_date=2, recruitment should be Apr-Dec."""
    conf = {"short": "AAAI", "conf_date": 2}
    assert is_in_recruitment_window(conf, datetime.date(2025, 4, 1))
    assert is_in_recruitment_window(conf, datetime.date(2025, 5, 1))
    assert is_in_recruitment_window(conf, datetime.date(2025, 8, 1))
    assert is_in_recruitment_window(conf, datetime.date(2025, 9, 1))
    assert is_in_recruitment_window(conf, datetime.date(2025, 10, 1))
    assert is_in_recruitment_window(conf, datetime.date(2025, 11, 1))
    assert is_in_recruitment_window(conf, datetime.date(2025, 12, 1))
    assert not is_in_recruitment_window(conf, datetime.date(2026, 1, 1))
    assert not is_in_recruitment_window(conf, datetime.date(2026, 2, 1))
    assert not is_in_recruitment_window(conf, datetime.date(2026, 3, 1))


def test_recruitment_window_multi_round():
    """Multi-round conference (OOPSLA) active during any round window."""
    conf = {"short": "OOPSLA", "conf_date": [4, 10]}

    assert is_in_recruitment_window(conf, datetime.date(2026, 3, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 9, 1))
    assert is_in_recruitment_window(conf, datetime.date(2025, 11, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 5, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 1, 1))
    assert is_in_recruitment_window(conf, datetime.date(2026, 7, 1))


def test_match_keywords_high_value_terms():
    """Test high-value terms for AI conferences."""
    assert "reviewer invite" in _match_keywords("Reviewer Invite for AAAI 2026")
    assert "reviewer needed" in _match_keywords("Reviewer needed for ICML")
    assert "shadow reviewer" in _match_keywords("Shadow Reviewer Program")
    assert "review panel" in _match_keywords("Join our review panel")
    assert "meta-review" in _match_keywords("Meta-review duties for ICLR")


def test_match_keywords_chair_variants():
    """Test co-chair and chair recruitment keywords."""
    assert "co-chair" in _match_keywords("PC co-chair nomination")
    assert "cochair" in _match_keywords("Cochair Recruitment")
    assert _match_keywords("Chair Recruitment")
    assert _match_keywords("Chair Nomination Form")


def test_match_keywords_volunteer_variants():
    """Test volunteer-related keywords."""
    assert "volunteer as pc member" in _match_keywords("Volunteer as PC Member")
    assert "reviewer volunteer" in _match_keywords("Reviewer Volunteer Program")
    assert "pc volunteer" in _match_keywords("PC Volunteer Recruitment")
    assert "volunteer as reviewer" in _match_keywords("Volunteer as Reviewer")


def test_match_keywords_student_junior():
    """Test student/junior reviewer keywords."""
    assert "student reviewer" in _match_keywords("Student Reviewer Program")
    assert "junior reviewer" in _match_keywords("Junior Reviewer Initiative")


def test_match_keywords_shadow_pc():
    """Test shadow PC variant."""
    matches = _match_keywords("Shadow PC Volunteer")
    assert "shadow pc" in matches or "shadow reviewer" in matches


def test_false_positive_url_dynamic_year():
    """Test year filtering uses current year dynamically."""
    from discover.validators import is_false_positive_url

    current_year = datetime.date.today().year

    assert not is_false_positive_url(f"https://example.com/{current_year}/reviewer/")
    assert not is_false_positive_url(
        f"https://example.com/{current_year - 1}/reviewer/"
    )

    if current_year > 2024:
        assert is_false_positive_url("https://example.com/2022/reviewer/")
        assert is_false_positive_url("https://example.com/2023/reviewer/")


def test_external_platform_whitelisting():
    """Test trusted external platforms are allowed."""
    from discover.filters import is_trusted_external_platform

    assert is_trusted_external_platform("https://workshop.github.io/iclr2026/", "ICLR")
    assert is_trusted_external_platform("https://random-workshop.github.io/", "ICLR")
    assert not is_trusted_external_platform("https://random-blog.github.io/", "ICLR")
    assert is_trusted_external_platform(
        "https://sites.google.com/view/iclr-2026-workshop/", "ICLR"
    )
    assert is_trusted_external_platform(
        "https://conf.researchr.org/track/icse-2026/", "ICSE"
    )
    assert is_trusted_external_platform("https://forum.cspaper.org/cvpr2026/", "CVPR")
    assert not is_trusted_external_platform("https://random-site.com/", "ICLR")


def test_keyword_filtering_positive():
    """Test keyword filtering with positive examples."""
    from discover.filters import should_explore_link, has_filter_keyword

    positive_examples = [
        {"url": "https://icaps26.org/call-for-reviewers", "text": "Join PC"},
        {"url": "https://kdd2026.kdd.org/pc-nomination/", "text": "PC"},
        {"url": "https://icaps26.org/calls/shadow_pc", "text": "Shadow PC"},
        {"url": "https://2026.ijcai.org/workshop/", "text": "Workshop"},
        {"url": "https://example.org/committee/", "text": "Committee"},
        {"url": "https://example.org/page", "text": "Call for Reviewers"},
    ]

    for link in positive_examples:
        assert should_explore_link(link), f"Expected to explore {link['url']}"
        assert has_filter_keyword(link["url"]) or has_filter_keyword(
            link.get("text", "")
        ), f"Expected keyword in {link}"


def test_keyword_filtering_negative():
    """Test keyword filtering with negative examples."""
    from discover.filters import should_explore_link

    negative_examples = [
        {"url": "https://icaps26.org/venue/hotel", "text": "Hotel"},
        {"url": "https://kdd2026.kdd.org/about/", "text": "About"},
        {"url": "https://example.org/news/", "text": "Latest News"},
        {"url": "https://example.org/travel/", "text": "Travel Information"},
        {"url": "https://example.org/sponsors/", "text": "Our Sponsors"},
    ]

    for link in negative_examples:
        assert not should_explore_link(link), f"Expected NOT to explore {link['url']}"


def test_keyword_filtering_examples():
    """Test keyword filtering on real examples."""
    from discover.filters import should_explore_link

    examples_positive = [
        {"url": "https://icaps26.org/calls/shadow_pc", "text": "Shadow PC"},
        {"url": "https://kdd2026.kdd.org/call-for-reviewers/", "text": "Join"},
        {"url": "https://2026.ijcai.org/call-for-pc-members/", "text": "PC"},
    ]

    for ex in examples_positive:
        assert should_explore_link(ex), f"Expected to explore {ex['url']}"

    examples_negative = [
        {"url": "https://icaps26.org/venue/hotel", "text": "Hotel"},
        {"url": "https://kdd2026.kdd.org/about/", "text": "About"},
    ]

    for ex in examples_negative:
        assert not should_explore_link(ex), f"Expected NOT to explore {ex['url']}"


def test_has_filter_keyword():
    """Test keyword detection."""
    from discover.filters import has_filter_keyword

    assert has_filter_keyword("/call-for-reviewers/")
    assert has_filter_keyword("/pc-nomination/")
    assert has_filter_keyword("/workshop/")
    assert has_filter_keyword("Join the Program Committee")
    assert has_filter_keyword("Call for Reviewers")

    assert not has_filter_keyword("/about/")
    assert not has_filter_keyword("/venue/")
    assert not has_filter_keyword("General Information")


def test_filter_keywords_path():
    """Test that path keywords are detected correctly."""
    from discover.filters import has_filter_keyword

    test_cases = [
        "/call/",
        "/calls/",
        "/reviewer/",
        "/reviewers/",
        "/pc/",
        "/committee/",
        "/nomination/",
        "/workshop/",
        "/workshops/",
        "/call-for-reviewers/",
        "/pc-nomination/",
    ]

    for path in test_cases:
        assert has_filter_keyword(path), f"Expected keyword in {path}"


def test_filter_keywords_text():
    """Test that text keywords are detected correctly."""
    from discover.filters import has_filter_keyword

    test_cases = [
        "Call for Reviewer",
        "Call for PC",
        "PC Nomination",
        "Shadow PC",
        "Become a Reviewer",
        "Join the Committee",
        "Workshop Reviewers",
    ]

    for text in test_cases:
        assert has_filter_keyword(text), f"Expected keyword in '{text}'"


def test_stop_words_filtering():
    """Test that stop-words are filtered correctly."""
    from discover.filters import should_explore_link

    link = {"url": "https://example.org/venue/", "text": ""}
    assert not should_explore_link(link), "Expected NOT to explore venue page"

    link = {"url": "https://example.org/venue/pc-nomination/", "text": ""}
    assert should_explore_link(link), (
        "Expected to explore PC nomination despite venue in path"
    )


def test_conference_page_scoring():
    """Test conference page validation scoring."""
    from discover.pipeline import _score_conference_page

    conf = {
        "short": "ICAPS",
        "name": "International Conference on Automated Planning and Scheduling",
        "domain": "icaps-conference.org",
    }
    year = 2026

    result = {
        "url": "https://icaps26.icaps-conference.org/",
        "title": "ICAPS 2026 - International Conference",
        "snippet": "The 36th International Conference on Automated Planning and Scheduling",
    }
    score = _score_conference_page(result, conf, year)
    assert score >= 15, f"Expected high score for perfect match, got {score}"

    result = {
        "url": "https://icaps-conference.org/2026/",
        "title": "ICAPS 2026 Homepage",
        "snippet": "Conference information",
    }
    score = _score_conference_page(result, conf, year)
    assert 10 <= score <= 22, f"Expected medium-high score, got {score}"

    result = {
        "url": "https://example.com/random",
        "title": "Random Page",
        "snippet": "Not related to conference",
    }
    score = _score_conference_page(result, conf, year)
    assert score == 0, f"Expected zero score for non-match, got {score}"


def test_conference_page_validation_flow():
    """Test that conference page validation checks abbr in URL and title/content."""
    from discover.pipeline import _score_conference_page

    conf = {
        "short": "NeurIPS",
        "name": "Neural Information Processing Systems",
        "domain": "neurips.cc",
    }
    year = 2026

    result = {
        "url": "https://neurips.cc/Conferences/2026",
        "title": "Conference",
        "snippet": "",
    }
    assert _score_conference_page(result, conf, year) > 0

    result = {"url": "https://example.com/conf", "title": "NeurIPS 2026", "snippet": ""}
    assert _score_conference_page(result, conf, year) > 0

    result = {
        "url": "https://example.com/conf",
        "title": "Conference",
        "snippet": "Neural Information Processing Systems 2026",
    }
    assert _score_conference_page(result, conf, year) > 0

    result = {
        "url": "https://example.com/random",
        "title": "Random",
        "snippet": "Nothing",
    }
    assert _score_conference_page(result, conf, year) == 0
