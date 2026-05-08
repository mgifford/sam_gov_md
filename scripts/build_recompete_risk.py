#!/usr/bin/env python3
"""Build a recompete risk dataset for a selected contractor cohort.

This script is intentionally provider-oriented so it can run now with
USASpending-only data, while remaining easy to connect to external
toolchains (for example MCP-backed usaspending/ecfr/gsa_calc clients).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

USASPENDING_ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
EARLIEST_USASPENDING_DATE = "2007-10-01"
REQUEST_TIMEOUT = 30
CONTRACT_AWARD_TYPE_CODES = ["A", "B", "C", "D"]
COHORT_COMPANY_FILES = {
    "dsc": "config/company_lists/dsc.json",
    "ai": "config/company_lists/ai_vendors_federal.json",
}

# Conservative fallback medians; replace with live gsa_calc integration when
# available. Values are hourly rates in USD.
FALLBACK_RATE_BENCHMARKS = {
    "Software Engineer": {"p50": 165.0, "p75": 205.0},
    "DevSecOps Engineer": {"p50": 185.0, "p75": 225.0},
    "Data Scientist": {"p50": 190.0, "p75": 240.0},
    "Business Analyst": {"p50": 130.0, "p75": 165.0},
    "UX Designer": {"p50": 145.0, "p75": 180.0},
    "Program Manager": {"p50": 170.0, "p75": 220.0},
    "Cybersecurity Analyst": {"p50": 180.0, "p75": 230.0},
    "General IT Services": {"p50": 145.0, "p75": 185.0},
}


@dataclass(frozen=True)
class Company:
    """A target company entry for cohort analysis."""

    name: str
    uei: str | None = None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build recompete risk outputs")
    parser.add_argument(
        "--cohort",
        choices=sorted(COHORT_COMPANY_FILES.keys()),
        help="Named company cohort preset (overrides --companies-file when set).",
    )
    parser.add_argument(
        "--companies-file",
        default="config/company_lists/dsc.json",
        help="JSON file containing company list (names and optional UEIs).",
    )
    parser.add_argument(
        "--fy-start",
        default="2026-10-01",
        help="FY window start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--fy-end",
        default="2027-09-30",
        help="FY window end date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--max-pages-per-company",
        type=int,
        default=8,
        help="USASpending pages fetched per company before stopping.",
    )
    parser.add_argument(
        "--output-json",
        default="data/today/recompetes.json",
        help="Output JSON path (ParaCharts shape).",
    )
    parser.add_argument(
        "--output-md",
        default="data/today/summary.md",
        help="Output markdown summary path.",
    )
    parser.add_argument(
        "--output-docs-json",
        default="docs/data/recompetes.json",
        help="Optional docs JSON output path for GitHub Pages visualization.",
    )
    parser.add_argument(
        "--output-paracharts-spec",
        default="docs/data/recompetes_paracharts_specs.json",
        help="ParaCharts manifest/spec JSON output path.",
    )
    return parser.parse_args()


def load_companies(path: Path) -> list[Company]:
    """Load companies from a JSON list.

    Accepted JSON formats:
    - ["Company A", "Company B"]
    - [{"name": "Company A", "uei": "ABC123..."}, ...]
    - [{"company_name": "Company A", "sector": "..."}, ...]
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Company file must be a JSON array")

    companies: list[Company] = []
    for item in payload:
        if isinstance(item, str):
            name = item.strip()
            if name:
                companies.append(Company(name=name))
            continue
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("company_name") or "").strip()
            uei_raw = str(item.get("uei", "")).strip()
            if name:
                companies.append(Company(name=name, uei=uei_raw or None))

    deduped: list[Company] = []
    seen = set()
    for company in companies:
        key = company.name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(company)
    return deduped


def resolve_companies_file(cohort: str | None, companies_file: str) -> Path:
    """Resolve final company-list path from cohort preset or explicit file."""
    if cohort:
        return Path(COHORT_COMPANY_FILES[cohort])
    return Path(companies_file)


def parse_date(value: str | None) -> date | None:
    """Parse common API date formats into a date value."""
    if not value:
        return None
    raw = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def quarter_from_date(value: date) -> str:
    """Map calendar month to Q1-Q4 for ParaCharts output."""
    month_to_q = {
        1: "Q1",
        2: "Q1",
        3: "Q1",
        4: "Q2",
        5: "Q2",
        6: "Q2",
        7: "Q3",
        8: "Q3",
        9: "Q3",
        10: "Q4",
        11: "Q4",
        12: "Q4",
    }
    return month_to_q[value.month]


def is_small_business_set_aside(value: str | None) -> bool:
    """Return True when set-aside text indicates a small-business action."""
    if not value:
        return False
    text = value.lower()
    return "small" in text and ("set aside" in text or "set-aside" in text)


def far_rule_of_two_note(is_set_aside: bool) -> str:
    """Return a compact FAR 19.5 note for recompete screening."""
    if is_set_aside:
        return (
            "Small Business Set-Aside detected; FAR 19.502-2 (Rule of Two) "
            "likely applies to recompete strategy."
        )
    return "No Small Business Set-Aside signal detected in award metadata."


def infer_labor_category(description: str | None) -> str:
    """Infer a primary labor category from text using simple keyword rules."""
    text = (description or "").lower()
    category_patterns: list[tuple[str, str]] = [
        (r"devsecops|ci/cd|pipeline|kubernetes", "DevSecOps Engineer"),
        (r"software|application development|coding|developer", "Software Engineer"),
        (r"data science|machine learning|analytics", "Data Scientist"),
        (r"ux|user experience|human-centered|design", "UX Designer"),
        (r"program management|project management|pmo", "Program Manager"),
        (r"cyber|security operations|zero trust", "Cybersecurity Analyst"),
        (r"business analysis|requirements", "Business Analyst"),
    ]
    for pattern, category in category_patterns:
        if re.search(pattern, text):
            return category
    return "General IT Services"


def benchmark_diff_percent(labor_category: str) -> float:
    """Return benchmark delta percent.

    Until gsa_calc integration is live in this repository runtime, we emit a
    neutral 0.0 value to keep ParaCharts schema stable.
    """
    _ = FALLBACK_RATE_BENCHMARKS.get(labor_category)
    return 0.0


def search_awards_for_company(
    company: Company,
    fy_start: date,
    fy_end: date,
    max_pages: int,
) -> list[dict[str, Any]]:
    """Query USASpending award search and return records expiring in FY window."""
    fields = [
        "Award ID",
        "Recipient Name",
        "Recipient UEI",
        "Awarding Agency",
        "Award Amount",
        "Description",
        "Type Set Aside",
        "Period of Performance End Date",
        "Period of Performance Current End Date",
    ]

    filters: dict[str, Any] = {
        "time_period": [{"start_date": EARLIEST_USASPENDING_DATE, "end_date": str(fy_end)}],
        "award_type_codes": CONTRACT_AWARD_TYPE_CODES,
    }
    if company.uei:
        filters["recipient_uei"] = [company.uei]
    else:
        filters["recipient_search_text"] = [company.name]

    selected: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        payload = {
            "fields": fields,
            "filters": filters,
            "page": page,
            "limit": 100,
            "sort": "Award ID",
            "order": "asc",
            "subawards": False,
        }
        response = requests.post(USASPENDING_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        body = response.json()

        results = body.get("results", [])
        for award in results:
            pop_end_raw = award.get("Period of Performance Current End Date") or award.get(
                "Period of Performance End Date"
            )
            pop_end = parse_date(pop_end_raw)
            if not pop_end:
                continue
            if fy_start <= pop_end <= fy_end:
                selected.append(award)

        metadata = body.get("page_metadata", {})
        if not metadata.get("hasNext"):
            break
    return selected


def build_recompete_rows(awards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Transform award payloads into ParaCharts rows and detail rows."""
    para_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    for award in awards:
        agency = str(award.get("Awarding Agency") or "Unknown")
        award_amount = float(award.get("Award Amount") or 0.0)
        pop_end_raw = award.get("Period of Performance Current End Date") or award.get(
            "Period of Performance End Date"
        )
        pop_end = parse_date(pop_end_raw)
        if not pop_end:
            continue

        set_aside_text = str(award.get("Type Set Aside") or "Unknown")
        is_set_aside = is_small_business_set_aside(set_aside_text)
        labor_category = infer_labor_category(str(award.get("Description") or ""))
        benchmark_diff = benchmark_diff_percent(labor_category)

        para_rows.append(
            {
                "agency": agency,
                "value": award_amount,
                "expiry_quarter": quarter_from_date(pop_end),
                "set_aside_status": set_aside_text,
                "benchmark_diff": benchmark_diff,
            }
        )

        detail_rows.append(
            {
                "award_id": award.get("Award ID"),
                "recipient_name": award.get("Recipient Name"),
                "recipient_uei": award.get("Recipient UEI"),
                "agency": agency,
                "award_amount": award_amount,
                "period_of_performance_end_date": str(pop_end),
                "set_aside_status": set_aside_text,
                "rule_of_two_note": far_rule_of_two_note(is_set_aside),
                "labor_category": labor_category,
                "benchmark_diff": benchmark_diff,
            }
        )

    return para_rows, detail_rows


def write_summary_md(
    path: Path,
    companies: list[Company],
    fy_start: date,
    fy_end: date,
    para_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
) -> None:
    """Write a Markdown summary in repo reporting style."""
    by_agency: dict[str, int] = {}
    for row in para_rows:
        agency = str(row.get("agency") or "Unknown")
        by_agency[agency] = by_agency.get(agency, 0) + 1

    top_agencies = sorted(by_agency.items(), key=lambda item: item[1], reverse=True)[:10]
    set_aside_count = sum(1 for row in detail_rows if is_small_business_set_aside(row.get("set_aside_status")))

    lines = [
        "# Recompete Discovery Summary",
        "",
        f"- Cohort size: {len(companies)} companies",
        f"- FY window: {fy_start} to {fy_end}",
        f"- Expiring awards found: {len(detail_rows)}",
        f"- Small-business set-aside awards: {set_aside_count}",
        "- Data source: USASpending API (no SAM.gov key required)",
        "- FAR reference: 19.5 / 19.502-2 (Rule of Two)",
        "- Rate benchmark method: neutral placeholder until gsa_calc adapter is connected",
        "",
        "## Top Agencies by Expiring Awards",
        "",
    ]

    if top_agencies:
        for agency, count in top_agencies:
            lines.append(f"- {agency}: {count}")
    else:
        lines.append("No awards found in selected period.")

    lines.extend(["", "## Sample Award Rows", ""])

    for row in detail_rows[:15]:
        lines.extend(
            [
                f"### {row.get('recipient_name', 'Unknown recipient')} | {row.get('award_id', 'Unknown award')}",
                "",
                f"- Agency: {row.get('agency', 'Unknown')}",
                f"- POP End: {row.get('period_of_performance_end_date', '')}",
                f"- Set-Aside: {row.get('set_aside_status', 'Unknown')}",
                f"- FAR 19.5 note: {row.get('rule_of_two_note', '')}",
                f"- Labor Category: {row.get('labor_category', 'General IT Services')}",
                f"- Benchmark diff: {row.get('benchmark_diff', 0.0)}%",
                "",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_paracharts_specs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build ParaCharts-compatible manifest specs from recompete rows."""
    agency_totals: dict[str, float] = {}
    quarter_counts: dict[str, int] = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    set_aside_counts: dict[str, int] = {}
    benchmark_bands = {
        "Below -10%": 0,
        "-10% to +10%": 0,
        "+10% to +25%": 0,
        "Above +25%": 0,
    }

    for row in rows:
        agency = str(row.get("agency") or "Unknown")
        value = float(row.get("value") or 0.0)
        quarter = str(row.get("expiry_quarter") or "Q1")
        set_aside = str(row.get("set_aside_status") or "Unknown")
        benchmark = float(row.get("benchmark_diff") or 0.0)

        agency_totals[agency] = agency_totals.get(agency, 0.0) + value
        if quarter in quarter_counts:
            quarter_counts[quarter] += 1
        else:
            quarter_counts[quarter] = quarter_counts.get(quarter, 0) + 1
        set_aside_counts[set_aside] = set_aside_counts.get(set_aside, 0) + 1

        if benchmark < -10:
            benchmark_bands["Below -10%"] += 1
        elif benchmark <= 10:
            benchmark_bands["-10% to +10%"] += 1
        elif benchmark <= 25:
            benchmark_bands["+10% to +25%"] += 1
        else:
            benchmark_bands["Above +25%"] += 1

    top_agencies = sorted(agency_totals.items(), key=lambda item: item[1], reverse=True)[:15]
    top_set_asides = sorted(set_aside_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    quarter_order = ["Q1", "Q2", "Q3", "Q4"]

    manifests = [
        {
            "id": "agency-value-bar",
            "title": "Recompete Value by Agency",
            "description": "Total expiring award value by awarding agency.",
            "manifest": {
                "type": "bar",
                "series": [
                    {
                        "name": "Total Value",
                        "data": [round(amount, 2) for _, amount in top_agencies],
                    }
                ],
                "categories": [agency for agency, _ in top_agencies],
            },
        },
        {
            "id": "expiry-quarter-column",
            "title": "Expiry Quarter Distribution",
            "description": "Count of expiring awards by fiscal quarter.",
            "manifest": {
                "type": "column",
                "series": [
                    {
                        "name": "Expiring Awards",
                        "data": [quarter_counts.get(quarter, 0) for quarter in quarter_order],
                    }
                ],
                "categories": quarter_order,
            },
        },
        {
            "id": "set-aside-donut",
            "title": "Set-Aside Status Mix",
            "description": "Distribution of set-aside statuses in expiring awards.",
            "manifest": {
                "type": "donut",
                "series": [
                    {
                        "name": "Set-Aside Count",
                        "data": [count for _, count in top_set_asides],
                    }
                ],
                "categories": [status for status, _ in top_set_asides],
            },
        },
        {
            "id": "benchmark-diff-bar",
            "title": "Benchmark Difference Bands",
            "description": "Count of rows grouped by benchmark difference bands.",
            "manifest": {
                "type": "bar",
                "series": [
                    {
                        "name": "Rows",
                        "data": [benchmark_bands[key] for key in benchmark_bands],
                    }
                ],
                "categories": list(benchmark_bands.keys()),
            },
        },
    ]

    return {
        "version": "1.0",
        "source": "docs/data/recompetes.json",
        "row_count": len(rows),
        "manifests": manifests,
    }


def main() -> None:
    """Run recompete extraction and output JSON+Markdown artifacts."""
    args = parse_args()

    fy_start = date.fromisoformat(args.fy_start)
    fy_end = date.fromisoformat(args.fy_end)
    companies_file = resolve_companies_file(args.cohort, args.companies_file)
    companies = load_companies(companies_file)

    all_awards: list[dict[str, Any]] = []
    for company in companies:
        awards = search_awards_for_company(
            company=company,
            fy_start=fy_start,
            fy_end=fy_end,
            max_pages=args.max_pages_per_company,
        )
        all_awards.extend(awards)

    para_rows, detail_rows = build_recompete_rows(all_awards)

    output_json_path = Path(args.output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(para_rows, indent=2), encoding="utf-8")

    docs_output_path = Path(args.output_docs_json) if args.output_docs_json else None
    if docs_output_path:
        docs_output_path.parent.mkdir(parents=True, exist_ok=True)
        docs_output_path.write_text(json.dumps(para_rows, indent=2), encoding="utf-8")

    paracharts_output_path = Path(args.output_paracharts_spec) if args.output_paracharts_spec else None
    if paracharts_output_path:
        paracharts_output_path.parent.mkdir(parents=True, exist_ok=True)
        paracharts_specs = build_paracharts_specs(para_rows)
        paracharts_output_path.write_text(json.dumps(paracharts_specs, indent=2), encoding="utf-8")

    write_summary_md(
        path=Path(args.output_md),
        companies=companies,
        fy_start=fy_start,
        fy_end=fy_end,
        para_rows=para_rows,
        detail_rows=detail_rows,
    )

    print(f"Loaded {len(companies)} companies")
    print(f"Company source: {companies_file}")
    print(f"Found {len(detail_rows)} expiring awards in window")
    print(f"Wrote {output_json_path}")
    if docs_output_path:
        print(f"Wrote {docs_output_path}")
    if paracharts_output_path:
        print(f"Wrote {paracharts_output_path}")
    print(f"Wrote {Path(args.output_md)}")


if __name__ == "__main__":
    main()
