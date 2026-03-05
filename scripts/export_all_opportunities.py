#!/usr/bin/env python3
"""Export all opportunities from SQLite to JSON for search and analysis."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export all opportunities from SQLite to JSON for search"
    )
    parser.add_argument("--db", default="data/opportunities.sqlite")
    parser.add_argument(
        "--output",
        default="docs/data/all_opportunities.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of records to export (0 = no limit)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        output_path.write_text(json.dumps([]), encoding="utf-8")
        return

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        query = """
        SELECT
            notice_id  AS NoticeId,
            sol_number AS "Sol#",
            title      AS Title,
            agency     AS Agency,
            notice_type AS Type,
            posted_date AS PostedDate,
            response_deadline AS ResponseDeadLine,
            naics_code AS NaicsCode,
            link       AS Link,
            is_win,
            first_seen_date,
            last_seen_date,
            seen_count,
            last_snapshot_date
        FROM opportunities
        ORDER BY posted_date DESC, last_seen_date DESC
        """

        if args.limit > 0:
            rows = conn.execute(query + " LIMIT ?", (args.limit,)).fetchall()
        else:
            rows = conn.execute(query).fetchall()

    records = []
    for row in rows:
        record = dict(row)
        record["is_win"] = bool(record.get("is_win"))
        records.append(record)

    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Exported {len(records)} opportunities to {output_path}")


if __name__ == "__main__":
    main()
