#!/usr/bin/env python3
"""
Quick script to add matches property to records without re-running Ollama analysis.
This enables term filtering to work immediately.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


def scan_terms(text: str, terms_config: dict) -> tuple[dict, dict]:
    """Simple term scanning without LLM analysis."""
    term_counts: dict[str, int] = {}
    term_details: list[dict] = []
    text_lower = text.lower()

    for category, config in terms_config.items():
        if isinstance(config, dict):
            terms = config.get("terms", [])
        else:
            terms = config if isinstance(config, list) else []

        for term in terms:
            # Skip if term is a dict (malformed config)
            if isinstance(term, dict):
                term = term.get("name", term.get("term", ""))

            if not isinstance(term, str):
                continue

            # Use word boundary matching
            pattern = r"\b" + re.escape(term.lower()) + r"\b"
            matches = re.findall(pattern, text_lower)
            count = len(matches)

            if count > 0:
                term_counts[term] = term_counts.get(term, 0) + count
                term_details.append({
                    "term": term,
                    "category": category,
                    "count": count,
                })

    # Sort by count descending
    term_details.sort(key=lambda x: x["count"], reverse=True)

    return term_counts, {"terms": term_details, "categories": {}}


def main() -> int:
    records_file = Path(__file__).parent.parent / "docs" / "data" / "today_records.json"
    terms_file = Path(__file__).parent.parent / "config" / "terms.yml"

    if not records_file.exists():
        print(f"Error: {records_file} not found")
        return 1

    try:
        terms_config: dict = yaml.safe_load(terms_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        print(f"Error loading terms config: {e}")
        return 1

    records: list[dict] = json.loads(records_file.read_text(encoding="utf-8"))

    print(f"Processing {len(records)} records...")

    # Add matches to each record
    updated = 0
    has_matches = 0
    for i, record in enumerate(records):
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(records)} processed...")

        if "matches" not in record:
            # Combine title and description for term scanning
            text = f"{record.get('Title', '')}\n{record.get('Description', '')}"
            _, details = scan_terms(text, terms_config)
            record["matches"] = details["terms"]
            updated += 1

            if details["terms"]:
                has_matches += 1

    # Save updated records
    records_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print("\nResults:")
    print(f"  Updated: {updated} records")
    print(f"  With matches: {has_matches} records")
    print(f"  Total records: {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
