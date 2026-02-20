"""Data loading and persistence for discovery."""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any

import yaml
import shutil

from discover import config
from discover.utils import normalize_url

logger = logging.getLogger(__name__)


def read_yaml(path: str) -> dict[str, Any]:
    """Read and parse YAML file.

    :param path: Path to YAML file
    :return: Parsed YAML data as dictionary
    :raises FileNotFoundError: If file doesn't exist
    """
    with open(path) as f:
        return yaml.safe_load(f)


def write_yaml(
    path: str,
    data: dict[str, Any],
    header: str | None = None,
) -> None:
    """Write data to YAML file with optional header.

    :param path: Path to YAML file
    :param data: Data to write
    :param header: Optional header comment to prepend
    """
    with open(path, "w") as f:
        if header:
            f.write(header)
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )


def backup_file(path: str) -> str:
    """Create backup copy of file.

    :param path: Path to file to backup
    :return: Path to backup file
    """
    backup_path = path + ".backup"
    shutil.copy(path, backup_path)
    return backup_path


def load_calls(path: str) -> list[dict[str, Any]]:
    """Load verified calls from YAML file.

    :param path: Path to calls.yaml file
    :return: List of call dictionaries
    """
    data = read_yaml(path)
    return data.get("calls", [])


def extract_normalized_urls_from_calls(calls: list[dict[str, Any]]) -> set[str]:
    """Extract and normalize all URLs from calls list.

    Handles both old format (single 'url' field) and new format (array of URLs).

    :param calls: List of call dictionaries
    :return: Set of normalized URLs
    """
    urls = set()

    for call in calls:
        if "urls" in call:
            for url_obj in call["urls"]:
                urls.add(normalize_url(url_obj["url"]))
        elif "url" in call:
            urls.add(normalize_url(call["url"]))

    return urls


def load_rejected_urls(path: str) -> set[str]:
    """Load and normalize rejected URLs.

    :param path: Path to rejected_urls.yaml file
    :return: Set of normalized rejected URLs
    """
    try:
        data = read_yaml(path)
        rejected = data.get("rejected_urls", [])
        return {normalize_url(entry["url"]) for entry in rejected}
    except FileNotFoundError:
        return set()


def clean_rejected_urls(path: str) -> None:
    """Remove rejected URLs older than 1 month.

    :param path: Path to rejected_urls.yaml file
    """
    try:
        data = read_yaml(path)
        rejected = data.get("rejected_urls", [])

        today = datetime.date.today()
        one_month_ago = today - datetime.timedelta(days=30)

        kept = [
            entry
            for entry in rejected
            if datetime.date.fromisoformat(entry.get("date", "1900-01-01"))
            >= one_month_ago
        ]

        if len(kept) < len(rejected):
            data["rejected_urls"] = kept
            header = (
                "# False positive URLs that should not be added to calls.yaml\n"
                "# Entries older than 1 month are automatically cleaned during discovery\n"
                "# Format: url, date (YYYY-MM-DD)\n"
                "\n"
            )
            write_yaml(path, data, header)
    except FileNotFoundError:
        pass


def filter_new_candidates(
    candidates: list[dict[str, Any]],
    existing_urls: set[str],
    rejected_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter candidates to only new ones (not already in calls.yaml or rejected).

    :param candidates: List of candidate dictionaries
    :param existing_urls: Set of normalized URLs already in calls.yaml
    :param rejected_urls: Set of normalized rejected URLs (optional)
    :return: List of new candidates (not duplicates)
    """
    if rejected_urls is None:
        rejected_urls = set()

    new_entries = []

    _strip_keys = {
        "matched_keywords",
        "source",
        "title",
        "snippet",
        "final_score",
        "decision",
        "search_score",
        "graph_score",
        "content_score",
        "match_strength",
        "evidence_snippet",
    }
    for candidate in candidates:
        candidate_url = normalize_url(candidate["url"])
        if candidate_url not in existing_urls and candidate_url not in rejected_urls:
            candidate_clean = {
                k: v for k, v in candidate.items() if k not in _strip_keys
            }
            new_entries.append(candidate_clean)
            existing_urls.add(candidate_url)

    return new_entries


def merge_and_sort_calls(
    new_entries: list[dict[str, Any]],
    existing_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge new entries with existing calls and sort by date.

    :param new_entries: New candidate entries to add
    :param existing_calls: Existing calls from calls.yaml
    :return: Merged and sorted list (newest first)
    """
    all_calls = new_entries + existing_calls
    all_calls.sort(key=lambda x: x.get("date", "1900-01-01"), reverse=True)
    return all_calls


def load_confs(path: str) -> list[dict[str, Any]]:
    """Load conference definitions from YAML file.

    :param path: Path to conferences.yaml file
    :return: List of conference dictionaries
    """
    data = read_yaml(path)
    return data.get("conferences", [])


def is_in_recruitment_window(conf: dict[str, Any], today: datetime.date) -> bool:
    """Check if conference is in reviewer recruitment window.

    :param conf: Conference dictionary
    :param today: Current date
    :return: True if in recruitment window
    """
    if conf["short"].upper() in config.ROLLING_REVIEW_CONFERENCES:
        return True

    conf_dates = conf.get("conf_date", [0])
    if not isinstance(conf_dates, list):
        conf_dates = [conf_dates]

    if all(d == 0 for d in conf_dates):
        return True  # Unknown date: include

    current_month = today.month
    for conf_date in conf_dates:
        if conf_date == 0:
            continue
        active_months = [
            (conf_date - i - 1) % 12 + 1
            for i in range(
                config.RECRUITMENT_WINDOW_MIN_MONTHS,
                config.RECRUITMENT_WINDOW_MAX_MONTHS + 1,
            )
        ]
        if current_month in active_months:
            return True

    return False


def write_to_calls_yaml(candidates: list[dict[str, Any]], calls_path: str) -> int:
    """Write candidates to calls.yaml.

    :param candidates: List of candidate dictionaries
    :param calls_path: Path to calls.yaml file
    :return: Number of entries written
    """
    if not candidates:
        return 0

    backup_file(calls_path)

    # Load and clean rejected URLs
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    rejected_path = os.path.join(repo_root, config.REJECTED_URLS_FILE)
    rejected_urls = load_rejected_urls(rejected_path)
    clean_rejected_urls(rejected_path)

    data = read_yaml(calls_path)
    existing_calls = data.get("calls", [])

    existing_urls = extract_normalized_urls_from_calls(existing_calls)
    new_entries = filter_new_candidates(candidates, existing_urls, rejected_urls)

    if not new_entries:
        logger.info("    No new unique entries to add")
        return 0

    all_calls = merge_and_sort_calls(new_entries, existing_calls)
    data["calls"] = all_calls

    header = (
        "# Verified reviewer self-nomination calls.\n"
        "# Manually maintained. PRs welcome after Issue verification.\n"
        "#\n"
        "# ============================================\n"
        "# IMPORTANT: Entries MUST be ordered by date\n"
        "# Order: NEWEST date first (descending)\n"
        "# DO NOT change the ordering when editing!\n"
        "# ============================================\n"
        "#\n"
        "# Fields:\n"
        "#   url: Official self-nomination page URL (PRIMARY KEY)\n"
        "#   conference: Conference short name (must match data/conferences.yaml)\n"
        "#   year: Conference year\n"
        "#   role: One of: Reviewer, External Reviewer, PC, SPC, AC, SAC, AEC, Emergency Reviewer\n"
        "#   date: Web page creation/publication date (YYYY-MM-DD)\n"
        "#   confirmed: Boolean, true=verified by human, false=auto-added pending review\n"
        "#   label: URL label (Main, Workshop, Industry, Shadow/Junior)\n"
        "#   round: (Optional) Round identifier for multi-round conferences\n"
        "\n"
    )
    write_yaml(calls_path, data, header)

    return len(new_entries)
