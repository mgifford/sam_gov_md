#!/usr/bin/env python3
"""Persist daily opportunity snapshot to SQLite with dedup and history."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            notice_id TEXT PRIMARY KEY,
            sol_number TEXT,
            title TEXT,
            agency TEXT,
            notice_type TEXT,
            posted_date TEXT,
            response_deadline TEXT,
            naics_code TEXT,
            link TEXT,
            is_win INTEGER NOT NULL,
            first_seen_date TEXT NOT NULL,
            last_seen_date TEXT NOT NULL,
            seen_count INTEGER NOT NULL DEFAULT 1,
            last_snapshot_date TEXT NOT NULL,
            description TEXT,
            matches TEXT,
            awardee TEXT,
            set_aside TEXT,
            additional_info_link TEXT
        )
        """
    )
    # Migrate existing tables that predate added columns
    for col, col_type in [
        ("description", "TEXT"),
        ("matches", "TEXT"),
        ("awardee", "TEXT"),
        ("set_aside", "TEXT"),
        ("additional_info_link", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE opportunities ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunity_sightings (
            notice_id TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (notice_id, snapshot_date)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunities_agency ON opportunities (agency)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunities_type ON opportunities (notice_type)
        """
    )


def upsert_record(conn: sqlite3.Connection, row: dict, snapshot_date: str) -> str:
    notice_id = (row.get("NoticeId") or "").strip()
    if not notice_id:
        return "skipped"

    existing = conn.execute(
        "SELECT notice_id FROM opportunities WHERE notice_id = ?", (notice_id,)
    ).fetchone()

    is_win = 1 if ("award" in (row.get("Type") or "").lower() or "win" in (row.get("Type") or "").lower()) else 0

    # Truncate description to 1000 chars for storage; full text lives in markdown files
    raw_description = row.get("Description") or ""
    description = raw_description[:1000] if raw_description else None

    # Store top matches as a compact JSON string
    matches_list = row.get("matches") or []
    matches_json = json.dumps(matches_list[:10]) if matches_list else None

    awardee = (row.get("Awardee") or "").strip() or None
    set_aside = (row.get("SetASide") or row.get("SetASideCode") or "").strip() or None
    additional_info_link = (row.get("AdditionalInfoLink") or "").strip() or None

    conn.execute(
        """
        INSERT INTO opportunities (
            notice_id, sol_number, title, agency, notice_type, posted_date,
            response_deadline, naics_code, link, is_win, first_seen_date,
            last_seen_date, seen_count, last_snapshot_date,
            description, matches, awardee, set_aside, additional_info_link
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(notice_id) DO UPDATE SET
            sol_number = excluded.sol_number,
            title = excluded.title,
            agency = excluded.agency,
            notice_type = excluded.notice_type,
            posted_date = excluded.posted_date,
            response_deadline = excluded.response_deadline,
            naics_code = excluded.naics_code,
            link = excluded.link,
            is_win = excluded.is_win,
            last_seen_date = excluded.last_seen_date,
            last_snapshot_date = excluded.last_snapshot_date,
            seen_count = opportunities.seen_count + 1,
            description = excluded.description,
            matches = excluded.matches,
            awardee = excluded.awardee,
            set_aside = excluded.set_aside,
            additional_info_link = excluded.additional_info_link
        """,
        (
            notice_id,
            row.get("Sol#"),
            row.get("Title"),
            row.get("Department/Ind.Agency"),
            row.get("Type"),
            row.get("PostedDate"),
            row.get("ResponseDeadLine"),
            row.get("NaicsCode"),
            row.get("Link"),
            is_win,
            snapshot_date,
            snapshot_date,
            snapshot_date,
            description,
            matches_json,
            awardee,
            set_aside,
            additional_info_link,
        ),
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO opportunity_sightings (notice_id, snapshot_date)
        VALUES (?, ?)
        """,
        (notice_id, snapshot_date),
    )

    return "updated" if existing else "inserted"


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist opportunity snapshot to SQLite")
    parser.add_argument("--records", default="data/today/records.json")
    parser.add_argument("--summary", default="data/today/summary.json")
    parser.add_argument("--db", default="data/opportunities.sqlite")
    parser.add_argument("--output", default="data/today/persistence_summary.json")
    args = parser.parse_args()

    records = json.loads(Path(args.records).read_text(encoding="utf-8"))
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    snapshot_date = summary.get("effective_date") or summary.get("requested_date")

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    inserted = 0
    updated = 0
    skipped = 0

    with sqlite3.connect(db_path) as conn:
        init_db(conn)
        for row in records:
            state = upsert_record(conn, row, snapshot_date)
            if state == "inserted":
                inserted += 1
            elif state == "updated":
                updated += 1
            else:
                skipped += 1
        conn.commit()

        total_unique = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
        total_sightings = conn.execute("SELECT COUNT(*) FROM opportunity_sightings").fetchone()[0]

    payload = {
        "snapshot_date": snapshot_date,
        "records_in_snapshot": len(records),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total_unique_opportunities": total_unique,
        "total_sightings": total_sightings,
        "db_path": str(db_path),
    }

    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
