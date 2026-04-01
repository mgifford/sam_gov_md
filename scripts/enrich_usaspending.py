#!/usr/bin/env python3
"""Enrich high-value SAM.gov alerts with USASpending market intelligence.

Reads high_value_matches.json (produced by generate_alerts.py) and
records.json (produced by process_today.py), calls the free USASpending
API for each unique (NAICS, agency) pair found in the matches, then
rewrites high_value_alert.md with a market-intel section appended to
each match entry.

Outputs
-------
data/today/usaspending_enrichment.json   Per-match enrichment payload.
data/today/high_value_alert.md           Overwritten with market intel added.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

USASPENDING_BASE = "https://api.usaspending.gov/api/v2"
LOOKBACK_YEARS = 3
REQUEST_TIMEOUT = 20
RETRY_DELAY = 2.0

# Map SAM.gov all-caps agency names to USASpending toptier agency names.
AGENCY_NAME_MAP: dict[str, str] = {
    "DEPT OF DEFENSE": "Department of Defense",
    "DEFENSE, DEPARTMENT OF": "Department of Defense",
    "VETERANS AFFAIRS, DEPARTMENT OF": "Department of Veterans Affairs",
    "HOMELAND SECURITY, DEPARTMENT OF": "Department of Homeland Security",
    "HEALTH AND HUMAN SERVICES, DEPARTMENT OF": (
        "Department of Health and Human Services"
    ),
    "GENERAL SERVICES ADMINISTRATION": "General Services Administration",
    "INTERIOR, DEPARTMENT OF THE": "Department of the Interior",
    "JUSTICE, DEPARTMENT OF": "Department of Justice",
    "TRANSPORTATION, DEPARTMENT OF": "Department of Transportation",
    "TREASURY, DEPARTMENT OF THE": "Department of the Treasury",
    "ENERGY, DEPARTMENT OF": "Department of Energy",
    "STATE, DEPARTMENT OF": "Department of State",
    "AGRICULTURE, DEPARTMENT OF": "Department of Agriculture",
    "EDUCATION, DEPARTMENT OF": "Department of Education",
    "LABOR, DEPARTMENT OF": "Department of Labor",
    "COMMERCE, DEPARTMENT OF": "Department of Commerce",
    "HOUSING AND URBAN DEVELOPMENT, DEPARTMENT OF": (
        "Department of Housing and Urban Development"
    ),
    "ENVIRONMENTAL PROTECTION AGENCY": "Environmental Protection Agency",
    "NATIONAL AERONAUTICS AND SPACE ADMINISTRATION": (
        "National Aeronautics and Space Administration"
    ),
    "SOCIAL SECURITY ADMINISTRATION": "Social Security Administration",
}

CONTRACT_TYPE_CODES = ["A", "B", "C", "D"]


def _fiscal_year_range(lookback: int) -> list[dict[str, str]]:
    """Return a list with one time-period dict spanning the last N fiscal years."""
    from datetime import date

    today = date.today()
    # Fiscal year starts Oct 1; end of most recent complete FY
    fy_end = date(today.year, 9, 30) if today.month > 9 else date(today.year - 1, 9, 30)
    fy_start = date(fy_end.year - lookback + 1, 10, 1)
    return [{"start_date": str(fy_start), "end_date": str(fy_end)}]


def _post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST to a USASpending endpoint and return parsed JSON, or None on error."""
    url = f"{USASPENDING_BASE}/{endpoint}"
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("USASpending request failed (%s): %s", url, exc)
        time.sleep(RETRY_DELAY)
        return None


def normalize_agency(sam_agency: str) -> str | None:
    """Convert a SAM.gov agency name to a USASpending toptier agency name."""
    return AGENCY_NAME_MAP.get((sam_agency or "").strip().upper())


def fetch_award_count(naics: str, agency_name: str, time_period: list) -> int:
    """Return the number of contracts at *agency_name* for *naics* in *time_period*."""
    filters: dict[str, Any] = {
        "time_period": time_period,
        "award_type_codes": CONTRACT_TYPE_CODES,
        "naics_codes": [naics],
    }
    if agency_name:
        filters["agencies"] = [
            {"type": "awarding", "tier": "toptier", "name": agency_name}
        ]
    result = _post("search/spending_by_award_count/", {"filters": filters})
    if result:
        return int(result.get("results", {}).get("contracts", 0))
    return 0


def fetch_top_vendors(
    naics: str,
    agency_name: str | None,
    time_period: list,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return top *limit* vendors by award amount for *naics* / *agency_name*."""
    filters: dict[str, Any] = {
        "time_period": time_period,
        "award_type_codes": CONTRACT_TYPE_CODES,
        "naics_codes": [naics],
    }
    if agency_name:
        filters["agencies"] = [
            {"type": "awarding", "tier": "toptier", "name": agency_name}
        ]
    result = _post(
        "search/spending_by_category/recipient/",
        {"filters": filters, "limit": limit, "page": 1},
    )
    if not result:
        return []
    vendors = []
    for item in result.get("results", []):
        vendors.append(
            {
                "name": item.get("name", ""),
                "amount": item.get("amount", 0),
            }
        )
    return vendors


def enrich_match(
    naics: str,
    sam_agency: str,
    time_period: list,
) -> dict[str, Any]:
    """Fetch all USASpending intel for one (naics, agency) pair."""
    usa_agency = normalize_agency(sam_agency)

    agency_count = fetch_award_count(naics, usa_agency or "", time_period)
    govwide_vendors = fetch_top_vendors(naics, None, time_period)
    agency_vendors = fetch_top_vendors(naics, usa_agency, time_period) if usa_agency else []

    return {
        "naics": naics,
        "sam_agency": sam_agency,
        "usaspending_agency": usa_agency,
        "lookback_years": LOOKBACK_YEARS,
        "agency_contract_count": agency_count,
        "govwide_top_vendors": govwide_vendors,
        "agency_top_vendors": agency_vendors,
    }


def _fmt_vendors(vendors: list[dict[str, Any]]) -> str:
    """Format a vendor list as a compact human-readable string."""
    if not vendors:
        return "No data"
    parts = [
        f"{v['name'].title()[:35]} (${v['amount']:,.0f})"
        for v in vendors[:5]
    ]
    return "; ".join(parts)


def _fmt_currency(amount: float) -> str:
    """Return a human-friendly dollar string (e.g. $4.2M, $830K)."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.0f}K"
    return f"${amount:,.0f}"


def build_enriched_markdown(
    selected: list[dict[str, Any]],
    enrichment_by_notice: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    min_hits: int,
    focus_terms: list[str],
) -> str:
    """Render the full enriched high_value_alert.md content."""
    lines = [
        "# High-value SAM.gov Matches",
        "",
        f"- Effective date: {summary.get('effective_date')}",
        f"- Requested date: {summary.get('requested_date')}",
        f"- Candidate records: {summary.get('records_total', 0)}",
        f"- High-value matches: {len(selected)}",
        f"- Threshold: total term hits >= {min_hits} and includes one focus term",
        "",
    ]

    if not selected:
        lines.append("No high-value matches were found for this snapshot.")
        return "\n".join(lines)

    for row in selected:
        notice_id = row.get("NoticeId", "")
        naics = row.get("NaicsCode") or ""
        lines += [
            f"## {row.get('Title', 'Untitled')}",
            "",
            f"- Department: {row.get('Agency', 'Unknown')}",
            f"- Type: {row.get('Type', 'Unknown')}",
            f"- PostedDate: {row.get('PostedDate', '')}",
            f"- NAICS: {naics or 'Not specified'}",
            f"- Total term hits: {row.get('total_hits', 0)}",
            f"- Link: {row.get('Link', '')}",
            "- Top terms: "
            + ", ".join(
                f"{m.get('term')}({m.get('count')})"
                for m in row.get("matches", [])[:6]
            ),
        ]

        intel = enrichment_by_notice.get(notice_id)
        if intel and naics:
            lines.append("")
            lines.append("### Market Intelligence (USASpending)")
            lines.append("")
            lines.append(
                f"- Agency contracts ({LOOKBACK_YEARS}yr, NAICS {naics}): "
                f"{intel['agency_contract_count']:,}"
            )
            gv = intel.get("govwide_top_vendors", [])
            if gv:
                lines.append(
                    f"- Gov-wide top vendors: {_fmt_vendors(gv)}"
                )
            av = intel.get("agency_top_vendors", [])
            if av:
                lines.append(
                    f"- Agency top vendors: {_fmt_vendors(av)}"
                )

        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Parse arguments, enrich high-value matches via USASpending, rewrite alert."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Enrich high-value SAM.gov alerts with USASpending data"
    )
    parser.add_argument(
        "--matches",
        default="data/today/high_value_matches.json",
        help="Path to high_value_matches.json produced by generate_alerts.py",
    )
    parser.add_argument(
        "--records",
        default="data/today/records.json",
        help="Path to records.json (fallback NAICS lookup for older match files)",
    )
    parser.add_argument(
        "--summary",
        default="data/today/summary.json",
        help="Path to summary.json produced by process_today.py",
    )
    parser.add_argument(
        "--output-enrichment",
        default="data/today/usaspending_enrichment.json",
        help="Output path for per-match enrichment JSON",
    )
    parser.add_argument(
        "--output-md",
        default="data/today/high_value_alert.md",
        help="Path to high_value_alert.md to rewrite with market intel",
    )
    parser.add_argument(
        "--lookback-years",
        type=int,
        default=LOOKBACK_YEARS,
        help="Number of fiscal years to look back in USASpending (default: 3)",
    )
    args = parser.parse_args()

    matches_path = Path(args.matches)
    if not matches_path.exists():
        logger.error("Matches file not found: %s", matches_path)
        raise SystemExit(1)

    hvm = json.loads(matches_path.read_text(encoding="utf-8"))
    selected: list[dict[str, Any]] = hvm.get("matches", [])

    # Build a NoticeId → NaicsCode lookup from records.json as a fallback
    # for matches generated before NaicsCode was added to top_matching_records.
    records_path = Path(args.records)
    naics_by_notice: dict[str, str] = {}
    if records_path.exists():
        records = json.loads(records_path.read_text(encoding="utf-8"))
        for rec in records:
            nid = rec.get("NoticeId", "")
            naics = (rec.get("NaicsCode") or "").strip()
            if nid and naics:
                naics_by_notice[nid] = naics
        logger.info("Loaded NAICS lookup for %d records.", len(naics_by_notice))

    # Backfill NaicsCode on any match entry that is missing it.
    for row in selected:
        if not row.get("NaicsCode"):
            row["NaicsCode"] = naics_by_notice.get(row.get("NoticeId", ""), "")

    if not selected:
        logger.info("No high-value matches to enrich.")
        return

    summary_path = Path(args.summary)
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}

    time_period = _fiscal_year_range(args.lookback_years)
    logger.info(
        "Enriching %d matches via USASpending (%d-year lookback)...",
        len(selected),
        args.lookback_years,
    )

    # Deduplicate API calls by (naics, agency) pair.
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    enrichment_by_notice: dict[str, dict[str, Any]] = {}

    for row in selected:
        notice_id = row.get("NoticeId", "")
        naics = (row.get("NaicsCode") or "").strip()
        agency = (row.get("Agency") or "").strip()

        if not naics:
            logger.info("Skipping %s — no NAICS code", row.get("Title", notice_id))
            continue

        key = (naics, agency)
        if key not in cache:
            logger.info("Fetching USASpending: NAICS %s / %s", naics, agency)
            cache[key] = enrich_match(naics, agency, time_period)
            time.sleep(0.5)  # be polite to the public API

        enrichment_by_notice[notice_id] = cache[key]

    # Persist enrichment JSON.
    enrichment_payload = {
        "requested_date": hvm.get("requested_date"),
        "lookback_years": args.lookback_years,
        "time_period": time_period,
        "enriched_count": len(enrichment_by_notice),
        "by_notice_id": enrichment_by_notice,
    }
    out_enrichment = Path(args.output_enrichment)
    out_enrichment.write_text(json.dumps(enrichment_payload, indent=2), encoding="utf-8")
    logger.info("Wrote enrichment data → %s", out_enrichment)

    # Rewrite high_value_alert.md with market intel sections.
    md_content = build_enriched_markdown(
        selected=selected,
        enrichment_by_notice=enrichment_by_notice,
        summary=summary,
        min_hits=hvm.get("min_hits", 8),
        focus_terms=hvm.get("focus_terms", []),
    )
    out_md = Path(args.output_md)
    out_md.write_text(md_content, encoding="utf-8")
    logger.info("Rewrote alert markdown → %s", out_md)

    logger.info(
        "Done. %d/%d matches enriched.", len(enrichment_by_notice), len(selected)
    )


if __name__ == "__main__":
    main()
