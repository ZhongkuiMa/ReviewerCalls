"""Transform calls.yaml to calls.json for website.

Reads data/calls.yaml and data/conferences.yaml,
joins them, and writes docs/calls.json and docs/conferences.json.
"""

import datetime
import json
import logging
import os
import yaml
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def extract_workshop_name(url: str) -> str:
    """Extract workshop name from URL.

    :param url: Workshop URL
    :return: Workshop name or empty string
    """
    url_lower = url.lower()

    # GitHub Pages: extract from domain
    if ".github.io" in url_lower:
        parsed = urlparse(url)
        domain = parsed.netloc
        name = domain.replace(".github.io", "")
        name = re.sub(r"-workshop$", "", name)
        name = re.sub(
            r"-(iclr|icml|neurips|cvpr|iccv|aaai|acl|emnlp)\d{4}$",
            "",
            name,
            flags=re.IGNORECASE,
        )

        if name.isupper() or len(name) <= 3:
            return name.upper()

        parts = name.split("-")
        capitalized_parts = []
        for part in parts:
            if len(part) <= 3 and part.isalpha():
                capitalized_parts.append(part.upper())
            else:
                capitalized_parts.append(part.capitalize())
        return "-".join(capitalized_parts)

    # Google Sites: extract from path
    if "sites.google.com" in url_lower:
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")
        if len(path_parts) >= 3:
            name = path_parts[-1]
            name = re.sub(
                r"^(iclr|icml|neurips|cvpr|iccv|aaai|acl)-?\d{4}-?",
                "",
                name,
                flags=re.IGNORECASE,
            )

            parts = name.split("-")
            capitalized_parts = []
            for part in parts:
                if len(part) <= 3 and part.isalpha():
                    capitalized_parts.append(part.upper())
                elif part.lower().startswith("llm"):
                    remainder = part[3:]
                    if remainder:
                        capitalized_parts.append("LLM")
                        capitalized_parts.append(remainder.capitalize())
                    else:
                        capitalized_parts.append("LLM")
                else:
                    capitalized_parts.append(part.capitalize())
            return "-".join(capitalized_parts)

    # Other cases: try to extract from URL path
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path:
        last_segment = path.split("/")[-1]
        name = re.sub(r"\.(html?|php)$", "", last_segment)
        return name.replace("-", " ").replace("_", " ").title()

    return ""


def main() -> int:
    """Main entry point for site builder.

    :return: Exit code (0 for success)
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    conf_path = os.path.join(repo_root, "data", "conferences.yaml")
    calls_path = os.path.join(repo_root, "data", "calls.yaml")
    site_dir = os.path.join(repo_root, "docs")

    with open(conf_path) as f:
        conf_data = yaml.safe_load(f)

    areas = conf_data.get("areas", {})
    conferences = conf_data.get("conferences", [])

    conf_index = {}
    for c in conferences:
        conf_index[c["short"]] = c

    with open(calls_path) as f:
        calls_data = yaml.safe_load(f)

    raw_calls = calls_data.get("calls", []) or []

    logger.info("Processing calls from calls.yaml")

    enriched_calls = []
    skipped_calls = []
    unconfirmed_calls = []

    for i, call in enumerate(raw_calls, 1):
        short = call["conference"]
        year = call.get("year", "N/A")
        base_role = call.get("role", "N/A")
        confirmed = call.get("confirmed", False)

        date_full = call.get("date", "")
        if date_full:
            date_display = "-".join(date_full.split("-")[:2])
        else:
            date_display = str(year)

        if not confirmed:
            logger.info(
                "[SKIP] [%d/%d] %s %s: Not confirmed (awaiting review)",
                i,
                len(raw_calls),
                short,
                year,
            )
            unconfirmed_calls.append(call)
            continue

        conf = conf_index.get(short)
        if not conf:
            logger.info(
                "[SKIP] [%d/%d] %s %s: Conference not found",
                i,
                len(raw_calls),
                short,
                year,
            )
            skipped_calls.append(short)
            continue

        urls_to_process = []
        if "urls" in call:
            urls_to_process = call["urls"]
            logger.info(
                "[OK] [%d/%d] %s %s - %s (%d URLs)",
                i,
                len(raw_calls),
                short,
                year,
                base_role,
                len(urls_to_process),
            )
        elif "url" in call:
            label = call.get("label", "Main")
            urls_to_process = [{"url": call["url"], "label": label}]
            logger.info(
                "[OK] [%d/%d] %s %s - %s (%s)",
                i,
                len(raw_calls),
                short,
                year,
                base_role,
                label,
            )
        else:
            logger.info(
                "[SKIP] [%d/%d] %s %s: No URL found", i, len(raw_calls), short, year
            )
            continue

        logger.info("  Conference: %s", conf["name"])
        logger.info(
            "  Rank: CCF %s, CORE %s", conf["rank"]["ccf"], conf["rank"]["core"]
        )
        logger.info("  Area: %s", areas.get(conf["area"], conf["area"]))

        for url_obj in urls_to_process:
            url = url_obj["url"]
            label = url_obj.get("label", "Main")

            role_display = base_role

            logger.info("    - %s: %s -> Role: '%s'", label, url, role_display)

            year_suffix = str(year)[-2:]
            conf_abbr = f"{short}'{year_suffix}"

            conf_name = conf["name"]
            if "Workshop" in label or "workshop" in label.lower():
                workshop_name = extract_workshop_name(url)
                if workshop_name:
                    conf_name = f"{conf['name']}, {workshop_name} Workshop"
                else:
                    conf_name = f"{conf['name']}, Workshop"

            enriched_calls.append(
                {
                    "conference": conf_abbr,
                    "name": conf_name,
                    "area": areas.get(conf["area"], conf["area"]),
                    "area_code": conf["area"],
                    "date": date_display,
                    "ccf": conf["rank"]["ccf"],
                    "core": conf["rank"]["core"],
                    "role": role_display,
                    "url": url,
                    "dblp": conf.get("dblp", ""),
                    "round": call.get("round", ""),
                }
            )

        logger.info("  Date: %s", date_display)

    conferences_out = []
    for c in conferences:
        conferences_out.append(
            {
                "short": c["short"],
                "name": c["name"],
                "area": areas.get(c["area"], c["area"]),
                "area_code": c["area"],
                "ccf": c["rank"]["ccf"],
                "core": c["rank"]["core"],
                "dblp": c.get("dblp", ""),
            }
        )

    os.makedirs(site_dir, exist_ok=True)

    logger.info("Writing output files")

    calls_json_path = os.path.join(site_dir, "calls.json")
    calls_payload = {
        "updated": datetime.date.today().isoformat(),
        "calls": enriched_calls,
    }
    with open(calls_json_path, "w") as f:
        json.dump(calls_payload, f, indent=2, ensure_ascii=False)
    logger.info("[OK] Written: %s", calls_json_path)
    logger.info("  Entries: %d", len(enriched_calls))
    logger.info("  Size: %d bytes", os.path.getsize(calls_json_path))

    conf_json_path = os.path.join(site_dir, "conferences.json")
    with open(conf_json_path, "w") as f:
        json.dump(conferences_out, f, indent=2, ensure_ascii=False)
    logger.info("[OK] Written: %s", conf_json_path)
    logger.info("  Entries: %d", len(conferences_out))
    logger.info("  Size: %d bytes", os.path.getsize(conf_json_path))

    logger.info("BUILD SUMMARY")
    logger.info("Input: %d calls from calls.yaml", len(raw_calls))
    logger.info("Output: %d enriched calls", len(enriched_calls))
    logger.info("Unconfirmed: %d calls (awaiting review)", len(unconfirmed_calls))
    if skipped_calls:
        logger.info("Skipped: %d calls (conference not found)", len(skipped_calls))
        logger.info("  %s", ", ".join(skipped_calls))
    logger.info("Conferences: %d total", len(conferences_out))
    logger.info("Updated: %s", datetime.date.today().isoformat())

    return 0
