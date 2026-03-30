#!/usr/bin/env python3
"""
Departmental forecasting: analyze pipeline, win rates, and value by department.
Provides sales forecasting intelligence for budget planning and strategy.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def forecast_departments(records_path: Path, dept_path: Path, summary_path: Path, output_path: Path) -> None:
    """Generate departmental forecasting insights."""

    if not records_path.exists() or not dept_path.exists():
        print("Error: Required data files not found")
        return

    records: list[dict] = json.loads(records_path.read_text(encoding="utf-8"))
    departments: list[dict] = json.loads(dept_path.read_text(encoding="utf-8"))

    # Aggregate by department
    dept_data: dict[str, dict] = defaultdict(lambda: {
        "opportunities": [],
        "awards": [],
    })

    for record in records:
        dept = record.get("Department/Ind.Agency", "UNKNOWN")

        # Track opportunity details
        dept_data[dept]["opportunities"].append({
            "title": record.get("Title", ""),
            "notice_id": record.get("NoticeId", ""),
            "posted_date": record.get("PostedDate", ""),
            "response_deadline": record.get("ResponseDeadLine", ""),
            "description_length": len(record.get("Description", "")),
            "has_attachments": record.get("AttachmentCount", 0) > 0,
            "matches": record.get("matches", []),
            "sol_number": record.get("Sol#", ""),
        })

        # Track award details
        if record.get("AwardNumber"):
            try:
                award_value = float(str(record.get("Award$", "0")).replace(",", ""))
            except (ValueError, TypeError):
                award_value = 0.0

            dept_data[dept]["awards"].append({
                "awardee": record.get("Awardee", ""),
                "award_number": record.get("AwardNumber", ""),
                "award_date": record.get("AwardDate", ""),
                "award_value": award_value,
                "title": record.get("Title", ""),
            })

    # Calculate forecasting metrics for each department
    dept_forecast: dict[str, dict] = {}
    for dept in departments:
        dept_name = dept["department"]
        opps = dept_data[dept_name]["opportunities"]
        awards = dept_data[dept_name]["awards"]

        # Financial metrics
        total_award_value = sum(a["award_value"] for a in awards)
        avg_award_value = total_award_value / len(awards) if awards else 0

        # Win metrics
        win_rate = (len(awards) / len(opps)) if opps else 0

        # Attachment and matching metrics
        opps_with_attachments = sum(1 for o in opps if o["has_attachments"])
        opps_with_matches = sum(1 for o in opps if o["matches"])

        # Deduplicate awardees before building top list
        awardee_totals: dict[str, dict] = {}
        for a in awards:
            name = a["awardee"]
            if name not in awardee_totals:
                awardee_totals[name] = {"name": name, "wins": 0, "total_value": 0.0}
            awardee_totals[name]["wins"] += 1
            awardee_totals[name]["total_value"] += a["award_value"]

        top_awardees = sorted(awardee_totals.values(), key=lambda x: x["total_value"], reverse=True)[:5]
        top_awardees = [
            {**entry, "total_value": int(entry["total_value"])} for entry in top_awardees
        ]

        dept_forecast[dept_name] = {
            "total_records": dept["total"],
            "open_opportunities": dept["opportunities"],
            "awarded": dept["wins"],
            "win_rate_percent": round(win_rate * 100, 1),
            "estimated_monthly_value": int(total_award_value),
            "average_award_value": int(avg_award_value),
            "opportunities_with_attachments": opps_with_attachments,
            "opportunities_with_keyword_matches": opps_with_matches,
            "top_awardees": top_awardees,
        }

    # Rank departments by opportunity and value
    ranked_by_opps = sorted(
        [{**v, "department": k} for k, v in dept_forecast.items()],
        key=lambda x: x["open_opportunities"],
        reverse=True,
    )

    ranked_by_value = sorted(
        [{**v, "department": k} for k, v in dept_forecast.items()],
        key=lambda x: x["estimated_monthly_value"],
        reverse=True,
    )

    # Resolve effective date from summary file
    effective_date: str | None = None
    if summary_path.exists():
        effective_date = json.loads(summary_path.read_text(encoding="utf-8")).get("effective_date")

    output = {
        "forecast_date": effective_date,
        "departments_by_opportunity_volume": ranked_by_opps,
        "departments_by_award_value": ranked_by_value,
        "department_forecasts": dept_forecast,
    }

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("✅ Department forecasting analysis complete")
    print("\n📊 TOP 5 DEPARTMENTS BY OPPORTUNITY VOLUME:")
    for i, dept in enumerate(ranked_by_opps[:5], 1):
        print(f"   {i}. {dept['department']}")
        print(f"      {dept['open_opportunities']} open opportunities, {dept['awarded']} awards")
        print(f"      Win rate: {dept['win_rate_percent']}% | Est. Value: ${dept['estimated_monthly_value']:,}")

    print("\n💰 TOP 5 DEPARTMENTS BY AWARD VALUE:")
    for i, dept in enumerate(ranked_by_value[:5], 1):
        print(f"   {i}. {dept['department']}")
        print(f"      ${dept['estimated_monthly_value']:,} awarded | Avg: ${dept['average_award_value']:,}")
        if dept["top_awardees"]:
            top = dept["top_awardees"][0]
            print(f"      Top winner: {top['name']} (${top['total_value']:,})")

    print(f"\n📁 Results saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate departmental forecasting insights from today's records"
    )
    parser.add_argument("--records", default="docs/data/today_records.json")
    parser.add_argument("--departments", default="docs/data/today_departments.json")
    parser.add_argument("--summary", default="docs/data/today_summary.json")
    parser.add_argument("--output", default="docs/data/department_forecast.json")
    args = parser.parse_args()

    forecast_departments(
        records_path=Path(args.records),
        dept_path=Path(args.departments),
        summary_path=Path(args.summary),
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
