"""Main validation pipeline."""

from __future__ import annotations

import argparse
import datetime
import logging
import os
from pathlib import Path

import yaml

from discover.data import load_calls, write_yaml, backup_file
from validate.client import OllamaClient
from validate.config import load_config
from validate.fetcher import fetch_page_text
from validate.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


def setup_logging(args: argparse.Namespace) -> None:
    """Configure logging based on arguments.

    :param args: Parsed command line arguments with quiet and log_level
    """
    if args.quiet:
        log_level = logging.ERROR
    else:
        log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=log_level, format="%(levelname).1s %(name)s %(message)s")


def validate_entry(
    entry: dict,
    client: OllamaClient,
    max_chars: int,
) -> dict:
    """Validate a single call entry.

    :param entry: Call entry with url, conference, year, role, label
    :param client: OllamaClient instance
    :param max_chars: Max chars to send to LLM
    :returns: Result dict with status, reason
    """
    url = entry.get("url", "")
    content, fetch_status = fetch_page_text(url, max_chars)

    result = {
        "url": url,
        "conference": entry.get("conference", ""),
        "year": entry.get("year", ""),
        "role": entry.get("role", ""),
        "label": entry.get("label", "Main"),
        "fetch_status": fetch_status,
        "reason": "",
        "status": "skipped",
    }

    if fetch_status != "ok":
        result["reason"] = f"Fetch {fetch_status}"
        return result

    llm_result = client.extract(SYSTEM_PROMPT, build_user_prompt(entry, content))
    if llm_result is None:
        result["status"] = "error"
        result["reason"] = "LLM error"
        return result

    answer = llm_result.get("answer", "").lower().strip()
    reason = llm_result.get("reason", "")

    result["reason"] = reason

    if answer == "yes":
        result["status"] = "valid"
    elif answer == "no":
        result["status"] = "invalid"
    else:
        result["status"] = "error"
        result["reason"] = f"Invalid LLM response: {answer}"

    return result


def print_result(result: dict, index: int, total: int, quiet: bool = False) -> None:
    """Log validation result for one entry.

    :param result: Result dict from validate_entry
    :param index: Entry number (1-based)
    :param total: Total entries
    :param quiet: Suppress output
    """
    if quiet:
        return

    logger.info(
        "[%d/%d] %s %s . %s . %s",
        index,
        total,
        result["conference"],
        result["year"],
        result["role"],
        result["label"],
    )
    logger.info("  URL: %s", result["url"])

    if result["fetch_status"] != "ok":
        logger.info("  Fetch: %s", result["fetch_status"])
        return

    if result["status"] == "error":
        logger.error("  Error: %s", result["reason"])
    else:
        reason = result.get("reason", "")
        if reason:
            logger.info("  Reason: %s", reason)

        if result["status"] == "valid":
            logger.info("  -> VALID")
        elif result["status"] == "invalid":
            logger.info("  -> INVALID")


def apply_results(
    results: list[dict],
    calls_path: str,
    rejected_urls_path: str,
    quiet: bool = False,
) -> tuple[int, int]:
    """Apply validation results to YAML files.

    Updates calls.yaml confirmed field and moves invalid entries to rejected_urls.yaml.

    :param results: Validation results list
    :param calls_path: Path to calls.yaml
    :param rejected_urls_path: Path to rejected_urls.yaml
    :param quiet: Suppress output
    :returns: Tuple of (valid_count, invalid_count)
    """
    valid_urls = {r["url"] for r in results if r["status"] == "valid"}
    invalid_results = {r["url"]: r for r in results if r["status"] == "invalid"}

    if not valid_urls and not invalid_results:
        logger.info("No valid or invalid entries to update")
        return (0, 0)

    backup_file(calls_path)
    if os.path.exists(rejected_urls_path):
        backup_file(rejected_urls_path)

    with open(calls_path) as f:
        calls_data = yaml.safe_load(f) or {}

    calls = calls_data.get("calls", [])
    valid_count = 0
    invalid_count = 0

    new_calls = []
    for call in calls:
        if "urls" in call:
            new_urls = []
            for url_obj in call["urls"]:
                url = url_obj.get("url")
                if url in valid_urls:
                    call["confirmed"] = True
                    valid_count += 1
                    new_urls.append(url_obj)
                elif url not in invalid_results:
                    new_urls.append(url_obj)
                else:
                    invalid_count += 1

            if new_urls:
                call["urls"] = new_urls
                new_calls.append(call)
        else:
            url = call.get("url")
            if url in valid_urls:
                call["confirmed"] = True
                valid_count += 1
                new_calls.append(call)
            elif url not in invalid_results:
                new_calls.append(call)
            else:
                invalid_count += 1

    calls_data["calls"] = new_calls

    calls_header = (
        "# Verified reviewer self-nomination calls.\n"
        "# Manually maintained. PRs welcome after Issue verification.\n"
        "#\n"
        "# IMPORTANT: Entries MUST be ordered by date (NEWEST first, descending)\n"
        "#\n"
        "# Fields:\n"
        "#   url: Official self-nomination page URL (PRIMARY KEY)\n"
        "#   conference: Conference short name (match data/conferences.yaml)\n"
        "#   year: Conference year\n"
        "#   role: Reviewer, External Reviewer, PC, SPC, AC, SAC, AEC, Emergency Reviewer\n"
        "#   date: Web page creation date (YYYY-MM-DD)\n"
        "#   confirmed: Boolean, true=verified by human, false=auto-added pending review\n"
        "#   label: URL label (Main, Workshop, Industry, Shadow/Junior)\n"
        "#   round: Optional, Round identifier for multi-round conferences\n"
        "\n"
    )
    write_yaml(calls_path, calls_data, calls_header)

    if invalid_count > 0:
        try:
            with open(rejected_urls_path) as f:
                rejected_data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            rejected_data = {}

        rejected_list = rejected_data.get("rejected_urls", [])
        today = datetime.date.today().isoformat()

        existing_urls = {entry.get("url") for entry in rejected_list}
        for url in invalid_results.keys():
            if url not in existing_urls:
                rejected_list.append({"url": url, "date": today})

        rejected_data["rejected_urls"] = rejected_list

        rejected_header = (
            "# False positive URLs (should not be added to calls.yaml)\n"
            "# Entries older than 1 month are auto-cleaned during discovery\n"
            "# Format: url, date (YYYY-MM-DD)\n"
            "\n"
        )
        write_yaml(rejected_urls_path, rejected_data, rejected_header)

    if not quiet:
        if valid_count > 0:
            logger.info("Updated %d entries to confirmed=true", valid_count)
        if invalid_count > 0:
            logger.info(
                "Moved %d false positive(s) to rejected_urls.yaml", invalid_count
            )

    return (valid_count, invalid_count)


def run_validation(args: argparse.Namespace) -> int:
    """Main validation pipeline.

    :param args: Parsed command line arguments
    :returns: Exit code (0 for success)
    """
    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1

    calls_path = "data/calls.yaml"
    try:
        calls = load_calls(calls_path)
    except FileNotFoundError:
        logger.error("File not found: %s", calls_path)
        return 1

    entries = []
    for entry in calls:
        if entry.get("confirmed", False):
            continue

        if "urls" in entry:
            for url_obj in entry["urls"]:
                entry_copy = entry.copy()
                entry_copy["url"] = url_obj["url"]
                entry_copy["label"] = url_obj.get("label", "Main")
                entries.append(entry_copy)
        elif "url" in entry:
            entries.append(entry)

    if not entries:
        logger.info("No unconfirmed calls found in %s", calls_path)
        return 0

    logger.info("ReviewerCalls Validator - %d call(s)", len(entries))

    client = OllamaClient(config)

    if not client.health_check():
        return 1

    max_chars = config.get("validation", {}).get("max_content_chars", 6000)
    results = []
    for i, entry in enumerate(entries, 1):
        result = validate_entry(entry, client, max_chars)
        results.append(result)
        print_result(result, i, len(entries), quiet=args.quiet)

    if not args.quiet:
        logger.info("-" * 50)

    valid = sum(1 for r in results if r["status"] == "valid")
    invalid = sum(1 for r in results if r["status"] == "invalid")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    summary = f"Summary: {valid} valid . {invalid} invalid"
    if skipped:
        summary += f" . {skipped} skipped"
    if errors:
        summary += f" . {errors} errors"

    logger.info(summary)

    if not args.dry_run and (valid > 0 or invalid > 0):
        repo_root = Path(__file__).parent.parent
        apply_results(
            results,
            str(repo_root / "data/calls.yaml"),
            str(repo_root / "data/rejected_urls.yaml"),
            quiet=args.quiet,
        )
    elif args.dry_run:
        logger.info("Dry-run mode - no files written")

    return 0
