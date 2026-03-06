#!/usr/bin/env python3
"""
Departmental forecasting: analyze pipeline, win rates, and value by department.
Provides sales forecasting intelligence for budget planning and strategy.
"""

import json
from pathlib import Path
from collections import defaultdict

def forecast_departments():
    """Generate departmental forecasting insights."""
    
    records_path = Path("docs/data/today_records.json")
    dept_path = Path("docs/data/today_departments.json")
    
    if not records_path.exists() or not dept_path.exists():
        print("Error: Required data files not found")
        return
    
    with open(records_path) as f:
        records = json.load(f)
    
    with open(dept_path) as f:
        departments = json.load(f)
    
    # Build detailed forecasting data
    dept_forecast = {}
    
    # Aggregate by department
    dept_data = defaultdict(lambda: {
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
                award_value = 0
            
            dept_data[dept]["awards"].append({
                "awardee": record.get("Awardee", ""),
                "award_number": record.get("AwardNumber", ""),
                "award_date": record.get("AwardDate", ""),
                "award_value": award_value,
                "title": record.get("Title", ""),
            })
    
    # Calculate forecasting metrics for each department
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
        
        # Prepare forecast entry
        dept_forecast[dept_name] = {
            "total_records": dept["total"],
            "open_opportunities": dept["opportunities"],
            "awarded": dept["wins"],
            "win_rate_percent": round(win_rate * 100, 1),
            "estimated_monthly_value": int(total_award_value),
            "average_award_value": int(avg_award_value),
            "opportunities_with_attachments": opps_with_attachments,
            "opportunities_with_keyword_matches": opps_with_matches,
            "top_awardees": sorted(
                [
                    {
                        "name": a["awardee"],
                        "wins": sum(1 for x in awards if x["awardee"] == a["awardee"]),
                        "total_value": int(sum(x["award_value"] for x in awards if x["awardee"] == a["awardee"])),
                    }
                    for a in awards
                ],
                key=lambda x: x["total_value"],
                reverse=True,
            )[:5],
        }
    
    # Rank departments by opportunity and value
    ranked_by_opps = sorted(
        [
            {**v, "department": k}
            for k, v in dept_forecast.items()
        ],
        key=lambda x: x["open_opportunities"],
        reverse=True,
    )
    
    ranked_by_value = sorted(
        [
            {**v, "department": k}
            for k, v in dept_forecast.items()
        ],
        key=lambda x: x["estimated_monthly_value"],
        reverse=True,
    )
    
    # Output
    output = {
        "forecast_date": json.loads(Path("docs/data/today_summary.json").read_text()).get("effective_date"),
        "departments_by_opportunity_volume": ranked_by_opps,
        "departments_by_award_value": ranked_by_value,
        "department_forecasts": dept_forecast,
    }
    
    output_path = Path("docs/data/department_forecast.json")
    output_path.write_text(json.dumps(output, indent=2))
    
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
        if dept['top_awardees']:
            print(f"      Top winner: {dept['top_awardees'][0]['name']} (${dept['top_awardees'][0]['total_value']:,})")
    
    print(f"\n📁 Results saved to docs/data/department_forecast.json")

if __name__ == "__main__":
    forecast_departments()
