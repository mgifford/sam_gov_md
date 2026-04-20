#!/usr/bin/env python3
"""
Compute RFP-to-award cycle-time analytics from the SQLite opportunities database.

For each Award Notice, we attempt to find the corresponding Solicitation via
the shared sol_number and measure the elapsed days from solicitation posting to
award date.  Results are aggregated by contract officer and by agency.

Additionally, solicitations that have not been re-sighted for --stale-days days
and have no matching Award Notice are flagged as abandoned/never-awarded.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


_SOLICITATION_TYPES = (
    "Solicitation",
    "Combined Synopsis/Solicitation",
    "Presolicitation",
)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S.%f%z",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
)


def _parse_date(value: str | None) -> date | None:
    """Return a :class:`datetime.date` parsed from *value*, or ``None``."""
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    # Last-resort: truncate to first 10 chars (YYYY-MM-DD) and try again
    truncated = (value.strip())[:10]
    try:
        return datetime.strptime(truncated, "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_between(start: date | None, end: date | None) -> int | None:
    """Return the integer number of days from *start* to *end*, or ``None``."""
    if start is None or end is None:
        return None
    delta = (end - start).days
    return delta if delta >= 0 else None


def compute_cycle_times(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """
    Join Award Notices to their source Solicitation via sol_number and return
    a list of cycle-time records, each describing one matched pair.
    """
    conn.row_factory = sqlite3.Row

    # Fetch all Award Notices that have an award_date and a sol_number
    awards = conn.execute(
        """
        SELECT notice_id, sol_number, title, agency, award_date,
               contract_officer, awardee
        FROM opportunities
        WHERE notice_type = 'Award Notice'
          AND award_date IS NOT NULL
          AND award_date != ''
          AND sol_number IS NOT NULL
          AND sol_number != ''
        """
    ).fetchall()

    # Build a lookup of solicitations by sol_number (keep the earliest posted_date)
    solicitations: dict[str, dict] = {}
    sol_rows = conn.execute(
        """
        SELECT sol_number, notice_id, agency, posted_date, contract_officer
        FROM opportunities
        WHERE notice_type IN ({})
          AND sol_number IS NOT NULL
          AND sol_number != ''
          AND posted_date IS NOT NULL
          AND posted_date != ''
        ORDER BY posted_date ASC
        """.format(", ".join("?" * len(_SOLICITATION_TYPES))),
        _SOLICITATION_TYPES,
    ).fetchall()

    for row in sol_rows:
        sol_num = row["sol_number"]
        if sol_num not in solicitations:
            solicitations[sol_num] = dict(row)

    cycle_times: list[dict[str, Any]] = []
    for award in awards:
        sol_num = award["sol_number"]
        sol = solicitations.get(sol_num)
        if sol is None:
            continue

        sol_posted = _parse_date(sol["posted_date"])
        award_dt = _parse_date(award["award_date"])
        days = _days_between(sol_posted, award_dt)
        if days is None:
            continue

        cycle_times.append(
            {
                "notice_id": award["notice_id"],
                "sol_number": sol_num,
                "title": award["title"],
                "agency": award["agency"] or sol["agency"] or "Unknown",
                "award_date": award["award_date"],
                "sol_posted_date": sol["posted_date"],
                "days_to_award": days,
                "contract_officer": award["contract_officer"] or sol["contract_officer"],
                "awardee": award["awardee"],
            }
        )

    return cycle_times


def aggregate_by_officer(
    cycle_times: list[dict[str, Any]],
    min_awards: int = 1,
    officer_emails: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Aggregate cycle-time statistics grouped by contract officer."""
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"days": [], "agencies": set()}
    )

    for ct in cycle_times:
        officer = ct["contract_officer"] or "Unknown"
        stats[officer]["days"].append(ct["days_to_award"])
        if ct["agency"]:
            stats[officer]["agencies"].add(ct["agency"])

    result = []
    for officer, data in stats.items():
        days_list = data["days"]
        if len(days_list) < min_awards:
            continue
        result.append(
            {
                "name": officer,
                "email": (officer_emails or {}).get(officer),
                "agencies": sorted(data["agencies"]),
                "avg_days": round(sum(days_list) / len(days_list), 1),
                "median_days": median(days_list),
                "fastest_award": min(days_list),
                "slowest_award": max(days_list),
                "awarded": len(days_list),
            }
        )

    result.sort(key=lambda x: x["avg_days"])
    return result


def aggregate_by_agency(
    cycle_times: list[dict[str, Any]],
    abandoned: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate cycle-time statistics grouped by agency."""
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"days": []})

    for ct in cycle_times:
        agency = ct["agency"] or "Unknown"
        stats[agency]["days"].append(ct["days_to_award"])

    # Count abandoned per agency
    abandoned_by_agency: dict[str, int] = defaultdict(int)
    for opp in abandoned:
        abandoned_by_agency[opp["agency"] or "Unknown"] += 1

    # Collect all known agencies (including those with only abandoned opps)
    all_agencies = set(stats.keys()) | set(abandoned_by_agency.keys())

    result = []
    for agency in all_agencies:
        days_list = stats[agency]["days"]
        entry: dict[str, Any] = {
            "agency": agency,
            "awarded": len(days_list),
            "never_awarded_count": abandoned_by_agency.get(agency, 0),
        }
        if days_list:
            entry["avg_days"] = round(sum(days_list) / len(days_list), 1)
            entry["median_days"] = median(days_list)
            entry["fastest_award"] = min(days_list)
            entry["slowest_award"] = max(days_list)
        else:
            entry["avg_days"] = None
            entry["median_days"] = None
            entry["fastest_award"] = None
            entry["slowest_award"] = None

        result.append(entry)

    # Sort: agencies with timing data first (by avg_days asc), then those without
    result.sort(
        key=lambda x: (x["avg_days"] is None, x["avg_days"] if x["avg_days"] is not None else 0)
    )
    return result


def find_abandoned(
    conn: sqlite3.Connection,
    stale_days: int,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """
    Return solicitations that have no matching Award Notice in the DB and whose
    last_seen_date is more than *stale_days* days before *as_of*.
    """
    if as_of is None:
        as_of = datetime.now(tz=timezone.utc).date()

    conn.row_factory = sqlite3.Row

    # Build set of sol_numbers that have been awarded
    awarded_sol_numbers: set[str] = set(
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT sol_number
            FROM opportunities
            WHERE notice_type = 'Award Notice'
              AND sol_number IS NOT NULL
              AND sol_number != ''
            """
        ).fetchall()
    )

    solicitations = conn.execute(
        """
        SELECT notice_id, sol_number, title, agency, contract_officer,
               posted_date, last_seen_date
        FROM opportunities
        WHERE notice_type IN ({})
          AND sol_number IS NOT NULL
          AND sol_number != ''
        """.format(", ".join("?" * len(_SOLICITATION_TYPES))),
        _SOLICITATION_TYPES,
    ).fetchall()

    abandoned = []
    for row in solicitations:
        if row["sol_number"] in awarded_sol_numbers:
            continue

        last_seen = _parse_date(row["last_seen_date"])
        if last_seen is None:
            continue

        days_since = (as_of - last_seen).days
        if days_since > stale_days:
            abandoned.append(
                {
                    "notice_id": row["notice_id"],
                    "title": row["title"],
                    "agency": row["agency"] or "Unknown",
                    "officer": row["contract_officer"],
                    "posted_date": row["posted_date"],
                    "last_seen_date": row["last_seen_date"],
                    "days_since_last_seen": days_since,
                }
            )

    abandoned.sort(key=lambda x: x["days_since_last_seen"], reverse=True)
    return abandoned


def build_output(
    conn: sqlite3.Connection,
    stale_days: int = 90,
    min_awards: int = 1,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Build the full time_to_award JSON payload."""
    if as_of is None:
        as_of = datetime.now(tz=timezone.utc).date()

    cycle_times = compute_cycle_times(conn)
    abandoned = find_abandoned(conn, stale_days=stale_days, as_of=as_of)

    # Officer email lookup: not stored in the current DB schema;
    # leave as empty dict so name-only reporting still works.
    officer_emails: dict[str, str] = {}

    by_officer = aggregate_by_officer(
        cycle_times, min_awards=min_awards, officer_emails=officer_emails
    )
    by_agency = aggregate_by_agency(cycle_times, abandoned)

    all_days = [ct["days_to_award"] for ct in cycle_times]
    overall_avg = round(sum(all_days) / len(all_days), 1) if all_days else None
    overall_median = median(all_days) if all_days else None

    return {
        "generated_date": as_of.isoformat(),
        "stale_days_threshold": stale_days,
        "summary": {
            "total_awards_with_timing": len(cycle_times),
            "avg_days_to_award": overall_avg,
            "median_days_to_award": overall_median,
            "fastest_award_days": min(all_days) if all_days else None,
            "slowest_award_days": max(all_days) if all_days else None,
            "total_abandoned": len(abandoned),
            "officers_with_timing": len(by_officer),
            "agencies_with_timing": sum(1 for a in by_agency if a["avg_days"] is not None),
        },
        "by_officer": by_officer,
        "by_agency": by_agency,
        "abandoned_opportunities": abandoned,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute RFP-to-award cycle-time analytics from SQLite"
    )
    parser.add_argument("--db", default="data/opportunities.sqlite")
    parser.add_argument("--output", default="docs/data/time_to_award.json")
    parser.add_argument(
        "--stale-days",
        type=int,
        default=90,
        help="Days since last sighting before a solicitation is flagged as abandoned",
    )
    parser.add_argument(
        "--min-awards",
        type=int,
        default=1,
        help="Minimum award count for an officer to appear in by_officer rankings",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        payload = build_output(
            conn, stale_days=args.stale_days, min_awards=args.min_awards
        )

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    summary = payload["summary"]
    print("✅ Time-to-award analytics complete")
    print(f"   Awards with timing data : {summary['total_awards_with_timing']}")
    print(f"   Average days to award   : {summary['avg_days_to_award']}")
    print(f"   Median days to award    : {summary['median_days_to_award']}")
    print(f"   Abandoned solicitations : {summary['total_abandoned']}")
    print(f"📁 Results saved to {output_path}")


if __name__ == "__main__":
    main()
