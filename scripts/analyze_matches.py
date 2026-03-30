#!/usr/bin/env python3
"""Analyze term matches and surface top records with snippets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_json_for_file(md_filename: str, json_dir: Path) -> dict:
    """Load the corresponding sample JSON for a markdown file."""
    base = md_filename.replace(".md", "")
    json_path = json_dir / f"{base}.sample.json"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze term matches and surface top records with snippets")
    parser.add_argument("--report", default="data/term_scan_report.json")
    parser.add_argument("--md-dir", default="data/samples_md")
    parser.add_argument("--json-dir", default="data/samples_json")
    parser.add_argument("--output", default="data/top_matches_report.md")
    args = parser.parse_args()

    report_path = Path(args.report)
    md_dir = Path(args.md_dir)
    json_dir = Path(args.json_dir)
    output_path = Path(args.output)

    report = json.loads(report_path.read_text(encoding="utf-8"))

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

        text = (md_dir / md_file).read_text(encoding="utf-8")
        record = load_json_for_file(md_file, json_dir)

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
        top_term = matches[0]["term"]
        snippet = extract_snippet(
            text,
            r"\b" + top_term.replace("_", r"\s*").replace("-", r"[-\s]") + r"\b",
        )
        output_lines.append(f"> {snippet}")
        output_lines.extend(["", "---", ""])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines), encoding="utf-8")

    print(f"Wrote top matches report to {output_path}")


if __name__ == "__main__":
    main()
