#!/usr/bin/env python3
"""
Extract and analyze contract officer information from opportunities and awards.
Identifies who manages the most opportunities, wins, and budgets by department.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def extract_officers(records_path: Path, summary_path: Path, output_path: Path) -> None:
    """Extract contract officer data and generate intelligence."""

    if not records_path.exists():
        print(f"Error: {records_path} not found")
        return

    records: list[dict] = json.loads(records_path.read_text(encoding="utf-8"))

    # Track officers by name, email, and their activity
    officer_stats: dict[str, dict] = defaultdict(lambda: {
        "email": None,
        "phone": None,
        "departments": set(),
        "opportunities": 0,
        "awards": 0,
        "total_award_value": 0,
        "primary_role_count": 0,
        "secondary_role_count": 0,
    })

    # Department-level officer tracking
    dept_officers: dict[str, dict] = defaultdict(lambda: defaultdict(lambda: {
        "opportunities": 0,
        "awards": 0,
        "total_award_value": 0,
    }))

    for record in records:
        dept = record.get("Department/Ind.Agency", "UNKNOWN")

        # Process primary contact
        primary_name = record.get("PrimaryContactFullname", "").strip()
        if primary_name:
            officer_stats[primary_name]["email"] = record.get("PrimaryContactEmail")
            officer_stats[primary_name]["phone"] = record.get("PrimaryContactPhone")
            officer_stats[primary_name]["departments"].add(dept)
            officer_stats[primary_name]["opportunities"] += 1
            officer_stats[primary_name]["primary_role_count"] += 1

            dept_officers[dept][primary_name]["opportunities"] += 1

            # Track awards and value
            if record.get("AwardNumber"):
                officer_stats[primary_name]["awards"] += 1
                dept_officers[dept][primary_name]["awards"] += 1

                try:
                    award_val = float(str(record.get("Award$", "0")).replace(",", ""))
                    officer_stats[primary_name]["total_award_value"] += award_val
                    dept_officers[dept][primary_name]["total_award_value"] += award_val
                except (ValueError, TypeError):
                    pass

        # Process secondary contact
        secondary_name = record.get("SecondaryContactFullname", "").strip()
        if secondary_name:
            officer_stats[secondary_name]["email"] = record.get("SecondaryContactEmail")
            officer_stats[secondary_name]["phone"] = record.get("SecondaryContactPhone")
            officer_stats[secondary_name]["departments"].add(dept)
            officer_stats[secondary_name]["opportunities"] += 1
            officer_stats[secondary_name]["secondary_role_count"] += 1

            dept_officers[dept][secondary_name]["opportunities"] += 1

            if record.get("AwardNumber"):
                officer_stats[secondary_name]["awards"] += 1
                dept_officers[dept][secondary_name]["awards"] += 1

                try:
                    award_val = float(str(record.get("Award$", "0")).replace(",", ""))
                    officer_stats[secondary_name]["total_award_value"] += award_val
                    dept_officers[dept][secondary_name]["total_award_value"] += award_val
                except (ValueError, TypeError):
                    pass

    # Convert departments set to list for JSON serialization
    for officer in officer_stats.values():
        officer["departments"] = sorted(officer["departments"])

    # Build output: top officers by opportunities and wins
    top_officers = sorted(
        [
            {
                "name": name,
                "email": stats["email"],
                "phone": stats["phone"],
                "departments": stats["departments"],
                "opportunities": stats["opportunities"],
                "awards": stats["awards"],
                "total_award_value": int(stats["total_award_value"]),
                "primary_role": stats["primary_role_count"],
                "secondary_role": stats["secondary_role_count"],
            }
            for name, stats in officer_stats.items()
        ],
        key=lambda x: x["opportunities"],
        reverse=True,
    )

    # Department officers summary
    dept_officer_summary: dict[str, list] = {}
    for dept, officers in dept_officers.items():
        top_officers_in_dept = sorted(
            [
                {
                    "name": name,
                    "opportunities": stats["opportunities"],
                    "awards": stats["awards"],
                    "total_award_value": int(stats["total_award_value"]),
                }
                for name, stats in officers.items()
            ],
            key=lambda x: x["opportunities"],
            reverse=True,
        )
        dept_officer_summary[dept] = top_officers_in_dept[:5]  # Top 5 per department

    # Resolve effective date from summary file
    effective_date: str | None = None
    if summary_path.exists():
        effective_date = json.loads(summary_path.read_text(encoding="utf-8")).get("effective_date")

    output = {
        "extraction_date": effective_date,
        "total_unique_officers": len(officer_stats),
        "top_officers": top_officers[:50],  # Top 50 officers
        "officers_by_department": dept_officer_summary,
    }

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"✅ Extracted {len(officer_stats)} unique contract officers")
    print("📊 Top 3 Most Active Officers:")
    for i, officer in enumerate(top_officers[:3], 1):
        print(f"   {i}. {officer['name']}")
        print(f"      {officer['opportunities']} opportunities, {officer['awards']} awards")
        print(f"      ${officer['total_award_value']:,.0f} managed")
        print(f"      Email: {officer['email']}")

    print(f"\n📁 Results saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract contract officer intelligence from today's records"
    )
    parser.add_argument("--records", default="docs/data/today_records.json")
    parser.add_argument("--summary", default="docs/data/today_summary.json")
    parser.add_argument("--output", default="docs/data/contract_officers.json")
    args = parser.parse_args()

    extract_officers(
        records_path=Path(args.records),
        summary_path=Path(args.summary),
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
