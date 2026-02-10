"""GitHub Issue creation with deduplication.

Uses ``gh`` CLI (available in GitHub Actions and locally if installed).
"""

from __future__ import annotations

import subprocess
import json
import re


def get_github_issues(repo: str, dry_run: bool = False) -> set[str]:
    """Fetch URLs from open GitHub issues labelled ``candidate``.

    :param repo: GitHub repository in format 'owner/repo'
    :param dry_run: Skip API call in dry-run mode
    :return: Set of URLs found in open issues
    """
    if not repo:
        return set()

    if dry_run:
        print(f"[INFO] Dry Run: Fetch existing issue URLs from {repo}")
        return set()

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--state",
                "open",
                "--label",
                "candidate",
                "--json",
                "body",
                "--limit",
                "500",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()

    if result.returncode != 0:
        return set()

    urls = set()
    for issue in json.loads(result.stdout):
        for match in re.finditer(r"https?://[^\s\)>]+", issue.get("body", "")):
            urls.add(match.group().lower().rstrip("/"))

    print(f"[INFO] Fetched {len(urls)} URLs from existing issues in {repo}")
    return urls


def _format_candidate_row(candidate: dict) -> str:
    """Format a single candidate as a markdown table row.

    :param candidate: Candidate dictionary
    :return: Markdown table row string
    """
    conf = candidate.get("conference", "Unknown")
    year = candidate.get("year", "Unknown")
    role = candidate.get("role", "Reviewer")
    url = candidate["url"]
    keywords = ", ".join(candidate.get("matched_keywords", [])[:3])
    return f"| {conf} | {year} | {role} | {url} | {keywords} |"


def _format_candidate_checklist(candidates: list[dict]) -> str:
    """Format per-candidate verification checklist.

    :param candidates: List of candidate dictionaries
    :return: Markdown checklist string
    """
    lines = []
    for c in candidates:
        conf = c.get("conference", "Unknown")
        year = c.get("year", "Unknown")
        role = c.get("role", "Reviewer")
        url = c["url"]
        lines.append(f"- [ ] **{conf} {year}** ({role}): {url}")
    return "\n".join(lines)


def create_issue(candidates: list[dict], repo: str, dry_run: bool = False) -> bool:
    """Create a single GitHub Issue listing all candidate reviewer calls.

    :param candidates: List of candidate dictionaries
    :param repo: GitHub repository in format 'owner/repo'
    :param dry_run: Skip actual issue creation in dry-run mode
    :return: True if issue was created, False otherwise
    """
    if not candidates:
        return False

    if not repo:
        print("[INFO] No --repo provided, skipping GitHub issue creation")
        return False

    title = f"[Discovery] {len(candidates)} new candidate(s) found"

    rows = "\n".join(_format_candidate_row(c) for c in candidates)
    checklist = _format_candidate_checklist(candidates)
    body = f"""## Discovery Results

Found **{len(candidates)}** new candidate reviewer call(s).

| Conference | Year | Role | URL | Keywords |
|------------|------|------|-----|----------|
{rows}

## Verification Checklist

{checklist}
"""

    if dry_run:
        print(f"[DRY-RUN] Would create issue: {title}")
        for c in candidates:
            print(
                f"  - {c['conference']} {c.get('year', '')} | {c.get('role', 'Reviewer')} | {c['url']}"
            )
        return True

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                title,
                "--body",
                body,
                "--label",
                "candidate",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("[ERROR] Failed to create issue: gh CLI not available or timed out")
        return False

    if result.returncode == 0:
        issue_url = result.stdout.strip()
        print(f"[INFO] Created issue: {issue_url}")
        return True

    print(f"[ERROR] Failed to create issue: {result.stderr.strip()}")
    return False
