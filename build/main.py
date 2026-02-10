"""Transform calls.yaml to calls.json for website.

Reads data/calls.yaml and data/conferences.yaml,
joins them, and writes docs/calls.json and docs/conferences.json.
"""

import datetime
import json
import os
import yaml
import re
from urllib.parse import urlparse


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

    print(f"\n{'=' * 60}")
    print("Processing calls from calls.yaml")
    print(f"{'=' * 60}")

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
            print(
                f"[SKIP] [{i}/{len(raw_calls)}] {short} {year}: Not confirmed (awaiting review)"
            )
            unconfirmed_calls.append(call)
            continue

        conf = conf_index.get(short)
        if not conf:
            print(f"[SKIP] [{i}/{len(raw_calls)}] {short} {year}: Conference not found")
            skipped_calls.append(short)
            continue

        urls_to_process = []
        if "urls" in call:
            urls_to_process = call["urls"]
            print(
                f"[OK] [{i}/{len(raw_calls)}] {short} {year} - {base_role} ({len(urls_to_process)} URLs)"
            )
        elif "url" in call:
            label = call.get("label", "Main")
            urls_to_process = [{"url": call["url"], "label": label}]
            print(f"[OK] [{i}/{len(raw_calls)}] {short} {year} - {base_role} ({label})")
        else:
            print(f"[SKIP] [{i}/{len(raw_calls)}] {short} {year}: No URL found")
            continue

        print(f"  Conference: {conf['name']}")
        print(f"  Rank: CCF {conf['rank']['ccf']}, CORE {conf['rank']['core']}")
        print(f"  Area: {areas.get(conf['area'], conf['area'])}")

        for url_obj in urls_to_process:
            url = url_obj["url"]
            label = url_obj.get("label", "Main")

            role_display = base_role

            print(f"    - {label}: {url} -> Role: '{role_display}'")

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

        print(f"  Date: {date_display}")

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

    print(f"\n{'=' * 60}")
    print("Writing output files")
    print(f"{'=' * 60}")

    calls_json_path = os.path.join(site_dir, "calls.json")
    calls_payload = {
        "updated": datetime.date.today().isoformat(),
        "calls": enriched_calls,
    }
    with open(calls_json_path, "w") as f:
        json.dump(calls_payload, f, indent=2, ensure_ascii=False)
    print(f"[OK] Written: {calls_json_path}")
    print(f"  Entries: {len(enriched_calls)}")
    print(f"  Size: {os.path.getsize(calls_json_path)} bytes")

    conf_json_path = os.path.join(site_dir, "conferences.json")
    with open(conf_json_path, "w") as f:
        json.dump(conferences_out, f, indent=2, ensure_ascii=False)
    print(f"[OK] Written: {conf_json_path}")
    print(f"  Entries: {len(conferences_out)}")
    print(f"  Size: {os.path.getsize(conf_json_path)} bytes")

    print(f"\n{'=' * 60}")
    print("BUILD SUMMARY")
    print(f"{'=' * 60}")
    print(f"Input: {len(raw_calls)} calls from calls.yaml")
    print(f"Output: {len(enriched_calls)} enriched calls")
    print(f"Unconfirmed: {len(unconfirmed_calls)} calls (awaiting review)")
    if skipped_calls:
        print(f"Skipped: {len(skipped_calls)} calls (conference not found)")
        print(f"  {', '.join(skipped_calls)}")
    print(f"Conferences: {len(conferences_out)} total")
    print(f"Updated: {datetime.date.today().isoformat()}")
    print(f"{'=' * 60}")

    return 0
