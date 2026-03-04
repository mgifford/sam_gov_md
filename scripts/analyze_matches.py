#!/usr/bin/env python3
"""Analyze term matches and surface top records with snippets."""

import json
import os
import re
from pathlib import Path

REPORT_PATH = "data/term_scan_report.json"
MD_DIR = "data/samples_md"
JSON_DIR = "data/samples_json"
OUTPUT_PATH = "data/top_matches_report.md"


def load_json_for_file(md_filename: str) -> dict:
    """Load the corresponding sample JSON for a markdown file."""
    base = md_filename.replace(".md", "")
    json_path = os.path.join(JSON_DIR, f"{base}.sample.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_snippet(text: str, term_pattern: str, context: int = 200) -> str:
    """Extract a snippet around the first match of a term."""
    match = re.search(term_pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - context)
    end = min(len(text), match.end() + context)
    snippet = text[start:end].strip()
    return f"...{snippet}..."


def main():
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    output_lines = [
        "# Top ICT/Digital Project Matches",
        "",
        f"Analyzed {report['files_scanned']} files from SAM.gov historical extracts.",
        "",
        "## Term Frequency Summary",
        "",
    ]

    for term, count in report["term_counts"][:15]:
        output_lines.append(f"- **{term}**: {count} occurrences")

    output_lines.extend(["", "## Top Matching Records", ""])

    for item in report["files_with_matches"][:10]:
        md_file = item["file"]
        matches = item["matches"]
        total = sum(m["count"] for m in matches)

        md_path = os.path.join(MD_DIR, md_file)
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()

        record = load_json_for_file(md_file)
        
        output_lines.extend([
            f"### {md_file}",
            "",
            f"**Total matches**: {total}",
            "",
        ])

        if record:
            if "SOLNBR" in record:
                output_lines.append(f"**Solicitation**: {record['SOLNBR']}")
            if "SUBJECT" in record:
                output_lines.append(f"**Subject**: {record['SUBJECT']}")
            if "AGENCY" in record:
                output_lines.append(f"**Agency**: {record['AGENCY']}")
            if "URL" in record:
                output_lines.append(f"**URL**: {record['URL']}")
            output_lines.append("")

        output_lines.append("**Terms found**:")
        for match in matches[:5]:
            output_lines.append(f"- {match['term']}: {match['count']}")

        output_lines.extend(["", "**Sample snippet**:", ""])
        # Get snippet for top term
        top_term = matches[0]["term"]
        snippet = extract_snippet(text, r"\b" + top_term.replace("_", r"\s*").replace("-", r"[-\s]") + r"\b")
        output_lines.append(f"> {snippet}")
        output_lines.extend(["", "---", ""])

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
        out.write("\n".join(output_lines))

    print(f"Wrote top matches report to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
