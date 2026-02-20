"""Prompt builders for LLM validation."""

from __future__ import annotations

SYSTEM_PROMPT = """You are an expert at identifying academic conference reviewer recruitment pages.

Task: Determine if this webpage is an ACTIVE call for reviewer/PC nominations or applications.

Decision rules:
1. Answer YES if page explicitly invites submissions/nominations for reviewer/PC/AC/SAC/AEC role
2. Answer NO if page is CFP (call for papers), generic committee listing, archived, or unrelated
3. Answer NO if page is for workshops, tutorials, non-main-conference tracks, or support content
4. Answer YES only if recruiting is currently OPEN (not closed/past)

Return ONLY valid JSON, no markdown."""


def build_user_prompt(entry: dict, content: str) -> str:
    """Build user prompt with entry metadata and page content.

    :param entry: Call entry with conference, year, role, url, label
    :param content: Extracted visible text from webpage
    :returns: User prompt string
    """
    conf = entry.get("conference", "Unknown")
    year = entry.get("year", "Unknown")
    role = entry.get("role", "Unknown")
    url = entry.get("url", "")
    label = entry.get("label", "Main")

    return f"""Conference: {conf} {year}
Claimed role: {role} ({label})
URL: {url}

--- PAGE CONTENT ---
{content}
--- END ---

Is this an active reviewer/committee recruitment call?

Return ONLY valid JSON (no markdown):
{{
  "answer": "yes" or "no",
  "reason": "one sentence explanation"
}}"""
