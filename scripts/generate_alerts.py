#!/usr/bin/env python3
"""Generate high-value match alerts from today's summary artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FOCUS_TERMS = {
    "web",
    "accessibility",
    "wcag",
    "acr",
    "vpat",
    "openacr",
    "open source",
    "drupal",
    "cms",
    "api",
    "cloud",
    "modernization",
    "user experience",
    "uswds",
    "ux",
    "ui",
    "content management system",
}

ACCESSIBILITY_SIGNAL_NAICS_PREFIXES = (
    "5112",   # Software publishers
    "518",    # Computing infrastructure, hosting, and related services
    "51913",  # Internet publishing and broadcasting and web search portals
    "5415",   # Computer systems design and related services
)

ACCESSIBILITY_SIGNAL_PSC_PREFIXES = (
    "D3",  # IT and telecom - information technology systems
    "D7",  # IT and telecom - IT strategy and architecture
)


def has_accessibility_code_signal(record: dict[str, Any]) -> bool:
    """Return True when NAICS/PSC codes suggest SRT (Solicitation Review Tool) relevance."""
    naics = "".join(ch for ch in str(record.get("NaicsCode", "")) if ch.isdigit())
    psc = str(record.get("ClassificationCode") or "").strip().upper()

    has_naics_signal = any(naics.startswith(prefix) for prefix in ACCESSIBILITY_SIGNAL_NAICS_PREFIXES)
    has_psc_signal = any(psc.startswith(prefix) for prefix in ACCESSIBILITY_SIGNAL_PSC_PREFIXES)
    return has_naics_signal or has_psc_signal


def score_record(record: dict[str, Any], min_hits: int) -> tuple[int, bool]:
    matches = record.get("matches", [])
    total_hits = sum(int(item.get("count", 0)) for item in matches)
    terms = {str(item.get("term", "")).lower() for item in matches}
    has_focus = bool(terms & FOCUS_TERMS) or has_accessibility_code_signal(record)
    return total_hits, bool(total_hits >= min_hits and has_focus)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate high-value alerts")
    parser.add_argument("--summary", default="data/today/summary.json")
    parser.add_argument("--output-json", default="data/today/high_value_matches.json")
    parser.add_argument("--output-md", default="data/today/high_value_alert.md")
    parser.add_argument("--output-meta", default="data/today/alerts_summary.json")
    parser.add_argument("--min-hits", type=int, default=8)
    parser.add_argument("--max-records", type=int, default=25)
    args = parser.parse_args()

    summary_path = Path(args.summary)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    selected: list[dict[str, Any]] = []
    for record in summary.get("top_matching_records", []):
        total_hits, include = score_record(record, args.min_hits)
        if include:
            item = dict(record)
            item["total_hits"] = total_hits
            selected.append(item)

    selected.sort(key=lambda row: row.get("total_hits", 0), reverse=True)
    selected = selected[: args.max_records]

    payload = {
        "requested_date": summary.get("requested_date"),
        "effective_date": summary.get("effective_date"),
        "records_total": summary.get("records_total", 0),
        "high_value_count": len(selected),
        "min_hits": args.min_hits,
        "focus_terms": sorted(FOCUS_TERMS),
        "matches": selected,
    }

    Path(args.output_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    Path(args.output_meta).write_text(
        json.dumps(
            {
                "high_value_count": len(selected),
                "effective_date": summary.get("effective_date"),
                "requested_date": summary.get("requested_date"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# High-value SAM.gov Matches",
        "",
        f"- Effective date: {summary.get('effective_date')}",
        f"- Requested date: {summary.get('requested_date')}",
        f"- Candidate records: {summary.get('records_total', 0)}",
        f"- High-value matches: {len(selected)}",
        f"- Threshold: total term hits >= {args.min_hits} and includes one focus term or NAICS/PSC accessibility signal",
        "",
    ]

    if not selected:
        lines.append("No high-value matches were found for this snapshot.")
    else:
        for row in selected:
            lines.extend(
                [
                    f"## {row.get('Title', 'Untitled')}",
                    "",
                    f"- Department: {row.get('Agency', 'Unknown')}",
                    f"- Type: {row.get('Type', 'Unknown')}",
                    f"- PostedDate: {row.get('PostedDate', '')}",
                    f"- Total term hits: {row.get('total_hits', 0)}",
                    f"- Link: {row.get('Link', '')}",
                    "- Top terms: "
                    + ", ".join(
                        f"{m.get('term')}({m.get('count')})" for m in row.get("matches", [])[:6]
                    ),
                    "",
                ]
            )

    Path(args.output_md).write_text("\n".join(lines), encoding="utf-8")

    print(f"High-value matches: {len(selected)}")
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_meta}")


if __name__ == "__main__":
    main()
