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

        # Deduplicate by sol_number: keep the latest-posted revision per notice.
        # Records with no sol_number are treated as unique (partitioned by notice_id).
        # version_count exposes how many revisions existed for that solicitation.
        query = """
        WITH ranked AS (
            SELECT
                notice_id,
                sol_number,
                title,
                agency,
                notice_type,
                posted_date,
                response_deadline,
                naics_code,
                link,
                is_win,
                awardee,
                description,
                matches,
                first_seen_date,
                last_seen_date,
                seen_count,
                last_snapshot_date,
                set_aside,
                additional_info_link,
                ROW_NUMBER() OVER (
                    PARTITION BY CASE
                        WHEN sol_number IS NOT NULL AND sol_number != ''
                        THEN sol_number
                        ELSE notice_id
                    END
                    ORDER BY posted_date DESC, notice_id DESC
                ) AS rn,
                COUNT(*) OVER (
                    PARTITION BY CASE
                        WHEN sol_number IS NOT NULL AND sol_number != ''
                        THEN sol_number
                        ELSE notice_id
                    END
                ) AS version_count
            FROM opportunities
        )
        SELECT
            notice_id        AS NoticeId,
            sol_number       AS "Sol#",
            title            AS Title,
            agency           AS Agency,
            notice_type      AS Type,
            posted_date      AS PostedDate,
            response_deadline AS ResponseDeadLine,
            naics_code       AS NaicsCode,
            link             AS Link,
            is_win,
            awardee          AS Awardee,
            description      AS Description,
            matches,
            first_seen_date,
            last_seen_date,
            seen_count,
            last_snapshot_date,
            set_aside        AS SetAside,
            additional_info_link AS AdditionalInfoLink,
            version_count
        FROM ranked
        WHERE rn = 1
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
        # Parse stored matches JSON back to a list
        raw_matches = record.pop("matches", None)
        try:
            record["matches"] = json.loads(raw_matches) if raw_matches else []
        except (TypeError, ValueError):
            record["matches"] = []

        # Include extracted PDF/document text for full-text search
        notice_id = record.get("NoticeId") or ""
        if notice_id:
            pdf_content_path = Path("docs/opportunities") / notice_id / "pdf_content.md"
            if pdf_content_path.exists():
                try:
                    pdf_text = pdf_content_path.read_text(encoding="utf-8")
                    # Only mark as having PDF content when actual text was extracted
                    # (files with only the "No PDF" note are not useful for search)
                    has_real_content = "_No PDF attachments or document links were found" not in pdf_text
                    record["has_pdf_content"] = has_real_content
                    if has_real_content:
                        # Truncate to keep the JSON file manageable while still
                        # covering enough text for meaningful keyword search
                        record["pdf_text"] = pdf_text[:8000]
                except Exception:
                    record["has_pdf_content"] = False
            else:
                record["has_pdf_content"] = False
        else:
            record["has_pdf_content"] = False

        records.append(record)

    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Exported {len(records)} opportunities to {output_path}")


if __name__ == "__main__":
    main()
