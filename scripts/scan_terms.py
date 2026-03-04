#!/usr/bin/env python3
"""Scan markdown extracts for configured terms and write term_scan_report.json."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import yaml


def load_terms(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("terms", [])


def count_matches(text: str, patterns: list[str]) -> int:
    total = 0
    for pattern in patterns:
        total += len(re.findall(pattern, text, flags=re.IGNORECASE))
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan markdown files for ICT terms")
    parser.add_argument("--md-dir", default="data/samples_md")
    parser.add_argument("--terms", default="config/terms.yml")
    parser.add_argument("--output", default="data/term_scan_report.json")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    md_dir = Path(args.md_dir)
    terms = load_terms(Path(args.terms))

    if not md_dir.exists():
        raise FileNotFoundError(f"Markdown directory not found: {md_dir}")

    term_counts: Counter[str] = Counter()
    files_with_matches: list[dict] = []
    files_scanned = 0

    for md_path in sorted(md_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8", errors="replace")
        files_scanned += 1
        per_file_matches: list[dict] = []

        for term in terms:
            name = term.get("name")
            patterns = term.get("patterns", [])
            if not name or not patterns:
                continue
            count = count_matches(text, patterns)
            if count > 0:
                term_counts[name] += count
                per_file_matches.append({"term": name, "count": count})

        if per_file_matches:
            per_file_matches.sort(key=lambda item: item["count"], reverse=True)
            files_with_matches.append(
                {
                    "file": md_path.name,
                    "match_count": sum(item["count"] for item in per_file_matches),
                    "matches": per_file_matches,
                }
            )

    files_with_matches.sort(key=lambda item: item["match_count"], reverse=True)

    report = {
        "files_scanned": files_scanned,
        "term_counts": term_counts.most_common(args.top),
        "files_with_matches": files_with_matches,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Scanned {files_scanned} markdown files")
    print(f"Files with matches: {len(files_with_matches)}")
    print(f"Wrote report to {output_path}")


if __name__ == "__main__":
    main()
