#!/usr/bin/env python3
"""Export department trends from SQLite for visualization."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export department trends from SQLite")
    parser.add_argument("--db", default="data/opportunities.sqlite")
    parser.add_argument("--output-dir", default="docs/data")
    args = parser.parse_args()

    db_path = Path(args.db)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Get all unique agencies and their activity over time
        query = """
        SELECT
            o.agency,
            s.snapshot_date,
            COUNT(*) as count,
            SUM(CASE WHEN o.is_win = 1 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN o.is_win = 0 THEN 1 ELSE 0 END) as opportunities
        FROM opportunity_sightings s
        JOIN opportunities o ON o.notice_id = s.notice_id
        GROUP BY o.agency, s.snapshot_date
        ORDER BY s.snapshot_date DESC, o.agency ASC
        """

        rows = conn.execute(query).fetchall()

        # Transform into timeseries format
        by_agency: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            agency = (row["agency"] or "Unknown").strip()
            by_agency[agency].append(
                {
                    "date": row["snapshot_date"],
                    "count": row["count"],
                    "wins": row["wins"],
                    "opportunities": row["opportunities"],
                }
            )

        # Sort each agency's timeline chronologically
        for agency in by_agency:
            by_agency[agency].sort(key=lambda x: x["date"])

        # Build overall timeline
        all_dates = set()
        for rows_list in by_agency.values():
            for row in rows_list:
                all_dates.add(row["date"])
        sorted_dates = sorted(all_dates)

        # Build top agencies list (by most recent snapshot)
        top_agencies = []
        recap_query = """
        SELECT
            agency,
            COUNT(*) as total,
            SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN is_win = 0 THEN 1 ELSE 0 END) as opportunities,
            COUNT(DISTINCT (SELECT snapshot_date FROM opportunity_sightings WHERE notice_id = opportunities.notice_id LIMIT 1)) as days_seen
        FROM opportunities
        GROUP BY agency
        ORDER BY total DESC
        LIMIT 15
        """
        recap_rows = conn.execute(recap_query).fetchall()
        for row in recap_rows:
            top_agencies.append(
                {
                    "agency": (row["agency"] or "Unknown").strip(),
                    "total": row["total"],
                    "wins": row["wins"],
                    "opportunities": row["opportunities"],
                    "days_seen": row["days_seen"],
                }
            )

    payload = {
        "timeline": sorted_dates,
        "agencies": by_agency,
        "top_agencies": top_agencies,
    }

    output_path = output_dir / "trends.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote trends to {output_path}")


if __name__ == "__main__":
    main()
