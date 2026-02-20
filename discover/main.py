"""Content-focused reviewer call discovery system.

Clean 4-step pipeline orchestrator.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import os
import datetime
import argparse
from dataclasses import dataclass

from discover import config
from discover.data import (
    load_confs,
    load_rejected_urls,
    is_in_recruitment_window,
    write_to_calls_yaml,
)
from discover.pipeline import (
    step1_search_homepage,
    step4_analyze_content,
    explore_graph,
)
from discover.scoring import ScoredURL
from discover.batch import AsyncFetcher
from discover.utils import load_current_urls, guess_year
from discover.github import create_issue, get_github_issues

logger = logging.getLogger(__name__)

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
    eval_output: str | None = None


def _validate_args(args: argparse.Namespace) -> None:
    """Validate parsed command-line arguments.

    :param args: Parsed arguments from argparse
    :raises SystemExit: If validation fails
    """
    if args.rank is not None:
        rank_upper = args.rank.upper()
        if rank_upper not in _VALID_RANKS:
            logger.error(
                "Invalid rank '%s'. Valid options: %s",
                args.rank,
                ", ".join(_VALID_RANKS),
            )
            sys.exit(1)
        args.rank = rank_upper

    if args.area is not None:
        area_upper = args.area.upper()
        if area_upper not in _VALID_AREAS:
            logger.error(
                "Invalid area '%s'. Valid options: %s",
                args.area,
                ", ".join(_VALID_AREAS),
            )
            sys.exit(1)
        args.area = area_upper

    if args.conference is not None:
        args.conference = args.conference.upper()

    if args.limit is not None and args.limit <= 0:
        logger.error("Invalid limit '%s'. Must be a positive integer.", args.limit)
        sys.exit(1)

    if args.max_links <= 0:
        logger.error(
            "Invalid max_links '%s'. Must be a positive integer.", args.max_links
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

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode (sets log level to ERROR)",
    )

    parser.add_argument(
        "--eval",
        metavar="FILE",
        dest="eval_output",
        help="Export evaluation JSON with score breakdowns to FILE",
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

    # Configure logging
    if args.quiet:
        log_level = logging.ERROR
    else:
        log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format="%(levelname).1s %(name)s %(message)s",
    )

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
        eval_output=args.eval_output,
    )


async def discover_conference(
    conf: dict,
    year: int,
    known_urls: set[str],
    *,
    max_links: int = 15,
    search_provider: str = "duckduckgo",
    serper_key: str = "",
    date_range: str = "m",
    fetcher: AsyncFetcher | None = None,
) -> list[dict]:
    """Main discovery pipeline for a single conference.

    :param conf: Conference dictionary
    :param year: Target year
    :param known_urls: Set of known URLs to skip
    :param max_links: Maximum links to explore from homepage
    :param search_provider: Search provider ('duckduckgo' or 'serper')
    :param serper_key: API key for Serper provider
    :param date_range: Date range filter
    :param fetcher: Optional AsyncFetcher instance for shared session
    :return: List of candidate dictionaries
    """
    logger.info("%s %s (%s)", conf["short"], year, conf["domain"])

    homepage, reviewer_links = step1_search_homepage(
        conf,
        year,
        search_provider=search_provider,
        serper_key=serper_key,
        date_range=date_range,
    )
    if not homepage:
        logger.info("  Skipped: No homepage found")
        return []

    # Build seeds for score-driven BFS
    seeds = [
        ScoredURL(
            url=homepage,
            depth=0,
            search_score=6.0,
            source_type="search",
            text="Homepage",
        )
    ]
    for rl in reviewer_links:
        seeds.append(
            ScoredURL(
                url=rl["url"],
                depth=0,
                search_score=6.0,
                source_type="search",
                text=rl.get("text", ""),
                from_reviewer_search=True,
            )
        )

    explored = await explore_graph(
        seeds, conf["domain"], conf["short"], fetcher=fetcher
    )

    all_links = [
        {
            "url": su.url,
            "text": su.text,
            "from_reviewer_search": su.from_reviewer_search,
            "graph_score": su.graph_score,
            "search_score": su.search_score,
        }
        for su in explored
    ]

    unique_links = _deduplicate_links(all_links)

    logger.info(
        "  Total pages: %d (%d explored by BFS)",
        len(unique_links),
        len(explored),
    )

    candidates = await step4_analyze_content(
        unique_links, conf, year, known_urls, fetcher=fetcher
    )

    logger.info("  Complete: %d candidates found", len(candidates))
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


async def _run_discovery(args: DiscoveryArgs) -> int:
    """Async entry point for the discovery pipeline.

    :param args: Validated discovery arguments
    :return: Exit code (0 for success)
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    conf_path = os.path.join(repo_root, config.CONFERENCES_FILE)
    calls_path = os.path.join(repo_root, config.CALLS_FILE)

    rejected_path = os.path.join(repo_root, config.REJECTED_URLS_FILE)

    conferences = load_confs(conf_path)
    known_urls = load_current_urls(calls_path)
    rejected_urls = load_rejected_urls(rejected_path)
    issue_urls = get_github_issues(args.repo, args.dry_run)
    all_known_urls = known_urls | rejected_urls | issue_urls

    logger.info(
        "Loaded: %d conferences, %d known URLs, %d rejected URLs",
        len(conferences),
        len(known_urls | issue_urls),
        len(rejected_urls),
    )

    today = datetime.date.today()
    year = guess_year()

    conferences = [c for c in conferences if is_in_recruitment_window(c, today)]
    conferences = _apply_filters(conferences, args)

    logger.info("Searching: %d conferences (year %d)", len(conferences), year)

    all_candidates = []

    async with AsyncFetcher() as fetcher:
        for i, conf in enumerate(conferences, 1):
            logger.info("[%d/%d]", i, len(conferences))
            try:
                candidates = await discover_conference(
                    conf,
                    year,
                    all_known_urls,
                    max_links=args.max_links,
                    search_provider=args.search_provider,
                    serper_key=args.serper_key,
                    date_range=args.date_range,
                    fetcher=fetcher,
                )
                all_candidates.extend(candidates)
            except Exception as e:
                logger.error("Conference %s failed: %s", conf["short"], e)
                continue

    _print_summary(all_candidates, len(conferences))

    # Evaluation JSON export
    if args.eval_output:
        _export_eval(args.eval_output, all_candidates, len(conferences))

    if all_candidates and not args.dry_run:
        logger.info("Writing to calls.yaml...")
        written = write_to_calls_yaml(all_candidates, calls_path)
        logger.info("Added %d new entries (backup: %s.backup)", written, calls_path)
    elif all_candidates and args.dry_run:
        logger.info("[DRY-RUN] Would add %d entries", len(all_candidates))

    if all_candidates:
        create_issue(all_candidates, args.repo, args.dry_run)

    return 0


def main() -> int:
    """Main entry point for discovery script.

    :return: Exit code (0 for success)
    """
    args = parse_args()
    return asyncio.run(_run_discovery(args))


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
    logger.info("=" * 60)
    logger.info(
        "SUMMARY: %d candidates from %d conferences", len(candidates), num_confs
    )
    logger.info("=" * 60)

    if candidates:
        for i, c in enumerate(candidates, 1):
            score = c.get("final_score", 0)
            decision = c.get("decision", "?")
            kws = ", ".join(c.get("matched_keywords", [])[:3])
            logger.info(
                "%d. [%.1f %s] %s %s | %s | %s",
                i,
                score,
                decision,
                c["conference"],
                c["year"],
                c["role"],
                kws,
            )
            logger.info("   %s", c["url"])
            evidence = c.get("evidence_snippet", "")
            if evidence:
                logger.debug("   Evidence: %s", evidence[:120])


def _export_eval(path: str, candidates: list, num_confs: int) -> None:
    """Export evaluation JSON with score breakdowns.

    :param path: Output file path
    :param candidates: List of candidate dicts
    :param num_confs: Number of conferences searched
    """
    eval_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "conferences_searched": num_confs,
        "total_candidates": len(candidates),
        "candidates": [
            {
                "url": c["url"],
                "conference": c["conference"],
                "year": c["year"],
                "role": c["role"],
                "final_score": c.get("final_score", 0),
                "search_score": c.get("search_score", 0),
                "graph_score": c.get("graph_score", 0),
                "content_score": c.get("content_score", 0),
                "decision": c.get("decision", "unknown"),
                "match_strength": c.get("match_strength", ""),
                "matched_keywords": c.get("matched_keywords", []),
                "evidence_snippet": c.get("evidence_snippet", ""),
            }
            for c in candidates
        ],
    }
    with open(path, "w") as f:
        json.dump(eval_data, f, indent=2)
    logger.info("Evaluation JSON written to %s", path)
