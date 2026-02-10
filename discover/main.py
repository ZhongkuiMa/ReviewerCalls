"""Content-focused reviewer call discovery system.

Clean 4-step pipeline orchestrator.
"""

from __future__ import annotations

import sys
import os
import datetime
import argparse
from dataclasses import dataclass

from discover import config
from discover.data import (
    load_confs,
    is_in_recruitment_window,
    write_to_calls_yaml,
)
from discover.pipeline import (
    step1_search_homepage,
    step2_explore_level1,
    step3_explore_level2,
    step4_analyze_content,
)
from discover.utils import load_current_urls, guess_year
from discover.github import create_issue, get_github_issues

_VALID_AREAS = ["AI", "CG", "CT", "DB", "DS", "HI", "MX", "NW", "SC", "SE"]
_VALID_RANKS = ["A", "B", "C"]


@dataclass
class DiscoveryArgs:
    """Container for parsed and validated discovery arguments.

    :ivar conference: Conference short name filter (e.g., 'IJCAI', 'AAAI')
    :ivar rank: CCF rank filter (A, B, or C)
    :ivar area: Area code filter (e.g., AI, SE, SC)
    :ivar limit: Maximum number of conferences to search
    :ivar max_links: Maximum links to explore from homepage
    :ivar dry_run: Dry run mode (skip file writes and GitHub operations)
    :ivar search_provider: Search provider ('duckduckgo' or 'serper')
    :ivar serper_key: API key for Serper provider
    :ivar repo: GitHub repository in 'owner/repo' format
    :ivar date_range: Search date range filter ('d', 'w', 'm', 'y', or None)
    """

    conference: str | None = None
    rank: str | None = None
    area: str | None = None
    limit: int | None = None
    max_links: int = 15
    dry_run: bool = False
    search_provider: str = "duckduckgo"
    serper_key: str = ""
    repo: str = ""
    date_range: str | None = "m"


def _validate_args(args: argparse.Namespace) -> None:
    """Validate parsed command-line arguments.

    :param args: Parsed arguments from argparse
    :raises SystemExit: If validation fails
    """
    if args.rank is not None:
        rank_upper = args.rank.upper()
        if rank_upper not in _VALID_RANKS:
            print(
                f"Error: Invalid rank '{args.rank}'. "
                f"Valid options: {', '.join(_VALID_RANKS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        args.rank = rank_upper

    if args.area is not None:
        area_upper = args.area.upper()
        if area_upper not in _VALID_AREAS:
            print(
                f"Error: Invalid area '{args.area}'. "
                f"Valid options: {', '.join(_VALID_AREAS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        args.area = area_upper

    if args.conference is not None:
        args.conference = args.conference.upper()

    if args.limit is not None and args.limit <= 0:
        print(
            f"Error: Invalid limit '{args.limit}'. Must be a positive integer.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.max_links <= 0:
        print(
            f"Error: Invalid max_links '{args.max_links}'. Must be a positive integer.",
            file=sys.stderr,
        )
        sys.exit(1)


def _create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    :return: Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Discover reviewer calls for academic conferences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Valid area codes:
  {", ".join(_VALID_AREAS)}

Valid CCF ranks:
  {", ".join(_VALID_RANKS)}

Examples:
  # Search all AI conferences with rank A
  python -m discover --area AI --rank A

  # Search specific conference
  python -m discover --conference IJCAI

  # Dry run (no writes, no GitHub ops)
  python -m discover --dry-run

  # Initialize database (search past year)
  python -m discover --init --rank A

  # Use Serper search provider
  python -m discover --search-provider serper --serper-key YOUR_KEY
""",
    )

    parser.add_argument(
        "--conference",
        metavar="NAME",
        help="Filter by conference short name (e.g., IJCAI, AAAI)",
    )

    parser.add_argument(
        "--rank",
        metavar="RANK",
        help=f"Filter by CCF rank ({', '.join(_VALID_RANKS)})",
    )

    parser.add_argument(
        "--area",
        metavar="CODE",
        help=f"Filter by area code ({', '.join(_VALID_AREAS)})",
    )

    parser.add_argument(
        "--limit",
        metavar="N",
        type=int,
        help="Maximum number of conferences to search",
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize database: search past year (overrides --date-range to 'y')",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (skip file writes and GitHub operations)",
    )

    parser.add_argument(
        "--max-links",
        metavar="N",
        type=int,
        default=15,
        help="Maximum links to explore from homepage (default: 15)",
    )

    parser.add_argument(
        "--search-provider",
        choices=["duckduckgo", "serper"],
        default="duckduckgo",
        help="Search provider (default: duckduckgo)",
    )

    parser.add_argument(
        "--serper-key",
        default="",
        help="API key for Serper search provider",
    )

    parser.add_argument(
        "--repo",
        default="",
        help="GitHub repository in 'owner/repo' format (for issue operations)",
    )

    parser.add_argument(
        "--date-range",
        choices=["d", "w", "m", "y", "none"],
        default="m",
        help="Search date range filter (default: m)",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> DiscoveryArgs:
    """Parse and validate command-line arguments.

    :param argv: Argument list to parse (defaults to sys.argv)
    :return: Validated DiscoveryArgs instance
    :raises SystemExit: If arguments are invalid
    """
    parser = _create_parser()
    args = parser.parse_args(argv)
    _validate_args(args)

    date_range = args.date_range
    if args.init:
        date_range = "y"
    if date_range == "none":
        date_range = None

    return DiscoveryArgs(
        conference=args.conference,
        rank=args.rank,
        area=args.area,
        limit=args.limit,
        max_links=args.max_links,
        dry_run=args.dry_run,
        search_provider=args.search_provider,
        serper_key=args.serper_key,
        repo=args.repo,
        date_range=date_range,
    )


def discover_conference(
    conf: dict,
    year: int,
    known_urls: set[str],
    *,
    max_links: int = 15,
    search_provider: str = "duckduckgo",
    serper_key: str = "",
    date_range: str = "m",
) -> list[dict]:
    """Main discovery pipeline for a single conference.

    :param conf: Conference dictionary
    :param year: Target year
    :param known_urls: Set of known URLs to skip
    :param max_links: Maximum links to explore from homepage
    :param search_provider: Search provider ('duckduckgo' or 'serper')
    :param serper_key: API key for Serper provider
    :param date_range: Date range filter
    :return: List of candidate dictionaries
    """
    print(f"\n{conf['short']} {year} ({conf['domain']})")

    homepage, reviewer_links = step1_search_homepage(
        conf,
        year,
        search_provider=search_provider,
        serper_key=serper_key,
        date_range=date_range,
    )
    if not homepage:
        print("  Skipped: No homepage found")
        return []

    level2_links = step2_explore_level1(
        homepage, conf["domain"], conf["short"], max_links
    )
    if not level2_links:
        print("  Warning: No level 2 links found, will analyze homepage only")

    if reviewer_links:
        level2_links.extend(reviewer_links)
        print(
            f"  Added {len(reviewer_links)} reviewer-specific search results to exploration"
        )

    level3_links = []
    if level2_links:
        level3_links = step3_explore_level2(level2_links, conf["domain"], conf["short"])
        if not level3_links:
            print("  Warning: No level 3 links, using level 1+2 only")
    else:
        print("  [3/4] Skipped: No level 2 links to explore")

    all_links = [{"url": homepage, "text": "Homepage"}] + level2_links + level3_links

    unique_links = _deduplicate_links(all_links)

    print(
        f"  Total pages: {len(unique_links)} (L1: 1, L2: {len(level2_links)}, L3: {len(level3_links)})"
    )

    candidates = step4_analyze_content(unique_links, conf, year, known_urls)

    print(f"  Complete: {len(candidates)} candidates found")
    return candidates


def _deduplicate_links(links: list[dict]) -> list[dict]:
    """Deduplicate links by URL.

    :param links: List of link dictionaries
    :return: Deduplicated list
    """
    seen = set()
    unique = []
    for link in links:
        if link["url"] not in seen:
            unique.append(link)
            seen.add(link["url"])
    return unique


def main() -> int:
    """Main entry point for discovery script.

    :return: Exit code (0 for success)
    """
    args = parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    conf_path = os.path.join(repo_root, config.CONFERENCES_FILE)
    calls_path = os.path.join(repo_root, config.CALLS_FILE)

    conferences = load_confs(conf_path)
    known_urls = load_current_urls(calls_path)
    issue_urls = get_github_issues(args.repo, args.dry_run)
    all_known_urls = known_urls | issue_urls

    print(f"Loaded: {len(conferences)} conferences, {len(all_known_urls)} known URLs")

    today = datetime.date.today()
    year = guess_year()

    conferences = [c for c in conferences if is_in_recruitment_window(c, today)]
    conferences = _apply_filters(conferences, args)

    print(f"Searching: {len(conferences)} conferences (year {year})")

    all_candidates = []
    for i, conf in enumerate(conferences, 1):
        print(f"\n[{i}/{len(conferences)}]", end=" ")
        try:
            candidates = discover_conference(
                conf,
                year,
                all_known_urls,
                max_links=args.max_links,
                search_provider=args.search_provider,
                serper_key=args.serper_key,
                date_range=args.date_range,
            )
            all_candidates.extend(candidates)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

    _print_summary(all_candidates, len(conferences))

    if all_candidates and not args.dry_run:
        print("\nWriting to calls.yaml...")
        written = write_to_calls_yaml(all_candidates, calls_path)
        print(f"Added {written} new entries (backup: {calls_path}.backup)")
    elif all_candidates and args.dry_run:
        print(f"\n[DRY-RUN] Would add {len(all_candidates)} entries")

    if all_candidates:
        create_issue(all_candidates, args.repo, args.dry_run)

    return 0


def _apply_filters(conferences: list, args: DiscoveryArgs) -> list:
    """Apply user-specified filters.

    :param conferences: List of conference dicts
    :param args: Validated discovery arguments (values already uppercased)
    :return: Filtered list
    """
    if args.conference:
        conferences = [c for c in conferences if c["short"].upper() == args.conference]
    if args.rank:
        conferences = [c for c in conferences if c["rank"]["ccf"] == args.rank]
    if args.area:
        conferences = [c for c in conferences if c["area"] == args.area]
    if args.limit:
        conferences = conferences[: args.limit]
    return conferences


def _print_summary(candidates: list, num_confs: int):
    """Print discovery summary.

    :param candidates: List of candidate dicts
    :param num_confs: Number of conferences searched
    """
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(candidates)} candidates from {num_confs} conferences")
    print(f"{'=' * 60}")

    if candidates:
        for i, c in enumerate(candidates, 1):
            kws = ", ".join(c.get("matched_keywords", [])[:3])
            print(f"{i}. {c['conference']} {c['year']} | {c['role']} | {kws}")
            print(f"   {c['url']}")
